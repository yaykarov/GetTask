import collections
import datetime
import itertools
import operator
from decimal import (
    Decimal,
    ROUND_CEILING,
)
from typing import (
    Optional,
    cast,
)

import rest_framework_filters as filters
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.contrib.postgres.aggregates import ArrayAgg
from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import ValidationError
from django.db.models import (
    DecimalField,
    Exists,
    F,
    IntegerField,
    JSONField,
    OuterRef,
    Q,
    Subquery,
    TextField,
    Value,
)
from django.db.models.functions import (
    Coalesce,
    JSONObject,
    NullIf,
)
from django.forms import Form
from django.urls import reverse
from django.utils import timezone
from rest_framework.fields import ChoiceField
from rest_framework.serializers import Serializer

from the_redhuman_is.geo_utils import zone_bb_lonlat
from the_redhuman_is.models.delivery import (
    DailyReconciliationConfirmation,
    DeliveryRequest,
    ItemWorker,
    ItemWorkerFinish,
    ItemWorkerFinishConfirmation,
    ItemWorkerStart,
    ItemWorkerStartConfirmation,
    Location,
    LocationZoneGroup,
    RequestWorker,
    RequestWorkerTurnout,
    WorkerZone,
    ZoneGroup,
)
from the_redhuman_is.models.models import (
    CustomerLocation,
    TimeSheet,
)
from the_redhuman_is.models.photo import Photo
from the_redhuman_is.models.turnout_calculators import (
    CalculatorInterval,
    EstimateSumItem,
    EstimateSumRequest,
    PROFIT_FACTOR,
    ServiceCalculator,
    VAT_FACTOR,
    calculate_delivery_request_hours,
    estimate_delivery_request_sum,
)
from the_redhuman_is.models.worker import Worker

from the_redhuman_is.services.delivery.tariffs import METRO_LINES
from the_redhuman_is.services.delivery.utils import (
    ObjectNotFoundError,
    get_user_customer_location,
    is_citizenship_migration_ok,
)
from the_redhuman_is.tasks import log
from the_redhuman_is.views.delivery import DISTANCE_LIMIT

from utils import date_time
from utils.date_time import (
    postgres_str_to_datetime,
    str_to_time,
)
from utils.expressions import PostgresConcatWS
from utils.filter import (
    BooleanFilter,
    CompactChoiceFilter,
    ConsistentOrderingFilter,
    FilterSet,
)
from utils.functools import pairwise
from utils.numbers import ZERO_OO
from utils.phone import (
    format_phone,
    format_phones,
)


class DeliveryRequestBaseFilter(FilterSet):
    first_day = filters.DateFilter(
        field_name='date', lookup_expr='gte', input_formats=[date_time.DATE_FORMAT],
        required=True,
    )
    last_day = filters.DateFilter(
        field_name='date', lookup_expr='lte', input_formats=[date_time.DATE_FORMAT],
        required=True,
    )
    search_text = filters.CharFilter(method='search_text_filter')
    location = CompactChoiceFilter(field_name='location')

    class Meta:
        model = DeliveryRequest
        fields = []

    def search_text_filter(self, queryset, name, value):
        return queryset.filter_by_text(value)


class DeliveryRequestBackofficeFilter(DeliveryRequestBaseFilter):
    zone = CompactChoiceFilter(field_name='location__locationzonegroup__zone_group')
    operator = CompactChoiceFilter(field_name='deliveryrequestoperator__operator')
    customer = CompactChoiceFilter(field_name='customer')
    in_progress = BooleanFilter(method='in_progress_filter')
    can_merge = BooleanFilter(method='can_merge_filter')
    unprofitable = BooleanFilter(method='unprofitable_filter')

    def in_progress_filter(self, queryset, name, value):
        if value is True:
            return queryset.exclude(
                status__in=DeliveryRequest.FINAL_STATUSES
            )
        elif value is False:
            return queryset.filter(
                status__in=DeliveryRequest.FINAL_STATUSES
            )

    def can_merge_filter(self, queryset, name, value):
        if 'arrival_time' not in queryset.query.annotations:
            queryset = queryset.with_arrival_time()
        if 'confirmation_time' not in queryset.query.annotations:
            queryset = queryset.with_confirmation_time()
        queryset = queryset.annotate(
            driver_name_blank=Coalesce('driver_name', Value('', output_field=TextField())),
            driver_phones_blank=Coalesce('driver_phones', Value('', output_field=TextField())),
        ).annotate(
            can_merge=Exists(
                queryset.get_requests_to_merge_subquery()
            )
        )
        if value is True:
            queryset = queryset.filter(
                can_merge=True
            ).exclude(
                status__in=DeliveryRequest.FAIL_STATUSES
            ).exclude(
                driver_name_blank='',
                driver_phones_blank='',
            )
        elif value is False:
            queryset = queryset.filter(
                Q(can_merge=False) |
                Q(status__in=DeliveryRequest.FAIL_STATUSES) |
                Q(
                    driver_name_blank='',
                    driver_phones_blank='',
                )
            )
        return queryset

    def unprofitable_filter(self, queryset, name, value):
        if value is not None:
            queryset = queryset.with_worker_amount()
            if 'customer_amount' not in queryset.query.annotations:
                queryset = queryset.with_customer_amount()

            profit_threshold = F('worker_amount') * Value(VAT_FACTOR) / Value(PROFIT_FACTOR)

            if value is True:
                queryset = queryset.filter(
                    customer_amount__lt=profit_threshold
                )
            else:
                queryset = queryset.filter(
                    customer_amount__gte=profit_threshold
                )
        return queryset


def _get_request_queryset(with_workers=False, with_customer_amount=False):
    fields = [
        'pk',
        'date',
        'driver_name',
        'driver_phones',
        'route',
        'status',
        'status_description',
        'timestamp',
        'confirmed_timepoint',
        'comment',
        'location_id',
        'location__location_name',
        'operator',
        'worker_count',
        'worker_confirmed_count',
        'author_id',
        'author__first_name',
        'author__username',
        'customer_id',
        'customer__cust_name',
        'delivery_service_id',
        'delivery_service__operator_service_name',
        'customer_resolution',
        'is_overdue',
        'has_self_assigned_worker',
        'is_private',
        'extra_photos_exist',
        'confirmation_time',
        'arrival_time',
        'new_start_photo_count',
        'new_finish_photo_count',
        'hours',
        'items',
        'delivery_service__hours',
        'delivery_service__travel_hours',
        'delivery_service__zone',
    ]
    request_qs = DeliveryRequest.objects.all(
    ).with_operator(
    ).with_worker_count(
    ).with_worker_count(
        confirmed=True
    ).with_customer_resolution(
    ).with_is_overdue(
    ).with_has_self_assigned_worker(
    ).with_is_private(
    ).with_extra_photos_exist(
    ).with_confirmation_time(
    ).with_arrival_time(
    ).with_new_start_photo_count(
    ).with_new_finish_photo_count(
    ).with_items_for_backoffice(
        with_workers=with_workers
    ).with_hours(
    )

    if with_customer_amount:
        request_qs = request_qs.with_customer_amount()
        fields.append('customer_amount')

    return request_qs.values(
        *fields
    ).order_by(
        '-pk'
    )


def _lateness_label(fact, plan, reserve_timedelta=datetime.timedelta(seconds=0)):
    if plan is None:
        return None
    if (fact + reserve_timedelta) > plan:
        return {
            'label': date_time.time_interval_format(fact - plan),
            'value': (fact - plan).total_seconds(),
        }
    else:
        return None


def _delete_tariff_fields(request):
    # delete fields required for pay estimates
    del request['delivery_service__hours']
    del request['delivery_service__travel_hours']
    del request['delivery_service__zone']


def _is_timepoint_ok(request):
    workers = collections.defaultdict(bool)
    max_understaffed = max(
        (item['workers_required'] - len(item['assigned_workers']) for item in request['items']),
        default=None
    )
    if max_understaffed is None:
        understaffed_ok = True
    else:
        understaffed_ok = any(
            item['confirmed_timepoint'] is not None
            for item in request['items']
            if item['workers_required'] - len(item['assigned_workers']) == max_understaffed
        )

    for item in request['items']:
        for worker in item['assigned_workers']:
            workers[worker['id']] |= item['confirmed_timepoint'] is not None

    return all(workers.values()) and understaffed_ok


def _calculate_item_lateness(request):
    if request['status'] in DeliveryRequest.CANCELLED_STATUSES:
        for item in request['items']:
            item['lateness'] = None
    else:
        timepoints = {}
        first_items = {}
        for item in request['items']:
            timepoints[item['id']] = item['confirmed_timepoint']
            if item['confirmed_timepoint'] is None:
                continue
            for worker in item['assigned_workers']:
                if (
                        worker['id'] not in first_items or
                        timepoints[first_items[worker['id']]] > item['confirmed_timepoint']
                ):
                    first_items[worker['id']] = item['id']
        for item in request['items']:
            if item['confirmed_timepoint'] is None:
                item['lateness'] = None
                continue
            try:
                latest_arrival = max(
                    worker['start']
                    for worker in item['assigned_workers']
                    if first_items[worker['id']] == item['id']
                )
            except ValueError:  # not a first address for anyone
                item['lateness'] = None
                continue
            except TypeError:  # at least one didn't arrive
                latest_arrival = timezone.localtime()
            else:
                if latest_arrival is None:
                    latest_arrival = timezone.localtime()
                else:
                    latest_arrival = postgres_str_to_datetime(cast(str, latest_arrival))
            item['lateness'] = _lateness_label(
                latest_arrival,
                timezone.make_aware(
                    datetime.datetime.combine(
                        request['date'],
                        str_to_time(item['confirmed_timepoint'])
                    )
                )
            )
    for item in request['items']:
        for worker in item['assigned_workers']:
            del worker['start']


def _delivery_request_format_in_place(request):
    username = request.pop('author__username')
    request['author'] = {
        'id': request.pop('author_id'),
        'name': request.pop('author__first_name') or username,
    }
    request['customer'] = {
        'id': request.pop('customer_id'),
        'name': request.pop('customer__cust_name'),
    }
    if request['delivery_service_id'] is not None:
        request['service'] = {
            'id': request.pop('delivery_service_id'),
            'name': request.pop('delivery_service__operator_service_name'),
        }
    else:
        del request['delivery_service_id']
        del request['delivery_service__operator_service_name']
        request['service'] = None

    if request['location_id'] is not None:
        request['location'] = {
            'id': request.pop('location_id'),
            'name': request.pop('location__location_name'),
        }
    else:
        del request['location_id']
        del request['location__location_name']
        request['location'] = None

    request['new_photo_count'] = (
        request.pop('new_start_photo_count') +
        request.pop('new_finish_photo_count')
    )

    if request['comment'] == '':
        request['comment'] = None

    for item in request['items']:
        metro = item['metro']
        if metro is not None:
            try:
                metro['line'] = METRO_LINES[metro['region']][metro['line']]
            except KeyError:
                metro['line'] = 0

    request['pay_estimate'] = _estimate_sum(
        request,
        {
            item['id']
            for item in request['items']
            if item['workers_required'] > 0
        }
    )
    request['timepoint_ok'] = _is_timepoint_ok(request)
    _calculate_item_lateness(request)

    request['driver_phones'] = format_phones(request['driver_phones'])


def get_delivery_request_list(user, filter_args):
    request_qs = _get_request_queryset(
        with_workers=True,
        with_customer_amount=user.is_superuser
    )
    if not user.is_superuser:
        request_qs = request_qs.exclude(status=DeliveryRequest.REMOVED)

    requests = list(DeliveryRequestBackofficeFilter(filter_args, queryset=request_qs).qs)
    for request in requests:
        _delivery_request_format_in_place(request)
        _delete_tariff_fields(request)
        del request['confirmed_timepoint']

    if 'unprofitable' in filter_args:
        fields_to_delete = ['worker_amount']
        if not user.is_superuser:
            fields_to_delete.append('customer_amount')
        for request in requests:
            for field_name in fields_to_delete:
                del request[field_name]

    return {
        'data': requests,
    }


def _get_photo_queryset(base_pks, base_model):
    return Photo.objects.filter(
        content_type=ContentType.objects.get_for_model(base_model),
        object_id__in=base_pks,
    ).order_by(
        'object_id'
    ).values(
        'id',
        'object_id',
        'image',
        'photorejectioncomment__rejection_comment',
    )


def _serialize_request_photos(photos):
    res = {}
    for object_id, group in itertools.groupby(photos, key=operator.itemgetter('object_id')):
        photos_for_object = []
        for e in group:
            photo = {
                'id': e['id'],
                'url': e['image'],
                'rejected': e['photorejectioncomment__rejection_comment']
            }
            photos_for_object.append(photo)
        res[object_id] = photos_for_object
    return res


def _get_itemworker_photos(item_workers):
    photos = []

    for model_class in (ItemWorkerStart, ItemWorkerFinish):
        ids = [
            iw[model_class._meta.model_name] for iw in item_workers
            if iw[model_class._meta.model_name] is not None
        ]
        photo_qs = _get_photo_queryset(ids, model_class)
        photos.append(
            _serialize_request_photos(photo_qs)
        )

    return photos


def _get_requestworker_queryset(request_id):
    return RequestWorker.objects.with_full_name(
    ).filter(
        request=request_id,
        workerrejection__isnull=True,
    ).values(
        'worker_id',
        'full_name',
        'worker__tel_number',
        'workerconfirmation__timestamp',
        'requestworkerturnout__workerturnout__hours_worked',
        'requestworkerturnout__workerturnout__turnoutoperationtopay__operation_id',
        'requestworkerturnout__workerturnout__turnoutoperationtopay__operation__amount',
    )


def _estimate_sum(request, only_these_items=None):
    if request['delivery_service__hours'] is None:
        return None

    if only_these_items is not None:
        if not only_these_items:
            return ZERO_OO
        items = [item for item in request['items'] if item['id'] in only_these_items]
    else:
        items = request['items']

    request_data = EstimateSumRequest(
        hours=sum(calculate_delivery_request_hours(
            request['delivery_service__hours'],
            request['delivery_service__travel_hours'],
            request['confirmed_timepoint'],
        )),
        zone=request['delivery_service__zone'],
        status=request['status'],
        date=request['date'],
        items=[
            EstimateSumItem(
                mass=item['mass'],
                has_elevator=item['has_elevator'],
                floor=item['floor'],
                carrying_distance=item['carrying_distance'],
            )
            for item in items
        ]
    )
    return estimate_delivery_request_sum(request_data)


def _get_hour_bonus(request):
    return sum(calculate_delivery_request_hours(
        request['delivery_service__hours'],
        request['delivery_service__travel_hours'],
        request['confirmed_timepoint'],
    )[1:])


def _worker_format_in_place(worker, request, item_worker_data):
    item_assignments = {
        item_id for item_id, item_data in item_worker_data.items()
        if (
            worker['worker_id'] in item_data and
            item_data[worker['worker_id']]['status'] >= ItemWorker.NEW
        )
    }

    worker['id'] = worker.pop('worker_id')
    worker['name'] = worker.pop('full_name')
    worker['phone'] = format_phone(worker.pop('worker__tel_number'))
    worker['confirmation_timestamp'] = worker.pop(
        'workerconfirmation__timestamp'
    )
    worker['total_hours'] = worker.pop('requestworkerturnout__workerturnout__hours_worked')
    if worker['total_hours'] is None or request['delivery_service__hours'] is None:
        worker['work_hours'] = None
    else:
        worker['work_hours'] = worker['total_hours'] - _get_hour_bonus(request)
    worker['operation_id'] = worker.pop(
        'requestworkerturnout__workerturnout__turnoutoperationtopay__operation_id'
    )
    if worker['operation_id'] is not None:
        worker['amount'] = worker.pop(
            'requestworkerturnout__workerturnout__turnoutoperationtopay__operation__amount'
        )
    else:
        # todo GT-807 to ensure request with workers has a service
        if request['delivery_service__hours'] is None:
            worker['amount'] = None
        else:
            worker['amount'] = _estimate_sum(
                request,
                only_these_items=item_assignments
            )
        del worker[
            'requestworkerturnout__workerturnout__turnoutoperationtopay__operation__amount'
        ]

    request['driver_phones'] = format_phones(request['driver_phones'])

    first_worker_item = min(
        (
            item
            for item in request['items']
            if item['id'] in item_assignments and item['confirmed_timepoint'] is not None
        ),
        key=operator.itemgetter('confirmed_timepoint'),
        default=None,
    )
    if first_worker_item is None:
        worker['confirmed_timepoint'] = None
        worker['lateness'] = None
    else:
        worker['confirmed_timepoint'] = first_worker_item['confirmed_timepoint']
        worker['lateness'] = _lateness_label(
            timezone.make_aware(
                datetime.datetime.combine(
                    request['date'],
                    datetime.datetime.strptime(worker['confirmed_timepoint'], '%H:%M:%S').time()
                )
            ),
            item_worker_data[first_worker_item['id']][worker['id']]['start']
        )


def _get_itemworker_queryset(request_id):
    return ItemWorker.objects.filter(
        item__request=request_id
    ).with_status(
    ).filter(
        requestworker__workerrejection__isnull=True
    ).order_by(
        'item_id',
        'requestworker__worker_id',
    ).values(
        'id',
        'item_id',
        'requestworker__worker_id',
        'itemworkerstart',
        'itemworkerstart__timestamp',
        'itemworkerstart__itemworkerstartconfirmation__timestamp',
        'itemworkerfinish',
        'itemworkerfinish__timestamp',
        'itemworkerfinish__itemworkerfinishconfirmation__timestamp',
        'status',
    )


def _collate_itemworker_data_table(item_workers, photos=None):
    item_worker_data = {}
    for item_id, per_item_group in itertools.groupby(
            item_workers,
            key=operator.itemgetter('item_id')
    ):
        item_data = {}
        for item_worker in per_item_group:
            worker_id = item_worker['requestworker__worker_id']
            worker_data = {
                'status': item_worker['status'],
                'start': item_worker['itemworkerstart__timestamp'],
                'start_confirmed': item_worker[
                    'itemworkerstart__itemworkerstartconfirmation__timestamp'
                ],
                'finish': item_worker['itemworkerfinish__timestamp'],
                'finish_confirmed': item_worker[
                    'itemworkerfinish__itemworkerfinishconfirmation__timestamp'
                ]
            }
            if photos:
                worker_data['start_photos'] = photos[0].get(
                    item_worker['itemworkerstart']
                )
                worker_data['finish_photos'] = photos[1].get(
                    item_worker['itemworkerfinish']
                )
            item_data[worker_id] = worker_data

        item_worker_data[item_id] = item_data

    return item_worker_data


def get_delivery_request_detail(request_id, user, with_photos=False):
    try:
        request = _get_request_queryset(
            with_workers=True,
            with_customer_amount=user.is_superuser,
        ).get(
            pk=request_id
        )
    except DeliveryRequest.DoesNotExist:
        raise ObjectNotFoundError(f'Заявка {request_id} не найдена.')
    _delivery_request_format_in_place(request)

    item_workers = list(
        _get_itemworker_queryset(request_id)
    )
    if with_photos:
        photos = _get_itemworker_photos(item_workers)
    else:
        photos = None
    item_worker_cell_data = _collate_itemworker_data_table(item_workers, photos)

    workers = list(
        _get_requestworker_queryset(request_id)
    )

    for worker in workers:
        _worker_format_in_place(worker, request, item_worker_cell_data)

    understaffed = collections.defaultdict(list)
    timepoints = {}
    for item in request['items']:
        if (diff := item['workers_required'] - len(item['assigned_workers'])) > 0:
            understaffed[diff].append(item['id'])
            if item['confirmed_timepoint'] is not None:
                if diff not in timepoints or timepoints[diff] > item['confirmed_timepoint']:
                    timepoints[diff] = item['confirmed_timepoint']

    if understaffed:
        best_timepoint = None
        understaffed_counts = sorted(understaffed.keys())

        for diff in reversed(understaffed_counts):
            if diff not in timepoints:
                timepoints[diff] = best_timepoint
            elif best_timepoint is None:
                best_timepoint = timepoints[diff]
            elif timepoints[diff] > best_timepoint:
                timepoints[diff] = best_timepoint
            else:
                best_timepoint = timepoints[diff]

        for prev, diff in pairwise(
                itertools.chain((0,), understaffed_counts)
        ):
            for virtual_worker_pk in range(prev + 1, diff + 1):
                workers.append({
                    'id': -virtual_worker_pk,
                    'confirmed_timepoint': timepoints[diff]
                })

        for diff, items in understaffed.items():
            for item_id in items:
                if item_id not in item_worker_cell_data:
                    item_worker_cell_data[item_id] = {}
                for virtual_worker_pk in range(1, diff + 1):
                    item_worker_cell_data[item_id][-virtual_worker_pk] = None

    _delete_tariff_fields(request)
    del request['confirmed_timepoint']

    return {
        'request': request,
        'workers': workers,
        'item_workers': item_worker_cell_data,
    }


def _get_min_travel_hours(row):
    if (
            row['itemworker__requestworker__request__delivery_service__hours'] is None or
            row['itemworker__requestworker__request__delivery_service__travel_hours'] is None
    ):
        min_hours = None
        travel_hours = None
    else:
        travel_hours = row['itemworker__requestworker__request__delivery_service__travel_hours']
        min_hours = (
                row['itemworker__requestworker__request__delivery_service__hours'] -
                travel_hours
        )
    return min_hours, travel_hours


def _serialize_photo_confirmation(row):
    min_hours, travel_hours = _get_min_travel_hours(row)

    for photo in row['photos']:
        if photo['rejected']['author'] is None:
            photo['rejected'] = None
        photo['timestamp'] = postgres_str_to_datetime(photo['timestamp'])

    return {
        'request': {
            'id': row['itemworker__requestworker__request'],
            'date': row['itemworker__requestworker__request__date'],
            'min_hours': min_hours,
            'travel_hours': travel_hours,
        },
        'item': {
            'id': row['itemworker__item'],
            'address': row['itemworker__item__address'],
            'code': row['itemworker__item__code'],
        },
        'worker': {
            'id': row['itemworker__requestworker__worker'],
            'name': row['worker_name'],
        },
        'photos': row['photos'],
        'timestamp': row['timestamp'],
        'confirmed': row['confirmed'],
    }


def _serialize_start_photo_confirmation(row):
    res = _serialize_photo_confirmation(row)
    res['is_suspicious'] = row['is_suspicious']
    if row['itemworkerdiscrepancycheck'] is None:
        res['discrepancy_check'] = None
    else:
        res['discrepancy_check'] = {
            'is_ok': row['itemworkerdiscrepancycheck__is_ok'],
            'comment': row['itemworkerdiscrepancycheck__comment'],
        }
    return res


def _serialize_finish_photo_confirmation(row):
    res = _serialize_photo_confirmation(row)

    main_photo_id = row['photo_id']
    if main_photo_id is not None:
        try:
            main_photo = next(
                photo
                for photo in res['photos']
                if photo['id'] == main_photo_id
            )
            main_photo['main'] = True
        except StopIteration:
            res['photos'].append({
                'id': main_photo_id,
                'url': row['photo__image'],
                'rejected': None,
                'timestamp': row['photo__timestamp'],
                'main': True,
            })
            res['photos'].sort(key=operator.itemgetter('timestamp'))

    return res


class PhotoFilterForm(Form):
    def clean(self):
        cleaned_data = super(PhotoFilterForm, self).clean()
        for key, value in list(cleaned_data.items()):
            if value is None:
                del cleaned_data[key]
        submitted_fields = cleaned_data.keys() | self.errors.keys()
        if not (
            submitted_fields.issuperset({'first_day', 'last_day'}) or
            'request' in submitted_fields
        ):
            raise ValidationError(
                "В запросе должна использоваться или пара фильтров first_day, last_day,"
                " или фильтр request."
            )
        return cleaned_data


class ItemWorkerStartPhotoFilter(FilterSet):
    first_day = filters.DateFilter(
        field_name='itemworker__requestworker__request__date', lookup_expr='gte',
        input_formats=[date_time.DATE_FORMAT],
    )
    last_day = filters.DateFilter(
        field_name='itemworker__requestworker__request__date', lookup_expr='lte',
        input_formats=[date_time.DATE_FORMAT],
    )
    worker = CompactChoiceFilter(field_name='itemworker__requestworker__worker')
    request = CompactChoiceFilter(field_name='itemworker__requestworker__request')
    confirmed = BooleanFilter(field_name='confirmed')

    class Meta:
        model = ItemWorkerStart
        fields = []
        form = PhotoFilterForm


class ItemWorkerFinishPhotoFilter(ItemWorkerStartPhotoFilter):
    class Meta:
        model = ItemWorkerFinish
        fields = []


def get_photo_annotation(model):
    # model is one of ItemWorkerStart, ItemWorkerFinish
    return Coalesce(
        Subquery(
            Photo.objects.filter(
                content_type=ContentType.objects.get_for_model(model),
                object_id=OuterRef('pk')
            ).annotate(
                obj=JSONObject(
                    id='id',
                    url='image',
                    rejected=JSONObject(
                        author=Coalesce(
                            NullIf('photorejectioncomment__author__first_name', Value('')),
                            'photorejectioncomment__author__username'
                        ),
                        timestamp='photorejectioncomment__timestamp',
                        text='photorejectioncomment__rejection_comment',
                    ),
                    timestamp='timestamp',
                )
            ).order_by(
            ).values(
                'object_id'
            ).annotate(
                list=ArrayAgg(
                    'obj',
                    ordering=('timestamp',)
                )
            ).values(
                'list'
            ),
            output_field=ArrayField(JSONField())
        ),
        []
    )


class PhotoConfirmationQuerySerializer(Serializer):
    photo_type = ChoiceField(choices=['start', 'finish'], allow_blank=True, default='')


def get_delivery_photo_queryset(model):
    worker_name_annotation = PostgresConcatWS(
        Value(' '),
        F('itemworker__requestworker__worker__last_name'),
        F('itemworker__requestworker__worker__name'),
        NullIf(F('itemworker__requestworker__worker__patronymic'), Value(''))
    )

    fields = [
        'itemworker__item',
        'itemworker__requestworker__request',
        'itemworker__requestworker__worker',
        'photos',
        'worker_name',
        'itemworker__requestworker__request__date',
        'itemworker__item__address',
        'itemworker__item__code',
        'timestamp',
        'confirmed',
        'itemworker__requestworker__request__delivery_service__hours',
        'itemworker__requestworker__request__delivery_service__travel_hours',
    ]

    if model == ItemWorkerStart:
        confirmation_sq = ItemWorkerStartConfirmation.objects.filter(
            itemworkerstart=OuterRef('pk')
        )
        fields.extend([
            'is_suspicious',
            'itemworkerdiscrepancycheck',
            'itemworkerdiscrepancycheck__is_ok',
            'itemworkerdiscrepancycheck__comment',

        ])
    elif model == ItemWorkerFinish:
        confirmation_sq = ItemWorkerFinishConfirmation.objects.filter(
            itemworkerfinish=OuterRef('pk')
        )
        fields.extend([
            'photo_id',
            'photo__image',
            'photo__timestamp',
        ])
    else:
        raise NotImplementedError

    return model.objects.all(
    ).annotate(
        photos=get_photo_annotation(model),
        worker_name=worker_name_annotation,
        confirmed=Exists(
            confirmation_sq
        ),
    ).order_by(
        'timestamp',
    ).values(
        *fields
    )


def get_delivery_photo_confirmation_list(filter_args):
    serializer = PhotoConfirmationQuerySerializer(data=filter_args)
    serializer.is_valid(raise_exception=True)
    photo_type = serializer.validated_data['photo_type']
    result = {}

    if photo_type != 'finish':
        itemworkerstart_qs = ItemWorkerStartPhotoFilter(
            filter_args,
            queryset=get_delivery_photo_queryset(ItemWorkerStart)
        ).qs

        result['start'] = [
            _serialize_start_photo_confirmation(row)
            for row in itemworkerstart_qs
        ]

    if photo_type != 'start':
        itemworkerfinish_qs = ItemWorkerFinishPhotoFilter(
            filter_args,
            queryset=get_delivery_photo_queryset(ItemWorkerFinish)
        ).qs

        result['finish'] = [
            _serialize_finish_photo_confirmation(row)
            for row in itemworkerfinish_qs
        ]

    return result


_ITEMWORKER_PHOTO_MODEL_CLASSES = {
    'start': ItemWorkerStart,
    'finish': ItemWorkerFinish,
}
_serialize_event_photo_confirmation = {
    'start': _serialize_start_photo_confirmation,
    'finish': _serialize_finish_photo_confirmation,
}


# Todo: this needs a better name
def get_delivery_photo_confirmation_detail(photo_type, item_id, worker_id):
    try:
        return _serialize_event_photo_confirmation[photo_type](
            get_delivery_photo_queryset(
                _ITEMWORKER_PHOTO_MODEL_CLASSES[photo_type]
            ).get(
                itemworker__item=item_id,
                itemworker__requestworker__worker=worker_id
            )
        )
    except (ItemWorkerStart.DoesNotExist, ItemWorkerFinish.DoesNotExist):
        raise ObjectNotFoundError(f'Отметка {item_id}|{worker_id} не найдена.')


def get_extra_photos(request_id):
    if not DeliveryRequest.objects.filter(pk=request_id).exists():
        raise ObjectNotFoundError(f'Заявка {request_id} не найдена.')
    photos = list(
        Photo.objects.filter(
            content_type=ContentType.objects.get_for_model(DeliveryRequest),
            object_id=request_id,
        ).values(
            'id',
            'timestamp',
            'image',
        ).order_by(
            'timestamp',
            'pk',
        )
    )
    for photo in photos:
        photo['url'] = photo.pop('image')
    return photos


def _get_zone_map_data(zone_code):
    (min_lon, min_lat), (max_lon, max_lat), city_lon_lat = zone_bb_lonlat(zone_code)
    city_lat_lon = [[lat, lon] for (lon, lat) in city_lon_lat]
    bounding_box = {
        'min_longitude': min_lon,
        'min_latitude': min_lat,
        'max_longitude': max_lon,
        'max_latitude': max_lat,
    }
    return city_lat_lon, bounding_box


def _map_request_format_in_place(request):
    request['driver_last_name'] = (request['driver_name'] or '').split(' ')[0]
    request['driver_full_name'] = request.pop('driver_name')
    request['expiring'] = request.pop('is_expiring')
    if request['confirmed_timepoint'] is not None:
        request['confirmed_timepoint'] = request['confirmed_timepoint'].strftime(
            date_time.TIME_FORMAT
        )
    for item in request['items']:
        item['location'] = item.pop('geotag_')


def _map_worker_format_in_place(worker):
    worker['phone'] = format_phone(worker.pop('tel_number'))
    worker['location'] = {
        'latitude': worker.pop('lastlocation__location__latitude'),
        'longitude': worker.pop('lastlocation__location__longitude'),
        'timestamp': worker.pop('lastlocation__location__timestamp'),
    }


def get_requests_on_map_querysets(
        date,
        user,
        zone_id=None,
        location_id=None,
        with_zone_code=False,
):
    user_customer, user_location = get_user_customer_location(user)

    request_qs = DeliveryRequest.objects.filter(
        date=date,
    ).exclude(
        status__in=DeliveryRequest.FINAL_STATUSES
    ).with_is_expiring(
        datetime.timedelta(minutes=15),
    ).with_is_worker_assignment_delayed(
    ).with_items_for_map(
    )

    requestworker_sq = RequestWorker.objects.filter(
        request__date=date,
        workerrejection__isnull=True,
    ).exclude(
        request__status__in=DeliveryRequest.FINAL_STATUSES,
    )

    if user_customer is not None:
        request_qs = request_qs.filter(
            customer=user_customer,
        )
        requestworker_sq = requestworker_sq.filter(
            request__customer=user_customer,
        )

    location_filter_arg = user_location or location_id
    zone_code = None

    if zone_id is not None:
        request_qs = request_qs.filter(
            location__locationzonegroup__zone_group=zone_id
        )
        requestworker_sq = requestworker_sq.filter(
            request__location__locationzonegroup__zone_group=zone_id
        )
        if with_zone_code:
            try:
                zone_code = ZoneGroup.objects.values_list(
                    'code',
                    flat=True
                ).get(
                    pk=zone_id,
                )
            except ZoneGroup.DoesNotExist:
                pass

    if location_filter_arg is not None:
        request_qs = request_qs.filter(
            location=location_filter_arg
        )
        requestworker_sq = requestworker_sq.filter(
            request__location=location_filter_arg
        )
        if with_zone_code:
            try:
                zone_code = LocationZoneGroup.objects.values_list(
                    'zone_group__code',
                    flat=True
                ).get(
                    location=location_filter_arg,
                )
            except (LocationZoneGroup.DoesNotExist, LocationZoneGroup.MultipleObjectsReturned):
                pass

    worker_qs = Worker.objects.annotate(
        has_requests=Exists(
            requestworker_sq.filter(
                worker=OuterRef('pk')
            )
        )
    ).annotate(
        requests=Subquery(
            requestworker_sq.filter(
                worker=OuterRef('pk')
            ).values(
                'worker'
            ).annotate(
                requests_list=ArrayAgg(
                    'request_id',
                    ordering=(
                        'request_id',
                    )
                )
            ).values(
                'requests_list'
            ),
            output_field=ArrayField(IntegerField())
        )
    ).filter(
        has_requests=True,
    ).with_full_name(
    )

    request_qs = request_qs.annotate(
        workers=Subquery(
            requestworker_sq.filter(
                request=OuterRef('pk')
            ).values(
                'request'
            ).annotate(
                workers_list=ArrayAgg(
                    'worker',
                    ordering=(
                        'pk',
                    )
                )
            ).values(
                'workers_list'
            ),
            output_field=ArrayField(IntegerField())
        )
    )

    if user_location is not None and location_id is not None and user_location != location_id:
        return request_qs.none(), worker_qs.none(), None

    return request_qs, worker_qs, zone_code


def get_requests_on_map(date, user, zone_id=None, location_id=None):

    request_qs, worker_qs, zone_code = get_requests_on_map_querysets(
        date,
        user,
        zone_id,
        location_id,
        with_zone_code=True
    )

    if zone_code is not None:
        city_borders, bounding_box = _get_zone_map_data(zone_code)
    else:
        bounding_box = city_borders = None

    requests = list(
        request_qs.values(
            'pk',
            'driver_name',
            'driver_phones',
            'confirmed_timepoint',
            'workers',
            'items',
            'is_expiring',
            'is_worker_assignment_delayed',
        )
    )
    for request in requests:
        _map_request_format_in_place(request)

    workers = list(
        worker_qs.values(
            'pk',
            'full_name',
            'last_name',
            'tel_number',
            'lastlocation__location__latitude',
            'lastlocation__location__longitude',
            'lastlocation__location__timestamp',
            'requests',
        )
    )
    for worker in workers:
        _map_worker_format_in_place(worker)

    return {
        'timestamp': timezone.localtime(),
        'delivery_requests': requests,
        'workers': workers,
        'bounding_box': bounding_box,
        'city_borders': city_borders,
    }


def _serialize_distance(distance):
    if distance is None:
        return None
    distance_km = round(distance)
    if distance_km > DISTANCE_LIMIT:
        return None
    return distance_km


def _get_requests_in_progress_queryset_for_worker(
        worker_id: int,
        location: Optional[Location] = None
):
    return DeliveryRequest.objects.all(
    ).exclude(
        status__in=DeliveryRequest.FINAL_STATUSES
    ).filter(
        requestworker__worker=worker_id
    ).with_confirmed_timepoint(
    ).with_worker_timepoint(
        worker_id=worker_id
    ).with_items_for_assigned_worker(
        worker_id=worker_id,
        location=location,
        with_amount_estimate=True
    ).annotate(
        active=Exists(
            RequestWorker.objects.annotate(
                has_items=Exists(
                    ItemWorker.objects.filter(
                        requestworker=OuterRef('pk'),
                        itemworkerrejection__isnull=True,
                    )
                )
            ).filter(
                request=OuterRef('pk'),
                worker=worker_id,
                workerrejection__isnull=True,
                requestworkerturnout__isnull=True,
                has_items=True,
            )
        ),
    ).filter(
        delivery_service__isnull=False,
        worker_timepoint__isnull=False,
        active=True,
    ).with_other_workers(
        worker_id
    ).annotate(
        min_hours=F('delivery_service__hours') - F('delivery_service__travel_hours')
    ).values(
        'id',
        'date',
        'driver_name',
        'driver_phones',
        'worker_timepoint',
        'deliveryrequestoperator__operator__first_name',
        'min_hours',
        'items',
        'other_workers',
        # to discard
        'confirmed_timepoint',
        'delivery_service__hours',
        'delivery_service__travel_hours',
        'delivery_service__zone',
        'status',
    ).order_by(
        'date',
        'worker_timepoint',
        'pk',
    )


def _remove_internal_fields(request):
    _delete_tariff_fields(request)
    del request['status']
    for item in request['items']:
        del item['has_elevator']
        del item['floor']
        del item['carrying_distance']


def _mobile_request_start_finish_format(request):
    for item in request['items']:

        is_suspicious = item['log'].pop('is_suspicious')
        check_ok = item['log'].pop('discrepancy_ok')
        if check_ok is not None:
            suspicious = not check_ok
        else:
            suspicious = is_suspicious
        item['log']['suspicious'] = suspicious

        main_photo_id = item['log'].pop('waybill')
        if main_photo_id is not None:
            try:
                main_photo = next(
                    photo
                    for photo in item['log']['finish_photos']
                    if photo['id'] == main_photo_id
                )
                main_photo['main'] = True
            except StopIteration:
                item['log']['finish_photos'].append({
                    'id': main_photo_id,
                    'rejection_comment': None,
                    'main': True,
                })
        item['status'] = item['log'].pop('status')


def _format_timepoint(timepoint):
    if timepoint is None:
        return None
    return timepoint.strftime(date_time.TIME_FORMAT)


def _delivery_request_active_format_in_place(request):
    request['operator_name'] = request.pop('deliveryrequestoperator__operator__first_name')
    request['amount'] = _estimate_sum(request)

    for item in request['items']:
        item['interval_begin'] = item['interval_begin'][:-3]
        item['interval_end'] = item['interval_end'][:-3]
        if 'distance' in item:
            item['distance'] = _serialize_distance(item['distance'])

    request['date'] = date_time.string_from_date(request['date'])

    if 'driver_phones' in request:
        request['driver_phones'] = format_phones(request['driver_phones'])

    _remove_internal_fields(request)


def _requestworker_status(request):
    itemworker_statuses = [item['status'] for item in request['items']]

    worst = min(itemworker_statuses)
    best = max(itemworker_statuses)

    if worst >= ItemWorker.REJECTED_CHEQUE:
        if worst == ItemWorker.COMPLETE:
            return 'complete'
        elif worst == ItemWorker.HAS_CHEQUE:
            return 'has_cheque'
        else:
            return 'rejected_cheque'

    if worst == ItemWorker.NEW:
        return 'new'
    elif worst == ItemWorker.ARRIVAL_REJECTED:
        return 'arrival_rejected'
    elif worst == ItemWorker.ARRIVAL_SUSPICIOUS:
        return 'arrival_suspicious'
    elif best == ItemWorker.ARRIVED:
        return 'arrived'
    elif best == ItemWorker.ARRIVAL_CHECKING:
        return 'arrival_checking'
    else:
        return 'confirmed'


def _delivery_request_in_progress_format_in_place(request):
    _delivery_request_active_format_in_place(request)
    request['confirmed_timepoint'] = _format_timepoint(request.pop('worker_timepoint'))
    _mobile_request_start_finish_format(request)
    request['status'] = _requestworker_status(request)


@log
def get_requests_in_progress_for_worker(worker_id: int, location: Optional[Location]):
    requests = list(_get_requests_in_progress_queryset_for_worker(worker_id, location))
    for request in requests:
        _delivery_request_in_progress_format_in_place(request)
    return requests


RECOMMENDED_REQUEST_LIMIT = 10


def _best_requests_for_worker(
        worker_id: int,
        location: Optional[Location],
):
    today = timezone.localdate()
    try:
        zone_id = WorkerZone.objects.values_list(
            'zone',
            flat=True
        ).get(
            worker_id=worker_id
        )
    except WorkerZone.DoesNotExist:
        return DeliveryRequest.objects.none()

    return DeliveryRequest.objects.all(
    ).with_new_worker_timepoint(
    ).filter_self_assign_ready(
        today,
        zone_id,
    ).annotate(
        already_assigned=Exists(
            RequestWorker.objects.filter(
                request=OuterRef('pk'),
                worker=worker_id,
            )
        ),
    ).filter(
        already_assigned=False,
    ).with_confirmed_timepoint(
    ).with_items_for_unassigned_worker(
        location=location
    ).annotate(
        min_hours=F('delivery_service__hours') - F('delivery_service__travel_hours')
    ).values(
        'id',
        'date',
        'confirmed_timepoint',
        'new_worker_timepoint',
        'deliveryrequestoperator__operator__first_name',
        'min_hours',
        'items',
        'delivery_service__hours',
        'delivery_service__travel_hours',
        'delivery_service__zone',
        'status',
    ).order_by(
        'date',
        'new_worker_timepoint',
        'pk',
    )[:RECOMMENDED_REQUEST_LIMIT]


def _delivery_request_recommended_format_in_place(request):
    _delivery_request_active_format_in_place(request)
    request['confirmed_timepoint'] = _format_timepoint(request.pop('new_worker_timepoint'))
    for item in request['items']:
        del item['mass']
    request['status'] = 'new'


def get_recommended_requests(
        worker_id: int,
        location: Optional[Location],
):
    requests = list(_best_requests_for_worker(worker_id, location))
    for request in requests:
        _delivery_request_recommended_format_in_place(request)
    return requests


def _get_last_location(worker_id: int) -> Optional[Location]:
    return Location.objects.filter(
        lastlocation__worker=worker_id,
        timestamp__date__gte=timezone.localdate()
    ).order_by(
        'timestamp'
    ).only(
        'latitude',
        'longitude',
    ).last()


def get_delivery_request_list_for_worker(
        worker_id: int,
        location: Optional[Location],
):
    try:
        worker = Worker.objects.select_related(
            'banned'
        ).only(
            'citizenship',
            'm_date_of_exp'
        ).get(
            pk=worker_id
        )
    except Worker.DoesNotExist:
        raise ObjectNotFoundError(f'Работник {worker_id} не найден.')

    if hasattr(worker, 'banned'):
        status = 'banned'
        requests_to_do = []
    else:
        if location is None:
            location = _get_last_location(worker_id)
        requests_to_do = get_requests_in_progress_for_worker(worker_id, location)
        if requests_to_do:
            status = 'busy'
        elif is_citizenship_migration_ok(worker):
            status = 'free'
            requests_to_do = get_recommended_requests(worker_id, location)
        else:
            status = 'expired_documents'

    completed_unreconciled = get_unpaid_requests_for_worker(worker_id, reconciled=False)
    return {
        'status': status,
        'requests': requests_to_do + completed_unreconciled['requests']
    }


def _get_unpaid_requests_queryset_for_worker(worker_id: int):
    return DeliveryRequest.objects.all(
    ).filter(
        requestworker__worker=worker_id
    ).annotate(
        is_reconciled=Exists(
            DailyReconciliationConfirmation.objects.filter(
                reconciliation__location=OuterRef('location'),
                reconciliation__date=OuterRef('date'),
            )
        )
    ).annotate(
        is_finished_unpaid=Exists(
            RequestWorkerTurnout.objects.filter(
                Q(workerturnout__turnoutoperationtopay__operation__paysheet_entry_operation__entry__paysheet__is_closed=False) |
                Q(workerturnout__turnoutoperationtopay__operation__paysheet_entry_operation__isnull=True),
                requestworker__request=OuterRef('pk'),
                requestworker__worker=worker_id,
            )
        ),
    ).filter(
        is_finished_unpaid=True,
    ).with_items_for_assigned_worker(
        worker_id=worker_id,
    ).with_other_workers(
        worker_id=worker_id
    ).annotate(
        amount=Subquery(
            RequestWorker.objects.filter(
                request=OuterRef('pk'),
                worker=worker_id,
            ).values(
                'requestworkerturnout__workerturnout__turnoutoperationtopay__operation__amount'
            ),
            output_field=DecimalField()
        )
    ).values(
        'id',
        'date',
        'driver_name',
        'driver_phones',
        'deliveryrequestoperator__operator__first_name',
        'items',
        'other_workers',
        'amount'
    ).order_by(
        '-pk'
    )


def _delivery_request_unpaid_format_in_place(request):
    request['operator_name'] = request.pop('deliveryrequestoperator__operator__first_name')
    request['driver_phones'] = format_phones(request['driver_phones'])
    _mobile_request_start_finish_format(request)


@log
def get_unpaid_requests_for_worker(worker_id: int, reconciled: bool = True):
    requests = list(
        _get_unpaid_requests_queryset_for_worker(worker_id).filter(
            is_reconciled=reconciled
        )
    )
    if reconciled:
        status = 'closed'
    else:
        status = 'unreconciled'
    for request in requests:
        _delivery_request_unpaid_format_in_place(request)
        request['status'] = status
    return {
        'requests': requests
    }


def get_delivery_request_detail_for_worker(
        request_id: int,
        worker_id: int,
        location: Optional[Location],
):
    try:
        if location is None:
            location = _get_last_location(worker_id)
        request = _get_requests_in_progress_queryset_for_worker(
            worker_id,
            location,
        ).get(pk=request_id)
    except DeliveryRequest.DoesNotExist:
        raise ObjectNotFoundError(f'Заявка {request_id} не найдена.')

    _delivery_request_in_progress_format_in_place(request)
    return request


CUSTOMER_REQUEST_MIN_DATE = datetime.date(2020, 8, 1)


def _get_request_queryset_for_customer(customer_id, user_location_id=None, api=False):
    request_qs = DeliveryRequest.objects.all(
    ).filter(
        customer=customer_id,
        date__gte=CUSTOMER_REQUEST_MIN_DATE
    ).with_confirmed_timepoint(
    ).with_worker_count(
    ).with_worker_count(
        turnout=False
    ).with_customer_resolution(
    ).with_arrival_time(
    ).with_start_photos(
    ).with_finish_photos(
    ).with_worked_hours(
    ).with_customer_amount(
    ).with_payment_status(
        customer_id=customer_id
    ).with_items_for_customer(
    )

    fields = [
        'pk',
        'date',
        'driver_name',
        'driver_phones',
        'route',
        'status',
        'status_description',
        'confirmed_timepoint',
        'comment',
        'worker_count',
        'worker_no_turnout_count',
        'delivery_service__service_id',
        'delivery_service__hours',
        'delivery_service__travel_hours',
        'customer_resolution',
        'customer_comment',
        'arrival_time',
        'worked_hours',
        'customer_amount',
        'items',
    ]
    if not api:
        fields.extend([
            'start_photos',
            'finish_photos',
        ])

    if user_location_id is not None:
        request_qs = request_qs.filter(
            location=user_location_id
        )
    elif not api:
        request_qs = request_qs.with_passport_selfies()
        fields.append('passport_selfies')

    return request_qs.values(*fields)


class DeliveryRequestFormatter:

    def __init__(self, api=False):
        self.api = api
        self.calculators = {}
        self.photo_url_prefix = reverse('the_redhuman_is:gt_customer_request_photo')

    def _get_calculator_intervals(self, service_id, day):

        def is_calculator_applicable(calc):
            return calc['first_day'] <= day <= (calc['last_day'] or datetime.date.max)

        try:
            return next(
                filter(
                    is_calculator_applicable,
                    self.calculators[service_id]
                )
            )['intervals']

        except (KeyError, StopIteration):
            calculator = ServiceCalculator.objects.values(
                'first_day',
                'last_day',
                'calculator__customer_object_id',
            ).get(
                Q(last_day__isnull=True) |
                Q(last_day__gte=day),
                customer_service=service_id,
                first_day__lte=day,
            )
            intervals = list(CalculatorInterval.objects.filter(
                singleturnoutcalculator=calculator['calculator__customer_object_id']
            ).order_by('-begin').values())
            for item in intervals:
                item['begin'] = Decimal(item['begin']).quantize(ZERO_OO, ROUND_CEILING)
            self.calculators.setdefault(service_id, []).append({
                'intervals': intervals,
                'first_day': calculator['first_day'],
                'last_day': calculator['last_day']
            })
            self.calculators[service_id].sort(
                key=operator.itemgetter('first_day')
            )
            return intervals

    def _get_customer_cost_estimate(self, request) -> Decimal:
        intervals = self._get_calculator_intervals(
            request['delivery_service__service_id'],
            request['date']
        )
        hours_worked = sum(
            calculate_delivery_request_hours(
                hours=request['delivery_service__hours'],
                travel_hours=request['delivery_service__travel_hours'],
                confirmed_timepoint=request['confirmed_timepoint'],
            )
        )
        try:
            interval = next(filter(lambda item: item['begin'] <= hours_worked, intervals))
            return Decimal(
                interval['k'] * float(hours_worked) + interval['b']
            ).quantize(ZERO_OO)
        except StopIteration:
            return ZERO_OO

    def _get_cost_for_customer(self, request) -> Optional[Decimal]:
        if request['delivery_service__service_id'] is None:
            return None
        if request['worker_count'] == 0 or request['worker_no_turnout_count'] > 0:
            estimate = self._get_customer_cost_estimate(request)
            if request['worker_count'] == 0:
                cost = estimate
            else:
                cost = (
                    request['customer_amount'] +
                    request['worker_no_turnout_count'] * estimate
                )
        else:
            cost = request['customer_amount']
        return cost

    def format_for_customer(self, request):
        if request['driver_name'] is None:
            request['driver_name'] = ''
        status_id = request['status']
        request['status'] = {
            'id': status_id,
            'text': request.pop('status_description'),
        }
        if not self.api:
            request['status']['order'] = DeliveryRequest.SORTING_ORDER[status_id]
            request_pk = request['pk']

            def serialize_photo_set(key_):
                return [
                    {
                        'id': pk,
                        'url': f'{self.photo_url_prefix}?request={request_pk}&photo={pk}'
                    }
                    for pk in request[key_]
                ]

            for key in ('start_photos', 'finish_photos', 'passport_selfies'):
                if key in request:
                    request[key] = serialize_photo_set(key)

        request['driver_phones'] = (
            format_phones(request['driver_phones']).split(', ')
            if request['driver_phones']
            else []
        )
        request['cost'] = self._get_cost_for_customer(request)

        if request['confirmed_timepoint'] is not None:
            request['confirmed_timepoint'] = request['confirmed_timepoint'].strftime(
                date_time.TIME_FORMAT
            )

        for item in request['items']:
            if item.get('interval_begin'):
                item['interval_begin'] = item['interval_begin'][:-3]

            if item.get('interval_end'):
                item['interval_end'] = item['interval_end'][:-3]

        del request['delivery_service__service_id']
        del request['delivery_service__hours']
        del request['delivery_service__travel_hours']
        del request['worker_no_turnout_count']


def get_delivery_request_detail_for_customer(request_id, user, api=False):
    user_customer, user_location = get_user_customer_location(user)

    try:
        request = _get_request_queryset_for_customer(
            customer_id=user_customer,
            user_location_id=user_location,
        ).get(
            pk=request_id
        )
    except DeliveryRequest.DoesNotExist:
        raise ObjectNotFoundError(f'Заявка {request_id} не найдена.')
    formatter = DeliveryRequestFormatter(api=api)
    formatter.format_for_customer(request)
    return request


def _get_customerlocation_queryset(customer_id):
    return CustomerLocation.objects.filter(
        customer_id=customer_id,
        is_actual=True,
    ).values(
        'id',
        'location_name',
    )


def _location_format_in_place(location):
    location['name'] = location.pop('location_name')


def get_location_list_for_customer_api(user):
    user_customer, _ = get_user_customer_location(user)

    locations = list(_get_customerlocation_queryset(
        customer_id=user_customer
    ).order_by('pk'))
    for location in locations:
        _location_format_in_place(location)

    return locations


class DeliveryRequestCustomerFilter(DeliveryRequestBaseFilter):
    status = filters.CharFilter(lookup_expr='iexact')
    customer_resolution = filters.ChoiceFilter(choices=DeliveryRequest.CUSTOMER_RESOLUTIONS)
    payment_status = filters.ChoiceFilter(
        choices=DeliveryRequest.PAYMENT_STATUSES,
        method='payment_status_filter'
    )

    class Meta:
        model = DeliveryRequest
        fields = []

    def payment_status_filter(self, queryset, name, value):
        if value == DeliveryRequest.ACTIVE:
            return queryset.filter(is_paid__isnull=True)
        elif value == DeliveryRequest.PAID:
            return queryset.filter(is_paid=True)
        elif value == DeliveryRequest.IN_PAYMENT:
            return queryset.filter(is_paid=False)
        else:
            raise NotImplementedError

    def search_text_filter(self, queryset, name, value):
        return queryset.filter_by_text(value, mode='customer')


class DeliveryRequestCustomerApiFilter(FilterSet):
    first_day = filters.DateFilter(field_name='date', lookup_expr='gte', required=True)
    last_day = filters.DateFilter(field_name='date', lookup_expr='lte', required=True)
    location = CompactChoiceFilter(field_name='location')
    is_finished = BooleanFilter(method='filter_finished')
    order = ConsistentOrderingFilter(
        fields=(
            ('date', 'date'),
        ),
        discriminator=('-pk',)
    )

    class Meta:
        model = DeliveryRequest
        fields = []

    def filter_finished(self, queryset, name, value):
        if value is True:
            return queryset.filter(
                status__in=DeliveryRequest.FINAL_STATUSES
            )
        elif value is False:
            return queryset.exclude(
                status__in=DeliveryRequest.FINAL_STATUSES
            )
        return queryset


def get_delivery_request_list_for_customer_api(user, filter_args):
    user_customer, user_location = get_user_customer_location(user)

    request_qs = _get_request_queryset_for_customer(
        customer_id=user_customer,
        user_location_id=user_location,
        api=True
    ).order_by(
        '-pk'
    )

    requests = list(DeliveryRequestCustomerApiFilter(filter_args, queryset=request_qs).qs)

    formatter = DeliveryRequestFormatter(api=True)
    for request in requests:
        formatter.format_for_customer(request)

    return requests


def get_delivery_request_list_for_customer(user, filter_args):
    user_customer, user_location = get_user_customer_location(user)

    request_qs = _get_request_queryset_for_customer(
        customer_id=user_customer,
        user_location_id=user_location,
    )

    requests = list(DeliveryRequestCustomerFilter(filter_args, queryset=request_qs).qs)

    formatter = DeliveryRequestFormatter()
    for request in requests:
        formatter.format_for_customer(request)

    return {
        'requests': requests,
    }


def get_photo_for_customer(photo_id: int, request_id: int, user: User) -> Optional[Photo]:
    user_customer, user_location = get_user_customer_location(user)
    try:
        photo = Photo.objects.defer('image').get(pk=photo_id)
    except Photo.DoesNotExist:
        return None

    def _customer_has_permissions(object_id, content_type_id):
        if content_type_id == ContentType.objects.get_for_model(Worker).pk:
            return (
                user_location is None and
                ItemWorker.objects.filter(
                    itemworkerrejection__isnull=True,
                    requestworker__request=request_id,
                    requestworker__workerrejection__isnull=True,
                    requestworker__worker=object_id,
                    requestworker__request__customer=user_customer,
                ).exists()
            )
        elif content_type_id == ContentType.objects.get_for_model(ItemWorkerStart).pk:
            item_qs = ItemWorkerStart.objects.filter(
                pk=object_id,
                itemworker__itemworkerrejection__isnull=True,
                itemworker__requestworker__request=request_id,
                itemworker__requestworker__request__customer=user_customer,
                itemworker__requestworker__workerrejection__isnull=True,
                itemworkerstartconfirmation__isnull=False,
            )
        elif (
            content_type_id == ContentType.objects.get_for_model(ItemWorkerFinish).pk or
            content_type_id == ContentType.objects.get_for_model(TimeSheet).pk
        ):
            item_qs = ItemWorkerFinish.objects.filter(
                photo=photo_id,
                itemworker__itemworkerrejection__isnull=True,
                itemworker__requestworker__request=request_id,
                itemworker__requestworker__request__customer=user_customer,
                itemworker__requestworker__workerrejection__isnull=True,
            )
        else:
            return False
        if user_location is not None:
            item_qs = item_qs.filter(
                itemworker__requestworker__request__location=user_location
            )
        return item_qs.exists()

    if _customer_has_permissions(photo.object_id, photo.content_type_id):
        return photo
