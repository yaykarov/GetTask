import datetime
from decimal import Decimal
from typing import (
    Any,
    List,
    Mapping,
    Optional,
    Tuple,
    cast,
)

import openpyxl
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import (
    PermissionDenied,
    ValidationError,
)
from django.core.files.uploadedfile import UploadedFile
from django.db import transaction
from django.db.models import (
    Exists,
    F,
    Min,
    OuterRef,
)
from django.utils import timezone

from the_redhuman_is.models.delivery import (
    DeliveryFirstAddress,
    DeliveryItem,
    DeliveryRequest,
    DeliveryRequestConfirmation,
    DeliveryService,
    DriverSms,
    ItemWorker,
    ItemWorkerDiscrepancyCheck,
    ItemWorkerFinish,
    ItemWorkerFinishConfirmation,
    ItemWorkerRejection,
    ItemWorkerStart,
    ItemWorkerStartConfirmation,
    Location,
    LocationZoneGroup,
    PhotoRejectionComment,
    PrivateDeliveryRequest,
    RequestWorker,
    RequestWorkerTurnout,
    Worker,
    WorkerConfirmation,
    WorkerRejection,
    WorkerZone,
)
from the_redhuman_is.models.models import (
    Customer,
    CustomerLocation,
    TimeSheet,
)
from the_redhuman_is.models.photo import (
    Photo,
    add_photo,
)
from the_redhuman_is.models.turnout_calculators import get_delivery_request_bonus
from the_redhuman_is.services.delivery import (
    notifications,
    tariffs,
)
from the_redhuman_is.services.delivery.utils import (
    DESCRIPTIONS,
    DeliveryWorkflowError,
    ObjectNotFoundError,
    can_be_cancelled_with_payment,
    can_override_hours,
    catch_lock_error,
    check_if_can_move,
    confirm_turnout,
    create_private_request,
    delete_turnout,
    ensure_can_be_edited,
    ensure_can_save_timesheet,
    ensure_unclosed_date,
    free_route_number,
    get_request_to_merge,
    get_user_customer_location,
    is_citizenship_migration_ok,
    is_request_paid,
    normalize_driver_name,
    try_assign_operator,
    update_delivery_request_status,
    update_request_timesheets,
    update_suspicion_flag,
    update_turnouts,
    validate_hours,
)
from the_redhuman_is.services.delivery_requests import (
    ConfirmationRequired,
    _deduction_worker,
    create_requests_file,
    customer_location,
)
from the_redhuman_is.services.turnout_calculations import update_turnout_payments
from the_redhuman_is.tasks import (
    import_requests_and_make_report,
    log,
    normalize_address_in_bulk,
    normalize_address,
)


@catch_lock_error
def _request_lock(
        request_id: int,
        customer_id: Optional[int] = None,
        location_id: Optional[int] = None,
) -> DeliveryRequest:
    filter_kwargs = {}
    if customer_id is not None:
        filter_kwargs['customer_id']: customer_id
    if location_id is not None:
        filter_kwargs['location_id']: location_id
    try:
        request = DeliveryRequest.objects.select_for_update(
            nowait=True
        ).filter(
            **filter_kwargs
        ).get(
            pk=request_id
        )
    except DeliveryRequest.DoesNotExist:
        raise ObjectNotFoundError(f'Заявка {request_id} не найдена.')

    ensure_can_be_edited(request)
    return request


@catch_lock_error
def _worker_lock(worker_id: int) -> Worker:
    try:
        return Worker.objects.select_for_update(
            nowait=True
        ).get(
            pk=worker_id
        )
    except Worker.DoesNotExist:
        raise ObjectNotFoundError(f'Работник {worker_id} не найден.')


def _get_item(request_id: int, item_id: int) -> DeliveryItem:
    try:
        return DeliveryItem.objects.get(
            request=request_id,
            pk=item_id,
        )
    except DeliveryItem.DoesNotExist:
        raise DeliveryWorkflowError(
            f'Адрес {item_id} отсутствует в заявке {request_id}.'
        )


@catch_lock_error
def _multiple_worker_lock(worker_ids: List[int]) -> List[Worker]:
    locked_ids = set(
        Worker.objects.select_for_update(
            nowait=True
        ).filter(
            pk__in=worker_ids
        ).values_list(
            'pk',
            flat=True
        )
    )
    not_found = sorted(set(worker_ids) - locked_ids)
    if not_found:
        raise ObjectNotFoundError(
            f'Работники {not_found} не найдены.'
        )
    return list(locked_ids)


def _is_rejected(rw: RequestWorker) -> bool:
    return hasattr(rw, 'workerrejection')


def _is_confirmed(rw: RequestWorker) -> bool:
    return hasattr(rw, 'workerconfirmation')


def _has_turnout(rw: RequestWorker) -> bool:
    return hasattr(rw, 'requestworkerturnout')


def _check_ok_self_assign(
        request_id: int,
        worker_id: int,
) -> None:
    try:
        zone_id = WorkerZone.objects.get(
            worker_id=worker_id
        ).zone_id

        DeliveryRequest.objects.all(
        ).filter_self_assign_ready(
            day=timezone.localdate(),
            zone_id=zone_id,
        ).get(
            pk=request_id
        )
    except (WorkerZone.DoesNotExist, DeliveryRequest.DoesNotExist):
        raise DeliveryWorkflowError(
            f'Заявка {request_id} может быть назначена только диспетчером.'
        )


def _check_start_exists(
        itemworker: ItemWorker,
        worker_id: int,
        item_id: int,
) -> None:
    try:
        itemworker.itemworkerstart
    except ItemWorkerStart.DoesNotExist:
        raise DeliveryWorkflowError(
            f'Работник {worker_id} не отметил прибытие на адрес {item_id}.'
        )


def _check_finish_exists(
        itemworker: ItemWorker,
        worker_id: int,
        item_id: int,
) -> None:
    try:
        itemworker.itemworkerfinish
    except ItemWorkerFinish.DoesNotExist:
        raise DeliveryWorkflowError(
            f'Работник {worker_id} не отметил завершение работы на адресе {item_id}.'
        )


def _check_can_assign_workers(request: DeliveryRequest) -> None:
    if request.delivery_service is None:
        raise DeliveryWorkflowError(f'В заявке {request.pk} не указан тариф.')


def _do_add_request_worker(
        request: DeliveryRequest,
        worker_id: int,
        user: User,
        autoassign: bool = False,
) -> RequestWorker:

    requestworker, created = RequestWorker.objects.get_or_create(
        request_id=request.pk,
        worker_id=worker_id,
        defaults={'author': user}
    )
    if created and autoassign:
        delivery_items = DeliveryItem.objects.with_itemworker_count(
        ).filter(
            request_id=request.pk,
            itemworker_count__lt=F('workers_required'),
        ).values_list('pk', flat=True)
        for item_id in delivery_items:
            ItemWorker.objects.create(
                item_id=item_id,
                requestworker_id=requestworker.pk,
                author=user,
            )
    else:
        WorkerRejection.objects.filter(requestworker=requestworker).delete()
    return requestworker


class WorkerPermissionDenied(PermissionDenied):
    pass


@log
def add_request_worker(
        request_id: int,
        worker_id: int,
        user: User,
) -> RequestWorker:
    """
    добавить грузчика
    """
    with transaction.atomic():
        request = _request_lock(request_id)
        worker = _worker_lock(worker_id)

        self_assigned = hasattr(user, 'workeruser') and user.workeruser.worker_id == worker_id
        if self_assigned:
            if hasattr(worker, 'banned'):
                raise WorkerPermissionDenied('banned')
            if not is_citizenship_migration_ok(worker, request.date):
                raise WorkerPermissionDenied('expired_documents')

        _check_can_assign_workers(request)

        new_assignments = RequestWorker.objects.filter(
            request=request_id,
            worker=worker_id,
            workerconfirmation__isnull=True,
        ).filter_active()

        if self_assigned:
            if not user.is_superuser:
                _check_ok_self_assign(request_id, worker_id)
            check_notify = False
        else:
            check_notify = not new_assignments.exists()

        requestworker = _do_add_request_worker(request, worker_id, user, autoassign=True)

        if not self_assigned:
            try_assign_operator(request_id, user)

        update_delivery_request_status(request, user=user)

        if check_notify:
            check_notify = new_assignments.exists()

    if check_notify:
        notifications.notify_new_request_available(worker_id)

    return requestworker


@log
def confirm_request_worker(
        request_id: int,
        worker_id: int,
        user: User,
) -> WorkerConfirmation:
    """
    подтвердить заявку
    """
    with transaction.atomic():
        request = _request_lock(request_id)
        _worker_lock(worker_id)
        try:
            requestworker = RequestWorker.objects.filter(
                workerrejection__isnull=True
            ).get(
                request_id=request_id,
                worker_id=worker_id,
            )
        except RequestWorker.DoesNotExist:
            raise DeliveryWorkflowError(
                f'Грузчик {worker_id} не назначен на заявку {request_id}.'
            )

        workerconfirmation, created = WorkerConfirmation.objects.get_or_create(
            requestworker_id=requestworker.pk,
            defaults={'author': user}
        )

        update_delivery_request_status(request, user=user)
    if created:
        notifications.notify_driver_worker_assigned(request, worker_id)

    return workerconfirmation


@log
def remove_request_worker(
        request_id: int,
        worker_id: int,
        user: User,
        force_commit: bool = False,
) -> Tuple[Optional[WorkerRejection], List[str], bool]:
    """
    отменить грузчика -
    ("прям удалять" можно только если он не успел подтвердить заявку,
     иначе надо оставлять привязку грузчика к заявке (с пометкой WorkerRejection))
    """
    messages = []
    confirmation_required = False
    try:
        with transaction.atomic():
            request = _request_lock(request_id)
            _worker_lock(worker_id)
            try:
                requestworker = RequestWorker.objects.annotate(
                    has_confirmation=Exists(
                        WorkerConfirmation.objects.filter(
                            requestworker=OuterRef('pk')
                        )
                    ),
                    has_rejection=Exists(
                        WorkerRejection.objects.filter(
                            requestworker=OuterRef('pk')
                        )
                    )
                ).get(
                    request_id=request_id,
                    worker_id=worker_id,
                )
            except RequestWorker.DoesNotExist:
                return None, messages, confirmation_required

            if requestworker.has_rejection:
                return None, messages, confirmation_required

            needs_soft_delete = (
                requestworker.has_confirmation or
                ItemWorkerRejection.objects.filter(
                    itemworker__requestworker=requestworker.pk
                ).exists()
            )
            if needs_soft_delete:
                ItemWorkerFinishConfirmation.objects.filter(
                    itemworkerfinish__itemworker__requestworker=requestworker
                ).delete()
                messages, confirmation_required = delete_turnout(
                    requestworker,
                    user,
                    force_commit
                )
                workerrejection, _ = WorkerRejection.objects.get_or_create(
                    requestworker_id=requestworker.pk,
                    defaults={'author': user}
                )
            else:
                ItemWorker.objects.filter(
                    requestworker=requestworker.pk
                ).delete()
                requestworker.delete()
                workerrejection = None

            if confirmation_required:
                raise ConfirmationRequired

            update_delivery_request_status(request, user=user)

    except ConfirmationRequired:
        return None, messages, confirmation_required
    else:
        return workerrejection, messages, confirmation_required


@log
def create_delivery_item(
        request_id: int,
        interval_begin: datetime.time,
        interval_end: datetime.time,
        code: str,
        mass: float,
        volume: float,
        max_size: float,
        place_count: int,
        shipment_type: str,
        address: str,
        has_elevator: Optional[bool],
        floor: Optional[int],
        carrying_distance: Optional[int],
        workers_required: int,
        confirmed_timepoint: Optional[datetime.time],
        user: User,
        notify_dispatchers: bool = False,
) -> DeliveryItem:
    """
    добавить новый адрес
    """
    with transaction.atomic():
        user_customer, user_location = get_user_customer_location(user)
        delivery_request = _request_lock(
            request_id,
            customer_id=user_customer,
            location_id=user_location
        )

        same_itemcode_today_request = DeliveryItem.objects.filter(
            request__customer=delivery_request.customer,
            request__date=delivery_request.date,
            code=code
        ).values_list(
            'request', flat=True
        ).first()
        if same_itemcode_today_request is not None:
            raise PermissionDenied(
                f'Индекс {code} уже используется в заявке №{same_itemcode_today_request}'
            )

        item = DeliveryItem.objects.create(
            request_id=request_id,
            interval_begin=interval_begin,
            interval_end=interval_end,
            code=code,
            mass=mass,
            volume=volume,
            max_size=max_size,
            place_count=place_count,
            shipment_type=shipment_type,
            address=address,
            address_version=0,
            has_elevator=has_elevator,
            floor=floor,
            carrying_distance=carrying_distance,
            workers_required=workers_required,
            confirmed_timepoint=confirmed_timepoint,
        )

        if not delivery_request.route and delivery_request.deliveryitem_set.count() > 1:
            delivery_request.route = free_route_number(
                delivery_request.customer,
                delivery_request.date
            )
            delivery_request.save(user=user)

        if user_customer is None:
            try_assign_operator(request_id, user)

    normalize_address(item.pk, 0, user)
    update_delivery_request_status(delivery_request, user)

    if notify_dispatchers:
        notifications.notify_new_request(delivery_request)

    return item


def _update_tariff_create_turnouts(
        request: DeliveryRequest,
        requestworkers: List[RequestWorker],
        user: User,
        force_commit: bool
) -> Tuple[List[str], bool]:

    update_delivery_request_status(request, user=user)
    messages, confirmation_required = tariffs.try_to_update_tariff(
        request,
        user,
        force_commit=force_commit,
    )
    for rw in requestworkers:
        rw_status = _get_requestworker_status(rw)
        if rw_status == ItemWorker.COMPLETE:
            _, create_messages, create_confirmation = confirm_turnout(
                rw,
                user,
                use_default_hours=True,
                force_commit=force_commit
            )
            messages.extend(create_messages)
            confirmation_required |= create_confirmation
    return messages, confirmation_required


@log
@catch_lock_error
def move_delivery_item(src_request_id, dest_request_id, item_id, user, force_commit=False):
    """
    переместить адрес между заявками
    """
    messages = []
    confirmation_required = False
    try:
        with transaction.atomic():
            if src_request_id is None:
                try:
                    src_request_id = DeliveryItem.objects.select_for_update(
                        nowait=True
                    ).select_related(
                        'request'
                    ).get(
                        pk=item_id
                    ).request_id
                except DeliveryItem.DoesNotExist:
                    raise ObjectNotFoundError(f"Адрес {item_id} не найден.")

            src_request = _request_lock(src_request_id)
            try:
                item = DeliveryItem.objects.get(
                    request_id=src_request_id,
                    pk=item_id,
                )
            except DeliveryItem.DoesNotExist:
                raise DeliveryWorkflowError(
                    f'Адрес {item_id} отсутствует в заявке {src_request_id}.'
                )

            if src_request_id == dest_request_id:
                raise DeliveryWorkflowError(
                    f'Адрес {item_id} уже в заявке {dest_request_id}.'
                )

            initial_src_req_id = src_request_id
            initial_dest_req_id = dest_request_id

            if dest_request_id is not None:
                dest_request = _request_lock(dest_request_id)
                check_if_can_move(item, src_request, dest_request)
            else:
                dest_request = create_private_request(
                    author=user,
                    customer=src_request.customer,
                    date=src_request.date,
                    driver_name=src_request.driver_name,
                    driver_phones=src_request.driver_phones
                )
                dest_request_id = dest_request.pk

            src_itemworkers = ItemWorker.objects.filter(
                item=item_id
            ).select_related(
                'requestworker__workerrejection',
                'requestworker__workerconfirmation',
                'requestworker__requestworkerturnout',
            ).annotate(
                requestworker_has_records=Exists(
                    ItemWorker.objects.exclude(
                        pk=OuterRef('pk')
                    ).filter(
                        requestworker=OuterRef('requestworker')
                    )
                ),
                requestworker_has_other_items=Exists(
                    ItemWorker.objects.exclude(
                        pk=OuterRef('pk')
                    ).filter(
                        requestworker=OuterRef('requestworker'),
                        requestworker__workerrejection__isnull=True,
                        itemworkerrejection__isnull=True,
                    )
                )
            )
            dest_requestworkers = {
                rw.worker_id: rw
                for rw in RequestWorker.objects.filter(
                    request=dest_request_id
                ).select_related(
                    'workerrejection',
                    'workerconfirmation',
                    'requestworkerturnout',
                )
            }

            src_check_and_create = []
            dest_check_and_create = []
            dest_check_and_remove = []

            for itemworker in src_itemworkers:
                src_requestworker = itemworker.requestworker
                worker_id = itemworker.requestworker.worker_id

                has_other_items = itemworker.requestworker_has_other_items
                has_records = itemworker.requestworker_has_records

                if worker_id not in dest_requestworkers:
                    dest_requestworker = RequestWorker.objects.create(
                        request_id=dest_request_id,
                        worker_id=worker_id,
                        author=user
                    )
                    if _is_rejected(src_requestworker):
                        WorkerRejection.objects.create(
                            requestworker=dest_requestworker,
                            author=user
                        )
                    else:
                        dest_check_and_create.append(dest_requestworker)
                else:
                    dest_requestworker = dest_requestworkers[worker_id]
                    if _is_rejected(src_requestworker) != _is_rejected(dest_requestworker):
                        if _is_rejected(src_requestworker):
                            request_rejected, request_included = src_request_id, dest_request_id
                        else:
                            request_rejected, request_included = dest_request_id, src_request_id
                        raise DeliveryWorkflowError(
                            f'Грузчик {worker_id} исключен из заявки {request_rejected},'
                            f' но присутствует в заявке {request_included}.'
                        )
                    if _has_turnout(dest_requestworker):
                        dest_check_and_remove.append(dest_requestworker)
                    else:
                        dest_check_and_create.append(dest_requestworker)
                if _is_confirmed(src_requestworker):
                    WorkerConfirmation.objects.get_or_create(
                        requestworker=dest_requestworker,
                        defaults={
                            'author': user
                        }
                    )

                itemworker.requestworker = dest_requestworker
                itemworker.save(update_fields=['requestworker'])

                if has_other_items:
                    if not _has_turnout(src_requestworker):
                        src_check_and_create.append(src_requestworker)
                else:
                    if _has_turnout(src_requestworker):
                        removed_messages, removed_confirmation = delete_turnout(
                            src_requestworker,
                            user,
                            force_commit,
                        )
                        messages.extend(removed_messages)
                        confirmation_required |= removed_confirmation
                    if not has_records:
                        if _is_rejected(src_requestworker):
                            src_requestworker.workerrejection.delete()
                        if _is_confirmed(src_requestworker):
                            src_requestworker.workerconfirmation.delete()
                        src_requestworker.delete()

            item.request_id = dest_request_id
            item.save(update_fields=['request'])
            try:  # todo: eventually delete this
                item.deliveryfirstaddress.delete()
            except DeliveryFirstAddress.DoesNotExist:
                pass

            def _update_tariff_turnouts_messages(request, requestworkers):
                m, cr = _update_tariff_create_turnouts(
                    request,
                    requestworkers,
                    user,
                    force_commit
                )
                messages.extend(m)
                nonlocal confirmation_required
                confirmation_required |= cr

            src_item_count = src_request.deliveryitem_set.count()
            if src_item_count > 0:
                if src_item_count == 1:
                    src_request.route = None
                    src_request.save(user=user)

                _update_tariff_turnouts_messages(src_request, src_check_and_create)

            else:
                PrivateDeliveryRequest.objects.filter(request=src_request).delete()
                DriverSms.objects.filter(
                    request=src_request
                ).update(
                    request=dest_request
                )
                src_request.delete()
                src_request_id = None

            if dest_request.route is None and dest_request.deliveryitem_set.count() > 1:
                dest_request.route = free_route_number(
                    dest_request.customer,
                    dest_request.date
                )
                dest_request.save(user=user)

            if dest_request.delivery_service is None and dest_request.active_workers().exists():
                dest_request.delivery_service = tariffs.get_default_tariff(
                    cast(int, src_request.customer_id),
                    src_request.delivery_service.zone,
                    dest_request.route is not None,
                )
                dest_request.save(user=user)

            for requestworker in dest_check_and_remove:
                rw_status = _get_requestworker_status(requestworker)
                if rw_status != ItemWorker.COMPLETE:
                    moved_messages, moved_confirmation = delete_turnout(
                        requestworker,
                        user,
                        force_commit=force_commit
                    )
                    messages.extend(moved_messages)
                    confirmation_required |= moved_confirmation

            _update_tariff_turnouts_messages(dest_request, dest_check_and_create)

            if confirmation_required:
                raise ConfirmationRequired

    except ConfirmationRequired:
        return initial_src_req_id, initial_dest_req_id, messages, confirmation_required

    else:
        return src_request_id, dest_request_id, messages, confirmation_required


@log
def add_item_workers(
        request_id: int,
        item_id: int,
        worker_ids: List[int],
        user: User,
        force_commit: bool = False,
) -> Tuple[Optional[Mapping[int, RequestWorker]], List[str], bool]:
    """
    назначить рабочих на адрес внутри заявки
    """
    messages = []
    confirmation_required = False
    try:
        with transaction.atomic():
            request = _request_lock(request_id)
            item = _get_item(request_id, item_id)
            _multiple_worker_lock(worker_ids)

            if item.workers_required == 0:
                raise DeliveryWorkflowError(
                    f'Адрес отменен. Для добавления грузчика нужно увеличить'
                    f' требуемое количество грузчиков на адресе (сейчас 0).'
                )

            _check_can_assign_workers(request)

            requestworkers = {
                rw.worker_id: rw
                for rw in RequestWorker.objects.filter(
                    workerrejection__isnull=True,
                    request_id=request_id,
                    worker__in=worker_ids
                )
            }

            new_assignments_qs = RequestWorker.objects.filter(
                request=request_id,
                worker__in=worker_ids,
                workerconfirmation__isnull=True,
            ).filter_active(
            ).values_list(
                'worker',
                flat=True
            )

            new_assignments = set(new_assignments_qs)

            messages, confirmation_required = [], False
            for worker_id in worker_ids:
                try:
                    requestworker = requestworkers[worker_id]
                except KeyError:
                    requestworker = _do_add_request_worker(
                        request,
                        worker_id,
                        user,
                        autoassign=False
                    )
                    requestworkers[worker_id] = requestworker

                itemworker, changed_state = ItemWorker.objects.get_or_create(
                    requestworker_id=requestworker.pk,
                    item_id=item_id,
                    defaults={'author': user}
                )
                if not changed_state:
                    changed_state = (
                        'the_redhuman_is.ItemWorkerRejection' in
                        ItemWorkerRejection.objects.filter(
                            itemworker=itemworker
                        ).delete()[1]
                    )

                if changed_state:
                    item_messages, item_confirmation_required = delete_turnout(
                        requestworker,
                        user,
                        force_commit=force_commit
                    )
                    messages.extend(item_messages)
                    confirmation_required |= item_confirmation_required

            if confirmation_required:
                raise ConfirmationRequired

            try_assign_operator(request_id, user)

            update_delivery_request_status(request, user=user)

            new_assignments = sorted(set(new_assignments_qs.all()) - new_assignments)

    except ConfirmationRequired:
        return None, messages, confirmation_required

    else:
        for worker_id in new_assignments:
            notifications.notify_new_request_available(worker_id)

        return requestworkers, messages, confirmation_required


def _get_requestworker_status(requestworker):
    requestworker_status = ItemWorker.objects.filter(
        requestworker=requestworker,
        requestworker__workerrejection__isnull=True,
        itemworkerrejection__isnull=True,
    ).with_status(
    ).aggregate(
        Min('status')
    )['status__min']
    return requestworker_status


def _auto_create_delete_turnout(
        requestworker: RequestWorker,
        user: User,
        force_commit: bool,
) -> Tuple[Optional[TimeSheet], List[str], bool]:

    requestworker_status = _get_requestworker_status(requestworker)
    if requestworker_status == ItemWorker.COMPLETE:
        return confirm_turnout(
            requestworker,
            user,
            use_default_hours=True,
            force_commit=force_commit
        )
    else:
        messages, confirmation_required = delete_turnout(
            requestworker,
            user,
            force_commit=force_commit
        )
        return None, messages, confirmation_required


@log
def remove_item_worker(
        request_id: int,
        item_id: int,
        worker_id: int,
        user: User,
        reason: Optional[str] = None,
        force_commit: bool = False,
) -> Tuple[Optional[ItemWorkerRejection], List[str], bool]:

    """
    снять назначение рабочего на адрес внутри заявки
    ("прям удалять" ItemWorker можно лишь если нет ItemWorkerStart
     или другой доп. информации по адресу,
     иначе - создавать пометку ItemWorkerRejection)
    ---
    пометить пару (грузчик, адрес) как брак
    ---
    пометить пару (грузчик, адрес) как срыв
    """
    messages = []
    confirmation_required = False
    try:
        with transaction.atomic():
            request = _request_lock(request_id)
            item_qs = DeliveryItem.objects.filter(
                request_id=request_id,
                pk=item_id,
            )
            if not item_qs.exists():
                raise DeliveryWorkflowError(
                    f'Адрес {item_id} отсутствует в заявке {request_id}.'
                )
            _worker_lock(worker_id)
            try:
                requestworker = RequestWorker.objects.filter(
                    workerrejection__isnull=True
                ).get(
                    request_id=request_id,
                    worker_id=worker_id,
                )
            except RequestWorker.DoesNotExist:
                raise DeliveryWorkflowError(
                    f'Грузчик {worker_id} не назначен на заявку {request_id}.'
                )

            try:
                itemworker = ItemWorker.objects.get(
                    requestworker_id=requestworker.pk,
                    item_id=item_id,
                )
            except ItemWorker.DoesNotExist:
                if reason is not None:
                    raise DeliveryWorkflowError(
                        f'Грузчик {worker_id} не назначен на адрес {item_id}'
                        f' и не может быть помечен как {reason}.'
                    )
                else:
                    return None, messages, confirmation_required

            if reason is None:
                if ItemWorkerStart.objects.filter(itemworker=itemworker.pk).exists():
                    raise DeliveryWorkflowError(
                        f'У работника {worker_id} есть отметки на адресе {item_id}.'
                        f'Нельзя снять работника с адреса  без указания причины.'
                    )
                else:
                    ItemWorkerRejection.objects.filter(itemworker=itemworker.pk).delete()
                    itemworker.delete()
                    itemworkerrejection = None
            else:
                itemworkerrejection, created = ItemWorkerRejection.objects.update_or_create(
                    itemworker_id=itemworker.pk,
                    defaults={
                        'reason': reason,
                        'author': user
                    }
                )
                ItemWorkerFinishConfirmation.objects.filter(
                    itemworkerfinish__itemworker=itemworker.pk
                ).delete()

            _, messages, confirmation_required = _auto_create_delete_turnout(
                requestworker,
                user,
                force_commit
            )

            if confirmation_required:
                raise ConfirmationRequired

            update_delivery_request_status(request, user)

    except ConfirmationRequired:
        return None, messages, confirmation_required

    else:
        return itemworkerrejection, messages, confirmation_required


@log
def delete_item_worker(
        request_id: int,
        item_id: int,
        worker_id: int,
        user: User,
        force_commit: bool = False,
) -> Tuple[List[str], bool]:
    """
    удалить пару (грузчик, адрес) на случай, если логисты наошибались (чисто для суперюзеров)
    """
    messages = []
    confirmation_required = False
    try:
        with transaction.atomic():
            if not user.is_superuser:
                raise DeliveryWorkflowError('Запрещено удаление назначенного работника.')
            request = _request_lock(request_id)
            item_qs = DeliveryItem.objects.filter(
                request_id=request_id,
                pk=item_id,
            )
            if not item_qs.exists():
                raise DeliveryWorkflowError(
                    f'Адрес {item_id} отсутствует в заявке {request_id}.'
                )
            _worker_lock(worker_id)
            try:
                requestworker = RequestWorker.objects.get(
                    request_id=request_id,
                    worker_id=worker_id,
                )
            except RequestWorker.DoesNotExist:
                raise DeliveryWorkflowError(
                    f'Грузчик {worker_id} не назначен на заявку {request_id}.'
                )
            try:
                itemworker = ItemWorker.objects.get(
                    requestworker_id=requestworker.pk,
                    item_id=item_id,
                )
            except ItemWorker.DoesNotExist:
                pass
            else:
                try:
                    itemworkerstart = itemworker.itemworkerstart
                except ItemWorkerStart.DoesNotExist:
                    pass
                else:
                    ItemWorkerStartConfirmation.objects.filter(
                        itemworkerstart=itemworkerstart.pk
                    ).delete()
                    PhotoRejectionComment.objects.filter(
                        photo__content_type=ContentType.objects.get_for_model(ItemWorkerStart),
                        photo__object_id=itemworkerstart.pk
                    ).delete()
                    Photo.objects.filter(
                        content_type=ContentType.objects.get_for_model(ItemWorkerStart),
                        object_id=itemworkerstart.pk
                    ).delete()
                    ItemWorkerDiscrepancyCheck.objects.filter(
                        itemworkerstart=itemworkerstart.pk
                    ).delete()
                    itemworkerstart.delete()
                try:
                    itemworkerfinish = itemworker.itemworkerfinish
                except ItemWorkerFinish.DoesNotExist:
                    pass
                else:
                    finish_pk = itemworkerfinish.pk
                    turnout_photo = itemworkerfinish.photo_id
                    ItemWorkerFinishConfirmation.objects.filter(
                        itemworkerfinish=itemworkerfinish.pk
                    ).delete()
                    PhotoRejectionComment.objects.filter(
                        photo__content_type=ContentType.objects.get_for_model(ItemWorkerFinish),
                        photo__object_id=itemworkerfinish.pk
                    ).delete()
                    itemworkerfinish.delete()
                    Photo.objects.filter(
                        content_type=ContentType.objects.get_for_model(ItemWorkerFinish),
                        object_id=finish_pk
                    ).delete()
                    if turnout_photo is not None:
                        Photo.objects.filter(
                            pk=turnout_photo
                        ).delete()
                ItemWorkerRejection.objects.filter(itemworker=itemworker).delete()
                itemworker.delete()

            _, messages, confirmation_required = _auto_create_delete_turnout(
                requestworker,
                user,
                force_commit
            )
            if confirmation_required:
                raise ConfirmationRequired

            update_delivery_request_status(request, user)

    except ConfirmationRequired:
        pass

    return messages, confirmation_required


def _make_confirmation_prechecks(
        request_id: int,
        item_id: int,
        worker_id: int,
) -> Tuple[DeliveryRequest, DeliveryItem, ItemWorker, RequestWorker]:

    request = _request_lock(request_id)
    item = _get_item(request_id, item_id)

    _worker_lock(worker_id)
    try:
        requestworker = RequestWorker.objects.filter(
            workerrejection__isnull=True,
        ).select_related(
            'workerconfirmation'
        ).get(
            request_id=request_id,
            worker_id=worker_id,
        )
    except RequestWorker.DoesNotExist:
        raise DeliveryWorkflowError(f'Грузчик {worker_id} не назначен на заявку {request_id}.')

    if not _is_confirmed(requestworker):
        raise DeliveryWorkflowError(
            f'Грузчик {worker_id} не подтвержден на заявке {request_id}.'
        )

    try:
        itemworker = ItemWorker.objects.select_related(
            'itemworkerrejection'
        ).get(
            requestworker_id=requestworker.pk,
            item_id=item_id,
        )
    except ItemWorker.DoesNotExist:
        raise DeliveryWorkflowError(
            f'Грузчик {worker_id} не назначен на адрес {item_id}.'
        )

    if hasattr(itemworker, 'itemworkerrejection'):
        raise DeliveryWorkflowError(
            f'Грузчик {worker_id} снят с адреса {item_id}'
            f' по причине {itemworker.itemworkerrejection.reason}.'
        )

    return request, item, itemworker, requestworker


class SuspiciousLocation(ConfirmationRequired):
    pass


@log
def log_itemworker_start(
        request_id: int,
        item_id: int,
        worker_id: int,
        user: User,
        location: Optional[Location],
        image: Optional[UploadedFile],
        force_commit: bool = False,
) -> ItemWorkerStart:
    """
    подтвердить прибытие рабочего на адрес
    (с опциональной картинкой и геолокацией, как сейчас)
    """
    with transaction.atomic():
        request, item, itemworker, requestworker = _make_confirmation_prechecks(
            request_id,
            item_id,
            worker_id
        )
        try:
            itemworkerstart = itemworker.itemworkerstart
        except ItemWorkerStart.DoesNotExist:
            itemworkerstart = ItemWorkerStart.objects.create(
                itemworker_id=itemworker.pk,
                location=location,
                author=user
            )
        else:
            start_confirmation = ItemWorkerStartConfirmation.objects.filter(
                itemworkerstart=itemworkerstart
            )
            if start_confirmation.exists():
                raise DeliveryWorkflowError(
                    f'Адрес {item_id} для грузчика {worker_id} уже подтвержден.'
                )
            itemworkerstart.location = location
            itemworkerstart.save(update_fields=['location'])

        distance = update_suspicion_flag(item, itemworkerstart)
        if itemworkerstart.is_suspicious:
            if not force_commit:
                raise SuspiciousLocation(distance)
            else:
                notify_suspicious = True
        else:
            notify_suspicious = False

        if image is not None:
            add_photo(itemworkerstart, image)

        if not itemworkerstart.is_suspicious:
            ItemWorkerStartConfirmation.objects.create(
                itemworkerstart=itemworkerstart,
                author=user,
            )

        update_delivery_request_status(request, user=user)

    if notify_suspicious:
        notifications.notify_new_suspicious_photo(request, requestworker.worker)

    return itemworkerstart


def _update_finish_photo(event_id: int) -> int:
    """
    This won't find the timesheet-facing photo.
    """
    current_finish_photo = ItemWorkerFinish.objects.values_list(
        'photo',
        flat=True
    ).get(pk=event_id)
    latest_valid_photo = Photo.objects.filter(
        photorejectioncomment__isnull=True,
        content_type=ContentType.objects.get_for_model(ItemWorkerFinish),
        object_id=event_id
    ).order_by(
        'timestamp'
    ).values_list(
        'pk',
        flat=True
    ).last()
    if current_finish_photo != latest_valid_photo:
        ItemWorkerFinish.objects.filter(
            pk=event_id
        ).update(
            photo=latest_valid_photo
        )
    return latest_valid_photo


def _reject_accept_event_photo(
        request_id: int,
        photo_id: int,
        is_valid: int,
        user: User,
        comment: Optional[str],
        EventModel,
        event_not_found_message: str,
        force_commit: bool = False,
) -> Tuple[PhotoRejectionComment, int, int, List[str], bool]:
    """
    отменить фото старта или финиша, убрать отмену (служебная функция)
    """
    messages, confirmation_required = [], False
    try:
        with transaction.atomic():
            request = _request_lock(request_id)
            event_qs = EventModel.objects.values_list(
                'pk',
                'itemworker__requestworker__request',
                'itemworker__item',
                'itemworker__requestworker__worker',
                'itemworker__requestworker__workerrejection',
                'itemworker__itemworkerrejection__reason'
            )
            try:
                photo = Photo.objects.get(
                    pk=photo_id,
                    content_type=ContentType.objects.get_for_model(EventModel)
                )
                event_data = event_qs.get(pk=photo.object_id)
            except Photo.DoesNotExist:
                if EventModel is ItemWorkerFinish:
                    try:
                        photo = Photo.objects.get(
                            pk=photo_id,
                            content_type=ContentType.objects.get_for_model(TimeSheet)
                        )
                        event_data = event_qs.get(photo=photo_id)
                    except Photo.DoesNotExist:
                        raise ObjectNotFoundError(f'Фото {photo_id} не найдено.')
                else:
                    raise ObjectNotFoundError(f'Фото {photo_id} не найдено.')
            except EventModel.DoesNotExist:
                raise ObjectNotFoundError(event_not_found_message.format(photo_id))

            (
                event_id,
                request_id_check,
                item_id,
                worker_id,
                worker_rejection_id,
                itemworker_rejection_reason,
            ) = event_data

            if request_id != request_id_check:
                raise DeliveryWorkflowError(
                    f'Фото {photo_id} отсутствует в заявке {request_id}.'
                )
            if worker_rejection_id is not None:
                raise DeliveryWorkflowError(
                    f'Грузчик {worker_id} не назначен на заявку {request_id}.'
                )
            if itemworker_rejection_reason is not None:
                raise DeliveryWorkflowError(
                    f'Грузчик {worker_id} снят с адреса {item_id}'
                    f' по причине {itemworker_rejection_reason}.'
                )

            if is_valid:
                changed = (
                    'the_redhuman_is.PhotoRejectionComment' in
                    PhotoRejectionComment.objects.filter(
                        photo=photo
                    ).delete()[1]
                )
                photorejectioncomment = None
            else:
                if comment is None:
                    raise DeliveryWorkflowError('Для отклонения фото требуется комментарий.')
                photorejectioncomment, changed = PhotoRejectionComment.objects.update_or_create(
                    photo=photo,
                    defaults={
                        'rejection_comment': comment,
                        'author': user,
                    }
                )
                if not changed:
                    return photorejectioncomment, item_id, worker_id, [], False
                ItemWorkerFinishConfirmation.objects.filter(
                    itemworkerfinish__itemworker__item=item_id,
                    itemworkerfinish__itemworker__requestworker__worker=worker_id
                ).delete()
                if EventModel is ItemWorkerStart:
                    ItemWorkerStartConfirmation.objects.filter(
                        itemworkerstart=photo.object_id
                    ).delete()
                requestworker = RequestWorker.objects.select_related(
                    'request'
                ).get(
                    request=request_id,
                    worker=worker_id
                )
                messages, confirmation_required = delete_turnout(
                    requestworker,
                    user,
                    force_commit=force_commit
                )
                if confirmation_required:
                    raise ConfirmationRequired
            if changed and EventModel is ItemWorkerFinish:
                _update_finish_photo(event_id)

            update_delivery_request_status(request, user)

    except ConfirmationRequired:
        pass

    else:
        if not is_valid and changed:
            notifications.notify_photo_rejected(worker_id, comment)

    return photorejectioncomment, item_id, worker_id, messages, confirmation_required


@log
def reject_accept_itemworker_start_photo(
        request_id: int,
        photo_id: int,
        is_valid: bool,
        user: User,
        comment: Optional[str] = None,
        force_commit: bool = False
) -> Tuple[PhotoRejectionComment, int, int, List[str], bool]:
    """
    отменить селфи (из-за недостаточного качества)
    убрать отмену селфи
    """
    return _reject_accept_event_photo(
        request_id,
        photo_id,
        is_valid,
        user,
        comment,
        ItemWorkerStart,
        'Отметка о прибытии с фото {} не найдена.',
        force_commit=force_commit
    )


@log
def confirm_unconfirm_itemworker_start(
        request_id: int,
        item_id: int,
        worker_id: int,
        is_valid: bool,
        user: User,
        force_commit: bool = False,
) -> Tuple[ItemWorkerStartConfirmation, List[str], bool]:
    """
    подтвердить прибытие на адрес (селфи)
    снять подтверждение
    """
    messages, confirmation_required = [], False
    try:
        with transaction.atomic():
            request, item, itemworker, requestworker = _make_confirmation_prechecks(
                request_id,
                item_id,
                worker_id,
            )
            _check_start_exists(itemworker, worker_id, item_id)

            if is_valid:
                def _is_start_suspicious(itemworkerstart: ItemWorkerStart) -> bool:
                    try:
                        is_ok = itemworkerstart.itemworkerdiscrepancycheck.is_ok
                        if is_ok is not None:
                            return not is_ok
                    except ItemWorkerDiscrepancyCheck.DoesNotExist:
                        pass
                    return itemworkerstart.is_suspicious

                if _is_start_suspicious(itemworker.itemworkerstart):
                    raise DeliveryWorkflowError(
                        'Нельзя подтвердить адрес с расхождением координат.'
                    )

                startconfirmation, created = ItemWorkerStartConfirmation.objects.get_or_create(
                    itemworkerstart=itemworker.itemworkerstart,
                    defaults={
                        'author': user,
                    }
                )
            else:
                ItemWorkerFinishConfirmation.objects.filter(
                    itemworkerstart__itemworker=itemworker
                ).delete()
                ItemWorkerStartConfirmation.objects.filter(
                    itemworkerstart=itemworker.itemworkerstart
                ).delete()
                messages, confirmation_required = delete_turnout(
                    requestworker,
                    user,
                    force_commit
                )
                startconfirmation = None
                if confirmation_required:
                    raise ConfirmationRequired

            update_delivery_request_status(request, user=user)

    except ConfirmationRequired:
        pass
    return startconfirmation, messages, confirmation_required


@log
def log_itemworker_finish(
        request_id: int,
        item_id: int,
        worker_id: int,
        user: User,
        location: Optional[Location],
        image,
) -> ItemWorkerFinish:
    """
    приложить фото накладной (накладная теперь вместо табеля)
    """
    with transaction.atomic():
        request, item, itemworker, _ = _make_confirmation_prechecks(
            request_id,
            item_id,
            worker_id
        )

        if not ItemWorkerStart.objects.filter(itemworker=itemworker).exists():
            raise DeliveryWorkflowError(
                f'Нельзя завершить работу по адресу {item_id},'
                f' для которого отсутствует отметка о начале работы.'
            )

        try:
            itemworkerfinish = itemworker.itemworkerfinish
        except ItemWorkerFinish.DoesNotExist:
            itemworkerfinish = ItemWorkerFinish.objects.create(
                itemworker_id=itemworker.pk,
                location=location,
                author=user
            )
        else:
            finish_confirmation = ItemWorkerFinishConfirmation.objects.filter(
                itemworkerfinish=itemworkerfinish
            ).first()
            if finish_confirmation is not None:
                raise DeliveryWorkflowError(
                    f'Адрес {item_id} для грузчика {worker_id} уже подтвержден.'
                )
            itemworkerfinish.location = location

        photo = add_photo(itemworkerfinish, image)
        itemworkerfinish.photo = photo
        itemworkerfinish.save(update_fields=['location', 'photo'])

        update_delivery_request_status(request, user=user)

    notifications.notify_photo_attached(request, item, itemworker)

    return itemworkerfinish


@log
def reject_accept_itemworker_finish_photo(
        request_id: int,
        photo_id: int,
        is_valid: bool,
        user: User,
        comment: Optional[str] = None,
        force_commit: bool = False,
):
    """
    отменить фото накладной (для возможности перефоткать)
    убрать отмену фото накладной
    """
    return _reject_accept_event_photo(
        request_id,
        photo_id,
        is_valid,
        user,
        comment,
        ItemWorkerFinish,
        'Отметка о завершении работы с фото {} не найдена.',
        force_commit=force_commit
    )


@log
def confirm_unconfirm_itemworker_finish(
        request_id: int,
        item_id: int,
        worker_id: int,
        is_valid: bool,
        user: User,
        hours: Optional[Decimal] = None,
        force_commit: bool = False,
):
    """
    подтвердить завершение работы на адресе
    снять подтверждение
    """
    messages = []
    confirmation_required = False
    try:
        with transaction.atomic():
            request, item, itemworker, requestworker = _make_confirmation_prechecks(
                request_id,
                item_id,
                worker_id,
            )
            _check_finish_exists(itemworker, worker_id, item_id)

            if is_valid:
                if request.delivery_service is None:
                    raise DeliveryWorkflowError(f'Для заявки {request.pk} не установлен тариф.')

                if not ItemWorkerStartConfirmation.objects.filter(
                    itemworkerstart__itemworker=itemworker
                ).exists():
                    raise DeliveryWorkflowError(
                        'Для подтверждения завершения работы на адресе'
                        ' необходимо подтверждение начала работы.'
                    )

                if itemworker.itemworkerfinish.photo is None:
                    raise DeliveryWorkflowError(
                        f'Для подтверждения завершения работы на адресе'
                        f' необходимо фото накладной.'
                    )

                finishconfirmation, _ = ItemWorkerFinishConfirmation.objects.get_or_create(
                    itemworkerfinish=itemworker.itemworkerfinish,
                    defaults={
                        'author': user,
                    }
                )
                unclosed_items = ItemWorker.objects.filter(
                    requestworker=itemworker.requestworker,
                ).exclude(
                    itemworkerfinish__itemworkerfinishconfirmation__isnull=False
                ).exclude(
                    itemworkerrejection__isnull=False
                )
                if not unclosed_items.exists():
                    _, messages, confirmation_required = confirm_turnout(
                        itemworker.requestworker,
                        user,
                        hours
                    )
                elif hours is not None:
                    raise DeliveryWorkflowError(
                        "Для подтверждения промежуточного адреса "
                        "'hours' указывать не следует."
                    )

            else:
                ItemWorkerFinishConfirmation.objects.filter(
                    itemworkerfinish=itemworker.itemworkerfinish.pk
                ).delete()
                messages, confirmation_required = delete_turnout(
                    itemworker.requestworker,
                    user,
                    force_commit
                )
                finishconfirmation = None

            if confirmation_required:
                raise ConfirmationRequired

            update_delivery_request_status(request, user=user)

    except ConfirmationRequired:
        pass

    return finishconfirmation, messages, confirmation_required


@log
def create_delivery_request(
        user,
        customer_id,
        location_id,
        date,
        driver_name,
        driver_phones,
        items,
        request_id=None,
        merge=True,
        notify_dispatchers=True,
):

    with transaction.atomic():
        user_customer, user_location = get_user_customer_location(user)

        driver_phones_str = ', '.join(sorted(driver_phones))

        if user_customer is not None and customer_id != user_customer:
            raise PermissionDenied(
                'У пользователя нет прав создавать заявки для этого клиента.'
            )

        if user_location is not None:
            if location_id is None:
                location_id = user_location
            elif location_id != user_location:
                raise PermissionDenied(
                    'У пользователя нет прав создавать заявки для этого филиала.'
                )
        try:
            customer = Customer.objects.get(pk=customer_id)
        except Customer.DoesNotExist:
            raise ObjectNotFoundError(f'Клиент {customer_id} не существует.')
        if location_id is not None:
            try:
                location = CustomerLocation.objects.filter(
                    customer_id_id=customer_id
                ).get(pk=location_id)
            except CustomerLocation.DoesNotExist:
                raise ObjectNotFoundError(f'У клиента {customer_id} нет филиала {location_id}.')
        else:
            location = None

        item_codes = [item['code'] for item in items]
        duplicate_code_item = DeliveryItem.objects.filter(
            request__customer=customer,
            request__date=date,
            code__in=item_codes
        ).first()
        if duplicate_code_item is not None:
            raise DeliveryWorkflowError(
                f'Индекс {duplicate_code_item.code} уже используется'
                f' в заявке №{duplicate_code_item.request_id}.'
            )

        if request_id is not None:
            try:
                delivery_request = DeliveryRequest.objects.select_for_update(
                    of=('self',)
                ).filter(
                    customer=customer_id,
                    location=location_id,
                ).get(
                    pk=request_id
                )
            except DeliveryRequest.DoesNotExist:
                raise ObjectNotFoundError(f'Заявка {request_id} не найдена.')
            ensure_can_be_edited(delivery_request)

        else:
            if location_id is not None:
                ensure_unclosed_date(location_id, date)
            delivery_request = None
            if merge:
                delivery_request = get_request_to_merge(
                    customer,
                    date,
                    driver_name,
                    driver_phones_str,
                    location
                )
            if delivery_request is None:
                delivery_request = create_private_request(
                    author=user,
                    customer=customer,
                    location=location,
                    date=date,
                    driver_name=driver_name,
                    driver_phones=driver_phones_str,
                )
            else:
                fields_to_update = []
                if not delivery_request.driver_name and driver_name:
                    delivery_request.driver_name = driver_name
                    fields_to_update.append('driver_name')
                if not delivery_request.driver_phones and driver_phones:
                    delivery_request.driver_phones = driver_phones
                    fields_to_update.append('driver_phones')
                if fields_to_update:
                    delivery_request.save(user=user, update_fields=fields_to_update)
            request_id = delivery_request.pk

        items_created = []
        for item in items:
            new_item = DeliveryItem.objects.create(
                request_id=delivery_request.id,
                **item
            )
            items_created.append(new_item)

        if not delivery_request.route and delivery_request.deliveryitem_set.count() > 1:
            delivery_request.route = free_route_number(
                delivery_request.customer,
                delivery_request.date
            )
            delivery_request.save(user=user)

        if user_customer is None:
            try_assign_operator(request_id, user)

    normalize_address_in_bulk([item.pk for item in items_created], delivery_request.pk, 0, user)

    if notify_dispatchers:
        notifications.notify_new_request(delivery_request)

    return delivery_request


@log
def set_worker_hours(request_id, worker_id, user, hours=None, force_commit=False):
    try:
        with transaction.atomic():
            request = _request_lock(request_id)
            _worker_lock(worker_id)
            try:
                requestworkerturnout = RequestWorkerTurnout.objects.filter(
                    requestworker__request=request_id,
                    requestworker__worker=worker_id,
                ).select_related(
                    'workerturnout',
                    'requestworker',
                ).get(
                )
            except RequestWorkerTurnout.DoesNotExist:
                raise DeliveryWorkflowError(
                    f'У работника {worker_id} отсутствует выход на заявке {request_id}.'
                )
            turnout = requestworkerturnout.workerturnout

            turnout.hours_worked = validate_hours(
                requestworkerturnout.requestworker,
                hours,
                override=can_override_hours(user)
            )
            turnout.save()

            messages, confirmation_required = update_turnout_payments(
                turnout.pk,
                user,
                _deduction_worker(request),
                force_commit=force_commit
            )
            if confirmation_required:
                raise ConfirmationRequired

    except ConfirmationRequired:
        return None, messages, confirmation_required

    return turnout, messages, confirmation_required


# Delivery Item updates

def _update_workers_required(
        request: DeliveryRequest,
        item: DeliveryItem,
        workers_required: int,
        user: User,
        force_commit: bool = False,
        user_customer: Optional[int] = None,
) -> Tuple[List[str], bool]:

    messages = []
    confirmation_required = False

    if workers_required == 0 and user_customer is not None:
        raise DeliveryWorkflowError(
            'Нельзя вручную удалять адреса. Обратитесь к администраторам.'
        )
    prev_value = item.workers_required
    item.workers_required = workers_required
    item.save(update_fields=['workers_required'])

    if item.workers_required == 0:
        itemworkers = ItemWorker.objects.select_related(
            'requestworker__workerrejection',
            'requestworker__requestworkerturnout',
        ).filter(
            item=item
        ).annotate(
            requestworker_has_other_items=Exists(
                ItemWorker.objects.exclude(
                    pk=OuterRef('pk')
                ).filter(
                    requestworker=OuterRef('requestworker')
                )
            ),
        )

        may_be_complete = []

        for itemworker in itemworkers:
            ItemWorkerRejection.objects.get_or_create(
                itemworker_id=itemworker.pk,
                defaults={
                    'reason': ItemWorkerRejection.CANCELLED,
                    'author': user
                }
            )
            if hasattr(itemworker.requestworker, 'workerrejection'):
                continue
            if itemworker.requestworker_has_other_items:
                if not hasattr(itemworker.requestworker, 'requestworkerturnout'):
                    may_be_complete.append(itemworker.requestworker)
            elif hasattr(itemworker.requestworker, 'requestworkerturnout'):
                delete_messages, delete_confirmation = delete_turnout(
                    itemworker.requestworker,
                    user,
                    force_commit=force_commit
                )
                messages.extend(delete_messages)
                confirmation_required |= delete_confirmation

        tariff_messages, tariff_confirmation = _update_tariff_create_turnouts(
            request,
            may_be_complete,
            user,
            force_commit,
        )
        messages.extend(tariff_messages)
        confirmation_required |= tariff_confirmation

    elif prev_value == 0:
        messages, confirmation_required = tariffs.try_to_update_tariff(
            request,
            user,
            force_commit=force_commit
        )

    update_delivery_request_status(request, user=user)

    return messages, confirmation_required


def _update_address(delivery_item, address):
    if delivery_item.address == address:
        return delivery_item
    delivery_item.address_version += 1
    delivery_item.address = address
    delivery_item.save(update_fields=['address', 'address_version'])
    return [], False


def _update_time_interval(delivery_item, value):
    delivery_item.interval_begin, delivery_item.interval_end = value
    delivery_item.save(update_fields=['interval_begin', 'interval_end'])
    return [], False


def _update_confirmed_timepoint(
        request: DeliveryRequest,
        delivery_item: DeliveryItem,
        value: Optional[datetime.time],
        user: User,
        force_commit: bool = False,
        user_customer: Optional[int] = None,
) -> Tuple[List[str], bool]:

    if user_customer is not None:
        raise PermissionDenied('Редактирование времени подачи запрещено.')

    prev_timepoint = request.confirmed_timepoint
    prev_bonus = get_delivery_request_bonus(request)

    delivery_item.confirmed_timepoint = value
    delivery_item.save(update_fields=['confirmed_timepoint'])

    delattr(request, 'confirmed_timepoint')
    if prev_timepoint == request.confirmed_timepoint:
        return [], False
    return update_turnouts(request, user, prev_bonus, force_commit)


@log
def update_delivery_item(
        request_id: int,
        item_id: int,
        field: str,
        value: Any,
        user: User,
        force_commit: bool = False
) -> Tuple[DeliveryItem, List[str], bool]:

    item_tariff_fields = {
        'mass',
        'floor',
        'volume',
        'max_size',
        'place_count',
        'has_elevator',
        'shipment_type',
        'workers_required',
        'carrying_distance',
        'confirmed_timepoint',
    }
    item_fields = item_tariff_fields | {
        'interval_begin',
        'interval_end',
        'time_interval',
        'code',
        'address',
    }

    if field not in item_fields:
        raise ValueError('Некорректное имя поля.')

    messages = []
    confirmation_required = False
    try:
        with transaction.atomic():
            user_customer, user_location = get_user_customer_location(user)

            request = _request_lock(
                request_id,
                customer_id=user_customer,
                location_id=user_location,
            )
            item = _get_item(request_id, item_id)

            if user_customer is None:
                if (
                    field == 'code' and
                    not user.is_superuser and
                    not user.groups.filter(name='Доставка-руководитель').exists()
                ):
                    raise PermissionDenied(
                        'Для редактирования индекса недостаточно прав.'
                        ' Обратитесь к руководителю.'
                    )
            elif (
                request.status != DeliveryRequest.NEW and
                field not in ('floor', 'has_elevator', 'carrying_distance')
            ):
                raise PermissionDenied('Редактировать это поле можно только в новой заявке.')

            if field == 'time_interval':
                prev_value = item.interval_begin, item.interval_end
            else:
                prev_value = getattr(item, field)

            if prev_value == value:
                return item, [], False

            if field == 'confirmed_timepoint':
                prev_timepoint = request.confirmed_timepoint
            else:
                prev_timepoint = None

            if field == 'address':
                messages, confirmation_required = _update_address(item, value)

            elif field == 'workers_required':
                messages, confirmation_required = _update_workers_required(
                    request,
                    item,
                    value,
                    user,
                    force_commit,
                    user_customer,
                )

            elif field == 'time_interval':
                messages, confirmation_required = _update_time_interval(item, value)

            elif field == 'confirmed_timepoint':
                messages, confirmation_required = _update_confirmed_timepoint(
                    request,
                    item,
                    value,
                    user,
                    force_commit,
                    user_customer,
                )

            else:
                if field == 'code':
                    duplicate_code_item = DeliveryItem.objects.filter(
                        request__customer=request.customer,
                        request__date=request.date,
                        code=value
                    ).first()
                    if duplicate_code_item is not None:
                        raise ValidationError(
                            f'Индекс {duplicate_code_item.code} уже используется'
                            f' в заявке №{duplicate_code_item.request_id}'
                        )

                setattr(item, field, value)
                item.save(update_fields=[field])

            if (
                    field in item_tariff_fields and
                    field not in ['workers_required', 'confirmed_timepoint']  # already updated
            ):
                messages, confirmation_required = update_turnouts(
                    request,
                    user,
                    force_commit=force_commit
                )

            if confirmation_required:
                raise ConfirmationRequired
            else:
                if field == 'confirmed_timepoint':
                    update_delivery_request_status(request, user=user)

    except ConfirmationRequired:
        pass

    if field == 'address':
        normalize_address(item.pk, item.address_version, user=user)
    elif field == 'workers_required' and item.workers_required == 0:
        notifications.notify_removed_item(request, item)

    if user_customer is not None and value != prev_value:
        notifications.notify_updated(request, item, field, prev_value, value)

    if field == 'confirmed_timepoint':
        if prev_timepoint is None and request.confirmed_timepoint is not None:
            notifications.notify_unassigned_request_available(request)

    return item, messages, confirmation_required


# Delivery Request updates

def _update_customer_confirmation(
        request,
        is_confirmed,
        user,
        force_commit=True,
        user_customer=None
):
    if not user.is_superuser and user_customer is None:
        raise PermissionDenied('Для редактирования обратитесь к администраторам.')
    if request.status not in DeliveryRequest.SUCCESS_STATUSES:
        raise PermissionDenied(
            'Подтверждать или отклонять можно только заявку в статусах "Выполнена" '
            'или "Отмена с оплатой".'
        )
    if is_confirmed:
        _, created = DeliveryRequestConfirmation.objects.get_or_create(
            request=request,
            defaults={
                'author': user,
            }
        )
        prev_value = not created
    else:
        prev_value = (
            'the_redhuman_is.DeliveryRequestConfirmation' in
            DeliveryRequestConfirmation.objects.filter(
                request=request
            ).delete()[1]
        )
    return [], False, prev_value


def _update_date(request, date, user, force_commit=False, user_customer=None):
    if user_customer is not None and request.status != DeliveryRequest.NEW:
        raise PermissionDenied('Редактировать можно только новую заявку.')
    prev_value = date

    ensure_can_save_timesheet(request)
    request.date = date
    ensure_can_save_timesheet(request, check_if_can_create_reconciliation=True)

    request.save(user=user)
    update_request_timesheets(request)
    return update_turnouts(request, user, force_commit=force_commit) + (prev_value,)


def _update_location_precheck(request):
    # Todo: GT-297
    if request.customer_id == 21 and request.location_id is not None:
        raise PermissionDenied(
            'У этого клиента нельзя менять филиал вручную, обратитесь к администрации.'
        )
    if is_request_paid(request):
        raise PermissionDenied(
            'Нельзя менять филиал у заявки, которая оплачена (даже частично).'
        )
    if request.active_workers().exists():
        raise PermissionDenied(
            'Нельзя менять филиал, если назначены работники.'
        )


def _update_location(request, location_id, user, force_commit=False, user_customer=None):
    prev_value = request.location_id
    if user_customer is not None:
        raise PermissionDenied('Редактирование филиала запрещено.')

    if request.location_id == location_id:
        return [], False, prev_value
    if not user.is_superuser:
        # Todo: GT-297
        _update_location_precheck(request)

    try:
        location = CustomerLocation.objects.get(
            pk=location_id,
            customer_id_id=request.customer_id
        )
    except CustomerLocation.DoesNotExist:
        raise ObjectNotFoundError(
            f'У клиента {request.customer_id} нет филиала {location_id}.'
        )

    prev_bonus = get_delivery_request_bonus(request)

    ensure_can_save_timesheet(request)
    request.location = location
    ensure_can_save_timesheet(request, check_if_can_create_reconciliation=True)

    if request.delivery_service is not None:
        zone_center = LocationZoneGroup.objects.filter(
            location=request.location
        ).values_list(
            'zone_group__code',
            flat=True,
        ).first()
        request.delivery_service = tariffs.get_tariff_for_zone(
            request.customer_id,
            zone_center,
            request.route is not None,
        )

    request.save(user=user)
    update_request_timesheets(request)

    return update_turnouts(request, user, prev_bonus, force_commit) + (prev_value,)


def _update_service(
        request: DeliveryRequest,
        service_id: Optional[int],
        user: User,
        force_commit: bool = False,
        user_customer: Optional[int] = None,
):
    if user_customer is not None:
        raise PermissionDenied(
            'Редактирование тарифа запрещено.'
        )
    else:
        try_assign_operator(request.pk, user)

    prev_value = request.delivery_service_id
    if request.delivery_service_id == service_id:
        return [], False, prev_value

    # # GT-869
    # if (
    #     request.customer_id == 21 and
    #     request.delivery_service_id is not None and
    #     not (
    #         user.is_superuser or
    #         user.groups.filter(name='Доставка-проверяющий').exists()
    #     )
    # ):
    #     raise PermissionDenied(
    #         'У этого клиента нельзя менять тариф вручную, обратитесь к администрации.'
    #     )

    prev_bonus = get_delivery_request_bonus(request)
    location_changed = False

    if service_id is None:
        if request.active_workers().exists():
            raise PermissionDenied('Нельзя сбрасывать тариф, если назначены работники.')
        request.delivery_service_id = None
    else:
        try:
            request.delivery_service = DeliveryService.objects.get(
                pk=service_id,
                service__customer_id=request.customer_id
            )
        except DeliveryService.DoesNotExist:
            raise ObjectNotFoundError(
                f'У клиента {request.customer_id} нет тарифа {service_id}.'
            )
        location = customer_location(
            request.customer,
            request.delivery_service.zone
        )
        if location.pk != request.location_id:
            _update_location_precheck(request)
            ensure_can_save_timesheet(request)
            request.location = location
            ensure_can_save_timesheet(request, check_if_can_create_reconciliation=True)
            location_changed = True

    request.save(user=user)
    if location_changed:
        update_request_timesheets(request)

    return update_turnouts(request, user, prev_bonus, force_commit) + (prev_value,)


def _update_status(request, status, user, force_commit=False, user_customer=None):
    messages, confirmation_required = [], False
    prev_value = request.status
    if user_customer is not None:
        if status == DeliveryRequest.CANCELLED:
            if request.status != DeliveryRequest.NEW:
                raise PermissionDenied(
                    'Отменить можно только новую заявку.'
                )
        elif status != DeliveryRequest.CANCELLED_WITH_PAYMENT:
            raise PermissionDenied(
                'Вручную можно установить только следующие статусы:'
                ' "Отмена" и "Отмена с оплатой".'
            )
    else:
        try_assign_operator(request.pk, user)

    if status not in DeliveryRequest.MANUAL_STATUSES:
        raise PermissionDenied(
            'Вручную можно установить только следующие статусы: "Новая", "Не принята в работу",'
            ' "Отмена", "Перезвонит сам", "Нет ответа" и "Отмена с оплатой".'
        )

    if status == request.status:
        return [], False, prev_value

    if user_customer is None:
        if (
            status in (DeliveryRequest.CANCELLED, DeliveryRequest.FAILED) and
            not request.comment
        ):
            raise PermissionDenied(
                'Нельзя установить статус "Отмена" или "Срыв заявки", не заполнив примечание.'
            )

    if status in DeliveryRequest.FAIL_STATUSES:
        if is_request_paid(request):
            raise PermissionDenied('Нельзя отменять заявку, которая оплачена (даже частично).')

    if status == DeliveryRequest.CANCELLED_WITH_PAYMENT:
        if not can_be_cancelled_with_payment(request):
            raise PermissionDenied(
                'Нельзя установить статус "Отмена с оплатой" - '
                'не указаны рабочие, или услуга, или время прибытия'
            )

    request.status = status
    request.status_description = DESCRIPTIONS[status]
    request.save(user=user)

    if status == DeliveryRequest.CANCELLED_WITH_PAYMENT:
        active_workers = RequestWorker.objects.annotate(
            is_active=Exists(
                ItemWorker.objects.filter(
                    requestworker=OuterRef('pk'),
                    itemworkerrejection__isnull=True
                )
            )
        ).filter(
            request=request,
            workerrejection__isnull=True,
            is_active=True,
        )
        for requestworker in active_workers:
            _, worker_messages, worker_confirmation_required = confirm_turnout(
                requestworker,
                user,
                use_default_hours=True,
                force_commit=force_commit
            )
            messages.extend(worker_messages)
            confirmation_required |= worker_confirmation_required

    elif prev_value == DeliveryRequest.CANCELLED_WITH_PAYMENT:
        requestworkers = request.requestworker_set.all(
        ).filter(
            workerrejection__isnull=True
        )
        for requestworker in requestworkers:
            requestworker_status = _get_requestworker_status(requestworker)
            if requestworker_status != ItemWorker.COMPLETE:
                incomplete_messages, incomplete = delete_turnout(
                    requestworker,
                    user,
                    force_commit=force_commit
                )
                messages.extend(incomplete_messages)
                confirmation_required |= incomplete
        update_messages, update_confirmation = update_turnouts(
            request,
            user,
            force_commit=force_commit
        )
        messages.extend(update_messages)
        confirmation_required |= update_confirmation

    return messages, confirmation_required, prev_value


def _update_operator(request, value, user, force_commit=False, user_customer=None):
    if user_customer is not None:
        raise PermissionDenied('Редактирование оператора запрещено.')

    created = try_assign_operator(request.pk, user)
    if not created:
        raise DeliveryWorkflowError('У заявки уже есть владелец. Обновите страницу.')
    return [], False, None


def _update_customer(
        request: DeliveryRequest,
        customer_id: int,
        user: User,
        force_commit: bool = False,
        user_customer: Optional[int] = None
) -> Tuple[List[str], bool, int]:

    if user_customer is not None:
        raise PermissionDenied('Редактирование клиента запрещено.')

    prev_value = cast(int, request.customer_id)

    if prev_value == customer_id:
        return [], False, prev_value

    try:
        customer = Customer.objects.get(pk=customer_id)
    except Customer.DoesNotExist:
        raise ObjectNotFoundError(f'Клиент {customer_id} не найден.')

    ensure_can_save_timesheet(request)

    request.customer_id = customer_id

    if request.location is not None:
        try:
            zone_code = LocationZoneGroup.objects.get(
                location=request.location
            ).zone_group.code
            request.location = customer_location(customer, zone_code)
        except LocationZoneGroup.DoesNotExist:
            request.location = CustomerLocation.objects.filter(
                customer_id=customer
            ).order_by('pk').first()

    ensure_can_save_timesheet(request, check_if_can_create_reconciliation=True)

    prev_bonus = get_delivery_request_bonus(request)

    if request.delivery_service is not None:
        prev_service = request.delivery_service
        # Todo: min mass
        new_service = DeliveryService.objects.filter(
            zone=prev_service.zone,
            is_for_united_request=prev_service.is_for_united_request,
            service__customer=customer
        ).first()
        if new_service is None:
            raise DeliveryWorkflowError(
                'У клиента "{}" нет услуги для зоны "{}" для {}.'.format(
                    customer,
                    prev_service.zone,
                    'маршрутов' if prev_service.is_for_united_request else 'единичных заявок'
                )
            )
    request.save(user=user)
    update_request_timesheets(request)
    return update_turnouts(request, user, prev_bonus, force_commit) + (prev_value,)


def _update_driver_name(request, value, user, force_commit=False, user_customer=None):
    prev_value = request.driver_name
    if user_customer is not None and request.status != DeliveryRequest.NEW:
        raise PermissionDenied('Редактировать можно только новую заявку.')
    request.driver_name = normalize_driver_name(value)
    request.save(user=user)
    return [], False, prev_value


def _update_driver_phones(request, value, user, force_commit=False, user_customer=None):
    prev_value = request.driver_phones.split(', ')
    if user_customer is not None and request.status != DeliveryRequest.NEW:
        raise PermissionDenied('Редактировать можно только новую заявку.')
    request.driver_phones = ', '.join(value)
    request.save(user=user)
    return [], False, prev_value


def _update_comment(request, value, user, force_commit=False, user_customer=None):
    prev_value = request.comment
    if user_customer is not None:
        raise PermissionDenied('Редактирование комментария запрещено.')
    request.comment = value
    request.save(user=user)
    return [], False, prev_value


def _update_customer_comment(request, value, user, force_commit=False, user_customer=None):
    prev_value = request.customer_comment
    if user_customer is None:
        raise PermissionDenied('Редактировать комментарий клиента может только клиент.')
    request.customer_comment = value
    request.save(user=user)
    return [], False, prev_value


def _update_is_private(request, is_private, user, force_commit=False, user_customer=None):
    if user_customer is not None:
        raise PermissionDenied('Редактирование приватности запрещено.')
    if is_private:
        _, created = PrivateDeliveryRequest.objects.get_or_create(
            request=request,
            defaults={
                'author': user,
            }
        )
        prev_value = not created
    else:
        prev_value = (
            'the_redhuman_is.PrivateDeliveryRequest' in
            PrivateDeliveryRequest.objects.filter(
                request=request
            ).delete()[1]
        )
    return [], False, prev_value


@log
def update_delivery_request(request_id, field, value, user, force_commit=False):
    update_function = {
        'customer_confirmation': _update_customer_confirmation,
        'date': _update_date,
        'location': _update_location,
        'service': _update_service,
        'status': _update_status,
        'operator': _update_operator,
        'customer': _update_customer,
        'driver_name': _update_driver_name,
        'driver_phones': _update_driver_phones,
        'comment': _update_comment,
        'customer_comment': _update_customer_comment,
        'is_private': _update_is_private,
    }

    try:
        with transaction.atomic():
            user_customer, user_location = get_user_customer_location(user)
            request = _request_lock(
                request_id,
                customer_id=user_customer,
                location_id=user_location,
            )

            try:
                _field_update_function = update_function[field]
            except KeyError:
                if field == 'arrival_time':
                    raise PermissionDenied(
                        'Редактирование времени прибытия в новой версии недоступно.'
                    )
                else:
                    raise ValueError('Некорректное имя поля.')

            messages, confirmation_required, prev_value = _field_update_function(
                request,
                value,
                user,
                force_commit,
                user_customer=user_customer,
            )

            if confirmation_required:
                raise ConfirmationRequired
            else:
                update_delivery_request_status(request, user=user)

        if user_customer is not None and value != prev_value:
            notifications.notify_updated(request, None, field, prev_value, value)

        elif field == 'driver_phones':
            if (
                value and
                prev_value != value and
                request.status not in DeliveryRequest.FINAL_STATUSES
            ):
                notifications.notify_driver_worker_assigned(request)

    except ConfirmationRequired:
        pass

    return messages, confirmation_required


def _has_resolve_discrepancy_permission(user: User) -> bool:
    return user.is_superuser or user.groups.filter(
        name__in=[
            'Доставка-руководитель',
            'Расхождения',
        ]
    ).exists()


@log
@transaction.atomic
def resolve_discrepancy(
        request_id: int,
        item_id: int,
        worker_id: int,
        comment: str,
        is_ok: Optional[bool],
        user: User
):
    request, item, itemworker, _ = _make_confirmation_prechecks(request_id, item_id, worker_id)
    _check_start_exists(itemworker, worker_id, item_id)

    if hasattr(itemworker.itemworkerstart, 'itemworkerstartconfirmation'):
        raise DeliveryWorkflowError('Адрес уже подтвержден.')

    if is_ok is not None and not _has_resolve_discrepancy_permission(user):
        raise PermissionDenied('Нет прав утверждать или отклонять расхождение.')

    return ItemWorkerDiscrepancyCheck.objects.update_or_create(
        itemworkerstart=itemworker.itemworkerstart,
        defaults={
            'author': user,
            'is_ok': is_ok,
            'comment': comment,
        }
    )


@log
@transaction.atomic
def add_extra_photos(request_id, images):
    try:
        delivery_request = DeliveryRequest.objects.select_for_update(
            nowait=True
        ).only('pk').get(pk=request_id)
    except DeliveryRequest.DoesNotExist:
        raise ObjectNotFoundError(f'Заявка {request_id} не найдена.')
    for image in images:
        add_photo(delivery_request, image)


@log
def import_requests(customer_id, xlsx_file, user, notify_dispatchers=False):
    user_customer, user_location = get_user_customer_location(user)
    if user_customer is not None:
        if customer_id != user_customer:
            raise PermissionDenied(
                'У пользователя нет прав импортировать заявки для этого клиента.'
            )
    else:
        if not Customer.objects.filter(pk=customer_id).exists():
            raise ObjectNotFoundError(f'Клиент {customer_id} не существует.')

    try:
        openpyxl.load_workbook(
            xlsx_file,
            read_only=True,
            data_only=True,
            keep_links=False,
        )
    except Exception:
        raise ValidationError(
            message=(
                'Неправильный формат файла. Файл должен быть в формате ".xlsx". '
                'Скачайте шаблон, нажав на кнопку "Скачать Excel-шаблон".'
            ),
            code='bad_file'
        )
    requests_file = create_requests_file(
        author_id=user.pk,
        customer_id=customer_id,
        data_file=xlsx_file,
    )
    import_requests_and_make_report(user.pk, customer_id, requests_file.pk, notify_dispatchers)
