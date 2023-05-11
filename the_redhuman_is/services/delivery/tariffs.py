import datetime
import json
import math
import time
from decimal import Decimal
from typing import (
    List,
    Optional,
    Tuple,
    Union,
    cast,
)

from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied

from django.db import transaction
from django.db.models import (
    CharField,
    OuterRef,
    Subquery,
)

from the_redhuman_is import geo_utils
from the_redhuman_is.async_utils import (
    dadata,
    googlemaps,
)
from the_redhuman_is.models.turnout_calculators import (
    calculate_delivery_request_hours,
    estimate_customer_price,
    get_delivery_request_bonus,
)
from the_redhuman_is.models.delivery import (
    DeliveryItem,
    DeliveryRequest,
    DeliveryService,
    DeliveryZone,
    ItemWorkerStart,
    GoogleMapsAddress,
    NormalizedAddress,
)
from the_redhuman_is.services.delivery import notifications
from the_redhuman_is.services.delivery_requests import customer_location
from the_redhuman_is.services.delivery.utils import (
    DeliveryWorkflowError,
    ensure_can_save_timesheet,
    update_delivery_request_status,
    update_request_timesheets,
    update_suspicion_flag,
    update_turnouts,
)
from the_redhuman_is.tasks import log

from utils import date_time


class AutotarificationError(Exception):
    pass


class EmptyRequest(AutotarificationError):
    pass


class GeodataError(AutotarificationError):
    pass


class NoGeodataError(GeodataError):
    pass


class GeodataVerificationFailed(GeodataError):
    pass


class AutotarificationForbidden(AutotarificationError, PermissionDenied):
    pass


class OutOfBounds(AutotarificationError):
    pass


class ServiceNotFound(AutotarificationError):
    pass


MOSCOW_METRO_LINES = {
    'Арбатско-Покровская': '3',
    'Белорусско-Савеловский': 'D1',
    'Большая кольцевая линия': '11',
    'Бутовская': '12',
    'Замоскворецкая': '2',
    'Калининская': '8',
    'Калужско-Рижская': '6',
    'Каховская': '11A',
    'Кольцевая': '5',
    'Курско-Рижский': 'D2',
    'Люблинско-Дмитровская': '10',
    'МЦК': '14',
    'Монорельс': '13',
    'Некрасовская': '15',
    'Серпуховско-Тимирязевская': '9',
    'Сокольническая': '1',
    'Солнцевская': '8A',
    'Таганско-Краснопресненская': '7',
    'Филёвская': '4',
}

SPB_METRO_LINES = {
    'Кировско-Выборгская': '1',
    'Московско-Петроградская': '2',
    'Невско-Василеостровская': '3',
    'Правобережная': '4',
    'Фрунзенско-Приморская': '5',
}


METRO_LINES = {
    # Москва
    'RU-MOS': MOSCOW_METRO_LINES,
    # МО
    'RU-MOW': MOSCOW_METRO_LINES,
    # Санкт-Петербург
    'RU-SPE': SPB_METRO_LINES,
    # Ленинградская область
    'RU-LEN': SPB_METRO_LINES,
    # Самара
    'RU-SAM': {
        'Первая': '1',
    },
    # Нижний Новгород
    'RU-NIZ': {
        'Автозаводская': '1',
        'Сормовско-Мещерская': '2',
    }
}


_BANNED_LINES = {
    'Белорусско-Савеловский',
    'Курско-Рижский',
}


def _validate_coordinate_pair(
        normalized: Optional[str],
        google_data: Optional[str]
) -> Tuple[Tuple[str, str], bool]:

    if not normalized:
        raise NoGeodataError('No normalized geodata record.')
    if not google_data:
        # Todo: GT-1074
        pass
#        raise NoGeodataError('No google geodata record.')

    try:
        normalized = json.loads(normalized)[0]
        lat = normalized['geo_lat']
        lon = normalized['geo_lon']
    except (json.JSONDecodeError, KeyError):
        raise NoGeodataError('Missing normalized geodata.')
    if lat is None or lon is None:
        raise NoGeodataError('No normalized coordinates.')

        # Todo: GT-1074
#    try:
#        google_data = json.loads(google_data)
#    except json.JSONDecodeError:
#        raise NoGeodataError('Missing google geodata.')
#    if not google_data:
#        raise NoGeodataError('No google coordinates.')
#
#    dst = min(
#        geo_utils.distance(
#            lon,
#            lat,
#            g_address['geometry']['location']['lng'],
#            g_address['geometry']['location']['lat']
#        )
#        for g_address in google_data
#    )
#
#    _MAX_ADDRESS_PARSERS_DIFF = 1000  # metres
    _MAX_DISTANCE_FROM_STATION = 2  # km

    # Todo: GT-1074
#    if dst > _MAX_ADDRESS_PARSERS_DIFF:
#        raise GeodataVerificationFailed(
#            f'Distance {dst} exceeds allowed max discrepancy {_MAX_ADDRESS_PARSERS_DIFF}.'
#        )

    in_moscow = (
        normalized['beltway_hit'] == 'IN_MKAD' or
        any(
            (
                info['line'] in MOSCOW_METRO_LINES and
                info['line'] not in _BANNED_LINES and
                info['distance'] <= _MAX_DISTANCE_FROM_STATION
            )
            for info in normalized['metro'] or []
        )
    )

    return (lat, lon), in_moscow


def _get_item_coordinates(request_id: int) -> Tuple[List[Tuple[str, str]], Optional[bool], int]:

    item_geodata = DeliveryItem.objects.filter(
        request=request_id
    ).filter(
        workers_required__gt=0
    ).annotate(
        normalized=Subquery(
            NormalizedAddress.objects.filter(
                location=OuterRef('pk'),
                version=OuterRef('address_version'),
            ).values(
                'raw_data'
            ),
            output_field=CharField()
        ),
        google=Subquery(
            GoogleMapsAddress.objects.filter(
                location=OuterRef('pk'),
                version=OuterRef('address_version')
            ).values(
                'raw_data'
            ),
            output_field=CharField()
        )
    ).values_list(
        'normalized',
        'google',
    )

    def _catch(func):
        def wrapper(*a, **kw):
            try:
                return func(*a, **kw)
            except GeodataError:
                return None
        return wrapper

    validated = tuple(zip(*(
        filter(
            lambda pair: pair is not None,
            (
                _catch(_validate_coordinate_pair)(normalized, google_data)
                for normalized, google_data in item_geodata
            )
        )
    )))

    items_count = item_geodata.count()

    try:
        item_coordinates, in_moscow = validated
    except ValueError:
        return [], None, items_count

    return item_coordinates, all(in_moscow), items_count


MAX_DISTANCE_TO_ZONE = math.inf

ZONE_BELTS = [
    (0, ''),
    (15_000, '_15'),
    (30_000, '_30'),
    (45_000, '_45'),
    (60_000, '_60'),
    (MAX_DISTANCE_TO_ZONE, '_60+'),
]


CoordinateType = Union[str, float, int, Decimal]


def _get_delivery_zone(
        coordinates: List[Tuple[CoordinateType, CoordinateType]],
        in_moscow: bool
) -> str:

    try:
        zone, dst = geo_utils.max_distance_to_zone(coordinates)
    except geo_utils.GeoUtilError as e:
        raise AutotarificationError from e

    if zone == 'msk' and in_moscow:
        return 'msk'
    try:
        zone += next(suffix for radius, suffix in ZONE_BELTS if dst <= radius)
    except StopIteration:
        raise OutOfBounds(
            f'Расстояние {dst} до зоны {zone}'
            f' превышает максимально допустимое ({MAX_DISTANCE_TO_ZONE}).'
        ) from None

    return zone


def get_tariff_for_zone(
        customer_id: int,
        zone: str,
        is_route: bool = False
) -> DeliveryService:
    service = DeliveryService.objects.filter(
        zone=zone,
        service__customer=customer_id,
    ).order_by(
        '-pk',
    ).first()
    if service is None:
        raise ServiceNotFound
    return service


def get_default_tariff(customer_id: int, zone: str, is_route: bool):
    zone_center = DeliveryZone.objects.values_list(
        'group__code',
        flat=True
    ).get(
        code=zone
    )
    return get_tariff_for_zone(
        customer_id,
        zone_center,
        is_route
    )


# Todo: it is obvious that it needs to be refactored
def try_to_update_tariff(
        delivery_request: DeliveryRequest,
        author: User,
        force_commit: bool = True,
) -> Tuple[List[str], bool]:

    _FIRST_ALLOWED_DAY = datetime.date(year=2021, month=4, day=3)

    if delivery_request.date < _FIRST_ALLOWED_DAY:
        raise AutotarificationForbidden(
            f'Невозможно автотарифицировать заявку '
            f'старше {_FIRST_ALLOWED_DAY.strftime(date_time.DATE_FORMAT)}.'
        )

    coordinates, in_moscow, items_count = _get_item_coordinates(delivery_request.pk)

    try:
        if not coordinates:
            raise AutotarificationError(
                'В заявке нет активных адресов с валидными координатами.'
            )
        zone = _get_delivery_zone(coordinates, in_moscow)

    except AutotarificationError as e:
        if delivery_request.active_workers().exists():
            if items_count == 0:
                raise DeliveryWorkflowError(
                    'В заявке нет активных адресов, но есть активные работники.'
                ) from e
            if delivery_request.delivery_service is None:
                raise DeliveryWorkflowError(
                    'В заявке нет тарифа, но есть активные работники.'
                ) from e

            zone = DeliveryZone.objects.values_list(
                'group__code',
                flat=True
            ).get(
                code=delivery_request.delivery_service.zone
            )

        else:
            delivery_request.delivery_service = None
            delivery_request.save(update_fields=['delivery_service'], user=author)
            return [], False

    service = get_tariff_for_zone(
        cast(int, delivery_request.customer_id),
        zone,
        is_route=items_count > 1
    )

    prev_bonus = get_delivery_request_bonus(delivery_request)

    delivery_request.delivery_service = service

    location_changed = False
    location = customer_location(delivery_request.customer_id, zone)

    if location != delivery_request.location:
        ensure_can_save_timesheet(delivery_request)
        delivery_request.location = location
        ensure_can_save_timesheet(delivery_request, check_if_can_create_reconciliation=True)

    delivery_request.save(user=author)
    if location_changed:
        update_request_timesheets(delivery_request)

    return update_turnouts(delivery_request, author, prev_bonus, force_commit)


def estimate_request_price_for_customer(
        customer_id: int,
        num_workers: int,
        hours: Decimal,
        date: datetime.date,
        timepoint: datetime.time,
        coordinates: List[Tuple[Decimal, Decimal]],
        in_moscow=False,
) -> Decimal:

    zone = _get_delivery_zone(coordinates, in_moscow=in_moscow)
    service = get_tariff_for_zone(customer_id, zone, is_route=len(coordinates) > 1)
    labor_units = sum(calculate_delivery_request_hours(
        service.hours,
        service.travel_hours,
        timepoint,
        hours
    ))
    price = estimate_customer_price(
        date,
        service.service_id,
        labor_units,
    )
    return price * num_workers


def _update_tariff(delivery_request_pk, user):
    with transaction.atomic():
        delivery_request = DeliveryRequest.objects.select_for_update().get(
            pk=delivery_request_pk
        )
        update_delivery_request_status(delivery_request, user=user)
        if delivery_request.status == DeliveryRequest.AUTOTARIFICATION:
            return delivery_request.delivery_service, [], False
        return (
            delivery_request.delivery_service,
            *try_to_update_tariff(delivery_request, user)
        )


@log
def do_normalize_address_update_tariff(delivery_item_pk, version, user):
    """
    !!! Should be a part of a huey task (see tasks.py)
    """
    with transaction.atomic():
        delivery_item = DeliveryItem.objects.select_for_update().get(pk=delivery_item_pk)
        if delivery_item.address_version != version:
            return
    _normalize_address(delivery_item, version)
    return _update_tariff(delivery_item.request_id, user)


@log
def do_normalize_address_in_bulk(delivery_item_pks, request_pk, version, user):
    """
    !!! Should be a part of a huey task (see tasks.py)
    """
    with transaction.atomic():
        DeliveryRequest.objects.select_for_update().get(pk=request_pk)
        delivery_items = DeliveryItem.objects.filter(
            request_id=request_pk,
            pk__in=delivery_item_pks,
            address_version=version
        )
        if not delivery_items.exists():
            return
    for item in delivery_items:
        _normalize_address(item, version)
    return _update_tariff(request_pk, user)


def _normalize_address(delivery_item, version):
    """
    !!! Should be a part of a huey task (see tasks.py)
    """
    address = delivery_item.address

    try:
        data = [{}]
        try:
            data = dadata.clean_address(address)
        except Exception as e:
            print(e)

        metro = data[0].get('metro')
        if metro is not None:
            metro_line = metro[0]['line']
            station_name = metro[0]['name']
        else:
            metro_line = None
            station_name = None

        NormalizedAddress.objects.create(
            location=delivery_item,
            version=version,
            latitude=data[0].get('geo_lat', 0),
            longitude=data[0].get('geo_lon', 0),
            region=data[0].get('region_iso_code'),
            nearest_metro_line=metro_line,
            nearest_metro_station=station_name,
            raw_data=json.dumps(data)
        )
        # dadata.ru: Максимальная частота запросов — 10 в секунду.
        # dirty and easy way
        time.sleep(0.1)
    except Exception as e:
        print(e)

    try:
        data = googlemaps.geocode(address)
        GoogleMapsAddress.objects.create(
            location=delivery_item,
            version=version,
            raw_data=json.dumps(data)
        )
    except Exception as e:
        print(e)

    update_suspicion_flag(delivery_item)

    suspicious_workers = list(
        start.itemworker.requestworker.worker
        for start in ItemWorkerStart.objects.filter(
            itemworker__item=delivery_item,
            is_suspicious=True,
            itemworker__itemworkerrejection__isnull=True,
            itemworker__requestworker__workerrejection__isnull=True,
        ).select_related(
            'itemworker__requestworker__worker'
        )
    )
    if suspicious_workers:
        notifications.notify_suspicious_address_update(delivery_item, suspicious_workers)
