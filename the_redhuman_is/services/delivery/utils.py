import re
from datetime import datetime
from decimal import (
    Decimal,
    ROUND_CEILING,
)
from typing import (
    List,
    Optional,
    Tuple,
    cast,
)

from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import (
    ObjectDoesNotExist,
    PermissionDenied,
    ValidationError,
)
from django.db import (
    OperationalError,
    transaction,
)
from django.db.models import (
    Case,
    F,
    IntegerField,
    Max,
    Min,
    OuterRef,
    ProtectedError,
    Q,
    Subquery,
    TextField,
    Value,
    When,
)
from django.db.models.functions import (
    Cast,
    Coalesce,
)
from django.db.transaction import TransactionManagementError
from django.utils import timezone
from django.utils.functional import lazy

from the_redhuman_is import geo_utils
from the_redhuman_is.models.delivery import (
    ConfirmedDailyReconciliationExists,
    DailyReconciliation,
    DeliveryItem,
    DeliveryRequest,
    DeliveryRequestOperator,
    ItemWorker,
    ItemWorkerFinish,
    ItemWorkerStart,
    PrivateDeliveryRequest,
    RequestWorker,
    RequestWorkerTurnout,
)
from the_redhuman_is.models.models import (
    Customer,
    CustomerAccount,
    LocationAccount,
    TimeSheet,
    TurnoutService,
    WorkerTurnout,
)
from the_redhuman_is.models.photo import Photo
from the_redhuman_is.models.turnout_calculators import get_delivery_request_hours
from the_redhuman_is.models.worker import Country
from the_redhuman_is.services import reconciliations

from the_redhuman_is.services.delivery_requests import (
    MAX_ARRIVAL_DELTA,
    _deduction_worker,
    ensure_timesheet,
)
from the_redhuman_is.services.turnout_calculations import update_turnout_payments

from utils import (
    extract_phones,
    string_from_date,
)
from utils.numbers import ZERO_OO


class DataIntegrityError(Exception):
    pass


class DeliveryWorkflowError(PermissionDenied):
    pass


class ObjectNotFoundError(ObjectDoesNotExist):
    pass


class DatabaseLockError(OperationalError):
    pass


def catch_lock_error(lock_func):
    def wrapped(*args, **kwargs):
        try:
            return lock_func(*args, **kwargs)
        except OperationalError as e:
            if e.args and e.args[0].startswith('could not obtain lock'):
                raise DatabaseLockError from None
            raise
    return wrapped


def normalize_driver_name(name):
    if name is None:
        return None
    return re.sub(r'\s+', ' ', name.strip()).upper()


def normalize_driver_phones(phones):
    if phones is None:
        return None
    return sorted(extract_phones(phones.strip()))


def get_user_customer_location(user):
    try:
        user_customer = user.customeraccount.customer_id
    except CustomerAccount.DoesNotExist:
        user_customer = None

    try:
        user_location = user.locationaccount.location_id
    except LocationAccount.DoesNotExist:
        user_location = None

    return user_customer, user_location


def ensure_unclosed_date(location_id, date):
    daily_reconciliations = DailyReconciliation.objects.filter(
        location=location_id,
        date=date,
        dailyreconciliationconfirmation__isnull=False,
    )
    if daily_reconciliations.exists():
        raise ConfirmedDailyReconciliationExists(
            f'Сверка за {string_from_date(date)} уже подтверждена.'
            f' Создание и редактирование заявок запрещено.'
        )


def ensure_can_be_edited(delivery_request):
    if delivery_request.location_id is not None:
        ensure_unclosed_date(delivery_request.location_id, delivery_request.date)


def ensure_can_save_timesheet(
        request: DeliveryRequest,
        check_if_can_create_reconciliation: bool = False
) -> None:
    if request.location_id is not None:
        try:
            reconciliations.ensure_unclosed(
                cast(int, request.customer_id),
                cast(int, request.location_id),
                request.date,
                check_if_can_create_reconciliation=check_if_can_create_reconciliation
            )
        except ValidationError as e:
            raise DeliveryWorkflowError(e.message) from None


DESCRIPTIONS = {k: v for k, v in DeliveryRequest.STATUS_TYPES}


def update_delivery_request_status(delivery_request, user):
    def _save(status, description=None):
        delivery_request.status = status
        if description is None:
            delivery_request.status_description = DESCRIPTIONS[status]
        delivery_request.save(user=user, update_fields=['status', 'status_description'])

    normalized = DeliveryItem.objects.filter(
        request=delivery_request
    ).with_dadata_address_exists(
#    ).with_googlemaps_address_exists( # Todo: GT-1074
    ).filter(
        dadata_address_exists=True,
#        googlemaps_address_exists=True, # Todo: GT-1074
    ).exists(
    )
    if not normalized:
        _save(DeliveryRequest.AUTOTARIFICATION)
        return

    active_workers = delivery_request.active_workers()

    if not active_workers.exists():
        if delivery_request.status not in DeliveryRequest.FAIL_STATUSES:
            if delivery_request.confirmed_timepoint is not None:
                _save(DeliveryRequest.TIMEPOINT_CONFIRMED)
            elif delivery_request.status not in DeliveryRequest.CALLBACK_STATUSES:
                _save(DeliveryRequest.NEW)
        return

    if delivery_request.status == DeliveryRequest.CANCELLED_WITH_PAYMENT:
        return

    if delivery_request.delivery_service_id is None:
        _save(DeliveryRequest.NEW)
        return

    itemworker_sq = active_workers.with_status(
    ).filter(
        item=OuterRef('pk')
    ).values(
        'item'
    )

    item_qs = DeliveryItem.objects.filter(
        request=delivery_request
    ).with_itemworker_count(
    ).annotate(
        status=Coalesce(
            Case(
                When(
                    itemworker_count__lt=F('workers_required'),
                    then=ItemWorker.NOT_ASSIGNED,
                )
            ),
            Subquery(
                itemworker_sq.annotate(
                    Min('status')
                ).values(
                    'status__min'
                ),
                output_field=IntegerField()
            )
        )
    ).filter(
        workers_required__gt=0,
    )

    best_worst_status = item_qs.aggregate(Min('status'), Max('status'))
    worst_item_status = best_worst_status['status__min']
    best_item_status = best_worst_status['status__max']
    if worst_item_status is None:
        return

    if worst_item_status >= ItemWorker.REJECTED_CHEQUE:
        if worst_item_status == ItemWorker.COMPLETE:
            _save(DeliveryRequest.COMPLETE)
        elif worst_item_status == ItemWorker.HAS_CHEQUE:
            _save(DeliveryRequest.CHEQUE_ATTACHED)
        else:  # REJECTED_CHEQUE
            _save(DeliveryRequest.ARRIVED, 'Накладная отклонена')

        return

    if worst_item_status == ItemWorker.NOT_ASSIGNED:
        _save(DeliveryRequest.TIMEPOINT_CONFIRMED)
    elif worst_item_status == ItemWorker.NEW:
        _save(DeliveryRequest.WORKERS_ASSIGNED)
    elif worst_item_status == ItemWorker.ARRIVAL_REJECTED:
        _save(DeliveryRequest.ARRIVAL_REJECTED)
    elif best_item_status >= ItemWorker.ARRIVED:
        _save(DeliveryRequest.ARRIVED)
    else:
        _save(DeliveryRequest.WORKERS_CONFIRMED)


def _can_override_hours(author: User):
    return author.is_superuser or author.groups.filter(
        name='Доставка-руководитель'
    ).exists()


can_override_hours = lazy(_can_override_hours, bool)


@transaction.atomic
def confirm_turnout(
        requestworker: RequestWorker,
        user: User,
        hours: Optional[Decimal] = None,
        use_default_hours: bool = False,
        force_commit: bool = False
) -> Tuple[TimeSheet, List[str], bool]:

    if not transaction.get_connection().in_atomic_block:
        raise TransactionManagementError(
            "Finance operations are forbidden outside of an atomic block."
        )

    request = requestworker.request
    worker = requestworker.worker

    if hasattr(requestworker, 'workerrejection'):
        raise DeliveryWorkflowError(
            f'Работник {requestworker.worker_id} не назначен на заявку {request.pk}.'
        )

    if not request.delivery_service:
        raise DeliveryWorkflowError(
            f'Для заявки №{request.pk} должен быть установлен тариф, но его нет.'
        )

    timesheet = ensure_timesheet(request, worker)

    if use_default_hours:
        hours_worked = sum(get_delivery_request_hours(request))
    else:
        hours_worked = validate_hours(requestworker, hours, override=can_override_hours(user))

    try:
        link = RequestWorkerTurnout.objects.filter(
            requestworker=requestworker
        ).select_related(
            'workerturnout__turnoutservice'
        ).get()
        link.timestamp = timezone.now()
        link.save(update_fields=['timestamp'])

        turnout = link.workerturnout
        turnout.hours_worked = hours_worked
        turnout.save()

        turnout_service = turnout.turnoutservice
        turnout_service.customer_service = request.delivery_service.service
        turnout_service.save()

    except RequestWorkerTurnout.DoesNotExist:
        turnout = WorkerTurnout.objects.create(
            timesheet=timesheet,
            worker=worker,
            hours_worked=hours_worked
        )
        RequestWorkerTurnout.objects.create(
            requestworker=requestworker,
            workerturnout=turnout
        )
        TurnoutService.objects.create(
            turnout=turnout,
            customer_service=request.delivery_service.service
        )

    messages, confirmation_required = update_turnout_payments(
        turnout.pk,
        user,
        _deduction_worker(request),
        # why: worker has turnout, gets auto-reconfirmed with fewer hours
        force_commit=force_commit
    )

    Photo.objects.filter(
        itemworkerfinish__itemworker__requestworker=requestworker
    ).update(
        content_type=ContentType.objects.get_for_model(TimeSheet),
        object_id=timesheet.pk,
    )

    return timesheet, messages, confirmation_required


def update_turnouts(
        delivery_request: DeliveryRequest,
        author: User,
        prev_bonus: Optional[Decimal] = None,
        force_commit: bool = False
) -> Tuple[List[str], bool]:

    if not transaction.get_connection().in_atomic_block:
        raise TransactionManagementError(
            "Finance operations are forbidden outside of an atomic block."
        )

    messages = []
    confirmation_required = False

    turnout_links = RequestWorkerTurnout.objects.filter(
        requestworker__request=delivery_request,
        requestworker__workerrejection__isnull=True,
    ).select_related(
        'workerturnout__turnoutservice'
    )
    if not turnout_links.exists():
        return messages, confirmation_required

    customer_service = delivery_request.delivery_service.service

    for link in turnout_links:
        if prev_bonus is not None:
            hours_worked = sum(get_delivery_request_hours(
                delivery_request,
                base_hours=link.workerturnout.hours_worked - prev_bonus
            ))
        else:
            hours_worked = link.workerturnout.hours_worked

        turnout = link.workerturnout
        turnout.hours_worked = hours_worked
        try:
            turnout.save()
        except ValidationError as ex:
            raise DeliveryWorkflowError(ex.message)

        turnout_service = turnout.turnoutservice
        turnout_service.customer_service = customer_service
        turnout_service.save()

        turnout_messages, turnout_confirmation_required = update_turnout_payments(
            link.workerturnout.pk,
            author,
            _deduction_worker(delivery_request),
            force_commit=force_commit
        )

        messages.extend(turnout_messages)
        confirmation_required |= turnout_confirmation_required

    return messages, confirmation_required


def delete_turnout(
        requestworker: RequestWorker,
        user: User,
        force_commit: bool = False
) -> Tuple[List[str], bool]:

    if not transaction.get_connection().in_atomic_block:
        raise TransactionManagementError(
            "Finance operations are forbidden outside of an atomic block."
        )

    try:
        requestworkerturnout = RequestWorkerTurnout.objects.select_related(
            'workerturnout__timesheet'
        ).get(requestworker=requestworker)
    except RequestWorkerTurnout.DoesNotExist:
        return [], False

    turnout = requestworkerturnout.workerturnout
    timesheet = turnout.timesheet
    request = requestworker.request

    TurnoutService.objects.filter(turnout=turnout).delete()
    messages, confirmation_required = update_turnout_payments(
        turnout.pk,
        user,
        _deduction_worker(request),
        force_commit=force_commit
    )

    requestworkerturnout.delete()
    try:
        with transaction.atomic():
            turnout.delete()
    except ProtectedError:
        turnout.hours_worked = 0
        turnout.save()
    else:
        if not timesheet.worker_turnouts.all().exists():
            timesheet.customerorder.delete()
            timesheet.delete()

    Photo.objects.annotate(
        # django update query bug, cannot use __-joined fields as values
        finish=Subquery(
            ItemWorkerFinish.objects.filter(
                photo=OuterRef('pk')
            ).values(
                'pk'
            ),
            output_field=IntegerField()
        )
    ).filter(
        itemworkerfinish__itemworker__requestworker=requestworker
    ).update(
        content_type=ContentType.objects.get_for_model(ItemWorkerFinish),
        object_id=F('finish'),
    )

    return messages, confirmation_required


def update_request_timesheets(delivery_request: DeliveryRequest) -> None:
    links = RequestWorkerTurnout.objects.filter(
        requestworker__request=delivery_request
    ).select_related(
        'requestworker__worker',
        'workerturnout__timesheet',
    )

    for link in links:
        worker = link.requestworker.worker
        worker_turnout = link.workerturnout

        timesheet = ensure_timesheet(delivery_request, worker)
        if timesheet == worker_turnout.timesheet:
            return

        old_timesheet = worker_turnout.timesheet
        worker_turnout.timesheet = timesheet
        worker_turnout.save()

        if not old_timesheet.worker_turnouts.all().exists():
            old_timesheet.customerorder.delete()
            old_timesheet.delete()


def check_if_can_move(
        item: DeliveryItem,
        src_request: DeliveryRequest,
        target_request: DeliveryRequest,
):
    fields_to_check = [
        'customer',
        'date',
        'driver_name',
        'driver_phones'
    ]

    for field in fields_to_check:
        if getattr(src_request, field) != getattr(target_request, field):
            raise DeliveryWorkflowError(
                'Нельзя перенести индекс {}({}) из маршрута {}({}) в {}({}): '
                'отличается поле {}.'.format(
                    item.code,
                    item.pk,
                    src_request.route,
                    src_request.pk,
                    target_request.route,
                    target_request.pk,
                    DeliveryRequest._meta.get_field(field).verbose_name
                )
            )


def create_private_request(
        author: User,
        *args,
        **kwargs
) -> DeliveryRequest:
    request = DeliveryRequest.objects.create(
        author=author,
        *args,
        **kwargs,
    )
    PrivateDeliveryRequest.objects.create(
        author=author,
        request=request,
    )
    return request


def get_request_to_merge(
        customer,
        date,
        driver_name,
        driver_phones,
        location=None
) -> Optional[DeliveryRequest]:

    if location is not None and DailyReconciliation.objects.filter(
        location=location,
        date=date,
        dailyreconciliationconfirmation__isnull=False
    ).exists():
        return None

    driver_name = driver_name or ''
    driver_phones = driver_phones or ''
    if not driver_name and not driver_phones:
        return None

    # locks at evaluation, watch out when debugging
    request_qs = DeliveryRequest.objects.select_for_update(
        of=('self',)
    ).annotate(
        driver_name_blank=Coalesce('driver_name', Value(''), output_field=TextField()),
        driver_phones_blank=Coalesce('driver_phones', Value(''), output_field=TextField()),
    ).filter(
        date=date,
        customer=customer,
    ).exclude(
        status__in=DeliveryRequest.FINAL_STATUSES
    ).exclude(
        driver_name_blank='',
        driver_phones_blank='',
    ).filter(
        Q(driver_name_blank=driver_name) |
        Q(driver_phones_blank=driver_phones)
    )
    if driver_name:
        request_qs = request_qs.filter(
            Q(driver_name_blank=driver_name) |
            Q(driver_name_blank='')
        )
    if driver_phones:
        request_qs = request_qs.filter(
            Q(driver_phones_blank=driver_phones) |
            Q(driver_phones_blank='')
        )
    if location is not None:
        request_qs = request_qs.filter(location=location)
    else:  # already ensured "location is not None" can be edited
        request_qs = request_qs.with_can_be_edited(
        ).filter(
            can_be_edited=True
        )
    request_to_merge = request_qs.order_by(
        'route', 'pk'
    ).last()
    return request_to_merge


def free_route_number(
        customer: Customer,
        date: datetime.date,
) -> int:
    greatest = DeliveryRequest.objects.filter(
        route__isnull=False,
        route__regex=r'^\d+',
        customer=customer,
        date=date,
    ).annotate(
        route_num=Cast('route', output_field=IntegerField())
    ).order_by(
        'route_num'
    ).last()

    if greatest is not None:
        return greatest.route_num + 1

    return 1


@transaction.atomic
def try_assign_operator(request_id, user):
    _, created = DeliveryRequestOperator.objects.get_or_create(
        request_id=request_id,
        defaults={
            'operator': user,
        }
    )
    return created


def is_request_paid(delivery_request: DeliveryRequest) -> bool:
    return RequestWorkerTurnout.objects.filter(
        requestworker__request=delivery_request,
        workerturnout__turnoutoperationtopay__operation__paysheet_entry_operation__isnull=False,
    ).exists()


def can_be_cancelled_with_payment(delivery_request):
    if delivery_request.delivery_service is None:
        return False

    arrived_workers = ItemWorkerStart.objects.filter(
        itemworker__item__request=delivery_request
    )
    return arrived_workers.exists()


def update_suspicion_flag(delivery_item, itemworkerstart=None):
    def _process_itemworkerstart(item, start):
        distance = None
        if start.location is None:
            start.is_suspicious = True
        elif item.geotag is None:
            start.is_suspicious = True
        else:
            distance = geo_utils.distance(
                start.location.longitude,
                start.location.latitude,
                item.geotag['longitude'],
                item.geotag['latitude']
            )
            start.is_suspicious = distance > MAX_ARRIVAL_DELTA
        start.save(update_fields=['is_suspicious'])
        return distance

    if itemworkerstart is not None:
        return _process_itemworkerstart(delivery_item, itemworkerstart)
    else:
        itemworkerstarts = ItemWorkerStart.objects.filter(
            itemworker__item=delivery_item
        )
        for iw_start in itemworkerstarts:
            _process_itemworkerstart(delivery_item, iw_start)


def _max_turnout_work_hours(requestworker: RequestWorker) -> Decimal:

    if requestworker.request.status == DeliveryRequest.CANCELLED_WITH_PAYMENT:
        return ZERO_OO

    start_time = ItemWorkerStart.objects.filter(
        itemworker__requestworker=requestworker
    ).aggregate(
        Min('timestamp')
    )['timestamp__min']

    finish_time = ItemWorkerFinish.objects.filter(
        itemworker__requestworker=requestworker
    ).aggregate(
        Max('photo__timestamp')
    )['photo__timestamp__max']

    if start_time is None or finish_time is None:
        return ZERO_OO

    delta_seconds = Decimal(str((finish_time - start_time).total_seconds()))

    return (delta_seconds / 3600).quantize(
        Decimal('1.'),
        rounding=ROUND_CEILING
    ).quantize(ZERO_OO)


def validate_hours(
        requestworker: RequestWorker,
        hours: Optional[Decimal] = None,
        override: bool = False,
):
    min_base_hours, travel_hours, night_surcharge = get_delivery_request_hours(
        requestworker.request
    )
    max_base_hours = max(min_base_hours, _max_turnout_work_hours(requestworker))
    error_args = (min_base_hours, max_base_hours, travel_hours, night_surcharge)

    if hours is None:
        raise HoursError(*error_args, code='hours_required')

    if not min_base_hours <= hours <= max_base_hours and not override:
        raise HoursError(*error_args, code='hours_invalid')

    return sum(get_delivery_request_hours(requestworker.request, hours))


class HoursError(Exception):
    default_error_details = {
        'hours_required': (
            'Для подтверждения завершения работы на заявке'
            ' необходимо указать количество отработанных часов.'
        ),
        'hours_invalid': (
            'Число часов работы на адресе должно быть в пределах от {min_hours} до {max_hours}.'
        )
    }

    def __init__(
            self,
            min_hours: Decimal,
            max_hours: Decimal,
            travel_hours: Decimal,
            night_surcharge: Decimal,
            code: str,
            detail: Optional[str] = None,
    ):
        self.code = code
        self.messages: dict = {
            'min_hours': min_hours,
            'max_hours': max_hours,
            'travel_hours': travel_hours,
            'night_surcharge': night_surcharge,
        }
        self.detail = detail or self.default_error_details[code].format(**self.messages)


def is_citizenship_migration_ok(worker, deadline=None):
    if deadline is None:
        deadline = timezone.localdate()
    return worker.citizenship_id == Country.RUSSIA.pk or worker.m_date_of_exp >= deadline
