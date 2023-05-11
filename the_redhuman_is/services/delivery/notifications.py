from typing import (
    List,
    Optional,
)

from django.contrib.postgres.aggregates import ArrayAgg
from django.contrib.postgres.fields import ArrayField
from django.db import (
    IntegrityError,
    transaction,
)
from django.db.models import (
    CharField,
    Exists,
    F,
    OuterRef,
    Subquery,
)
from django.urls import reverse
from django.utils import timezone

from the_redhuman_is.async_utils import smsc_sms
from the_redhuman_is.models.delivery import (
    DeliveryItem,
    DeliveryRequest,
    DeliveryWorkerFCMToken,
    DriverSms,
    ItemWorker,
    RequestWorker,
    SmsPhone,
    ZoneGroup,
)
from the_redhuman_is.models.worker import Worker
from the_redhuman_is import tasks

from utils.date_time import string_from_date
from utils.phone import (
    extract_phones,
    format_phone,
    format_phones,
)


def notify_dispatchers(message_body):
    now = timezone.localtime().strftime('%H:%M')
    tasks.send_tg_message_to_dispatchers(f'{now} {message_body}')


def do_try_notify_driver_worker_assigned(
        request_id: int,
        formatted_phones: List[str],
        message: str
) -> None:
    """
    !!! Should be a part of a huey task (see tasks.py)
    """
    try:
        sms = DriverSms.objects.create(
            request_id=request_id,
            text=message
        )
    except IntegrityError:
        return

    for phone in formatted_phones:
        try:
            with transaction.atomic():
                SmsPhone.objects.create(
                    sms=sms,
                    phone=phone
                )

                # Todo: use some data from response?
                response = smsc_sms.send_sms('GetTask', phone, message)

        except Exception as e:
            print(e)


def _last_fcm_token(worker_id):
    return DeliveryWorkerFCMToken.objects.filter(
        user__workeruser__worker=worker_id
    ).order_by(
        'timestamp'
    ).last()


def notify_new_request_available(worker_id):
    token = _last_fcm_token(worker_id)
    if token is not None:
        tasks.send_push_notification(
            'Новая заявка',
            'Есть новая заявка для работы! Нажмите, чтобы подтвердить.',
            None,
            'new_request',
            token.token
        )


def notify_unassigned_request_available(request: DeliveryRequest):
    if (
        request.delivery_service_id is None or
        request.location_id is None or
        request.confirmed_timepoint is None or
        request.status in DeliveryRequest.FINAL_STATUSES or
        request.date != timezone.localdate() or
        hasattr(request, 'privatedeliveryrequest')
    ):
        return

    has_understaffed_items = DeliveryItem.objects.all(
    ).with_itemworker_count(
    ).filter(
        request=request,
        itemworker_count__lt=F('workers_required'),
        confirmed_timepoint__isnull=False,
    ).exists()
    if not has_understaffed_items:
        return

    try:
        zone = ZoneGroup.objects.get(locationzonegroup__location=request.location)
    except ZoneGroup.DoesNotExist:
        return

    workers = Worker.objects.all(
    ).filter_rf_or_mk(
        deadline=request.date,
    ).annotate(
        has_active_requests=Exists(
            RequestWorker.objects.annotate(
                has_items=Exists(
                    ItemWorker.objects.filter(
                        requestworker=OuterRef('pk'),
                        itemworkerrejection__isnull=True,
                    )
                )
            ).filter(
                request__delivery_service__isnull=False,
                worker=OuterRef('pk'),
                workerrejection__isnull=True,
                requestworkerturnout__isnull=True,
                has_items=True,
            ).exclude(
                request__status__in=DeliveryRequest.FINAL_STATUSES,
            )
        ),
    ).filter(
        mobileappworker__isnull=False,
        banned__isnull=True,
        workerzone__zone=zone,
        has_active_requests=False,
    ).values_list(
        'pk',
        flat=True
    )
    for worker_id in workers:
        notify_new_request_available(worker_id)


def notify_driver_worker_assigned(request: DeliveryRequest, worker_id: Optional[int] = None):
    driver_phones = extract_phones(format_phones(request.driver_phones))
    if len(driver_phones) == 0:
        return

    workers = RequestWorker.objects.with_full_name(
    ).filter(
        request=request,
        workerrejection__isnull=True,
        workerconfirmation__isnull=False,
    ).annotate(
        item_codes=Subquery(
            ItemWorker.objects.filter(
                itemworkerrejection__isnull=True,
                requestworker=OuterRef('pk'),
            ).values(
                'requestworker'
            ).annotate(
                codes=ArrayAgg(
                    'item__code',
                    ordering=(
                        'item__confirmed_timepoint',
                        'item__interval_begin',
                        'item__interval_end',
                        'item_id',
                    )
                )
            ).values(
                'codes'
            ),
            output_field=ArrayField(CharField())
        ),
    ).values(
        'full_name',
        'worker__tel_number',
        'item_codes',
    ).order_by(
        'worker'
    )
    if worker_id is not None:
        workers = workers.filter(
            worker=worker_id,
        )

    message_lines = [
        '{} {} принял {}'.format(
            worker['full_name'],
            format_phone(worker['worker__tel_number']),
            ','.join(worker['item_codes'])
        )
        for worker in workers
        if worker['item_codes']
    ]
    if not message_lines:
        return

    message_lines.append('Дисп: +7(966)666-30-26')
    message = '\n'.join(message_lines)

    tasks.try_notify_driver_worker_assigned(request.pk, driver_phones, message)


def notify_photo_rejected(worker_id, rejection_comment):
    token = _last_fcm_token(worker_id)
    if token is not None:
        tasks.send_push_notification(
            'Фото отклонено',
            rejection_comment,
            None,
            'photo_rejected',
            token.token
        )


def notify_new_suspicious_photo(
        request: DeliveryRequest,
        worker: Worker
) -> None:
    worker_ref = '<a href="https://is.gettask.ru{}">{}</a>'.format(
        reverse('the_redhuman_is:worker_detail', kwargs={'pk': worker.pk}),
        worker
    )
    request_ref = (
        '<a href="https://is.gettask.ru/rf/delivery/photos_dashboard/'
        '?request={}&worker={}">заявке №{}</a>'.format(
            request.pk,
            worker.pk,
            request.pk,
        )
    )

    notify_dispatchers(f'{worker_ref} подозрительно отметился на {request_ref}.')


def notify_suspicious_address_update(
        item: DeliveryItem,
        workers: List[Worker]
) -> None:
    header = (
        f'Адрес {item.code} в заявке {item.request_id} обновлен.\n'
        f'Подозрительные отметки:\n\n'
    )
    worker_lines = [
        '<a href="https://is.gettask.ru{}">{}</a>'.format(
            reverse('the_redhuman_is:worker_detail', kwargs={'pk': worker.pk}),
            worker
        ) + ' -- ' +
        (
            '<a href="https://is.gettask.ru/rf/delivery/photos_dashboard/'
            '?request={}&worker={}">фото</a>'.format(
                item.request_id,
                worker.pk,
            )
        )
        for worker in workers
    ]
    notify_dispatchers(header + '\n'.join(worker_lines))


def notify_photo_attached(request, item, itemworker):
    worker = itemworker.requestworker.worker

    remaining_items_count = ItemWorker.objects.filter(
        requestworker=itemworker.requestworker,
        requestworker__workerrejection__isnull=True,
        itemworkerrejection__isnull=True,
        itemworkerfinish__photo__isnull=True,
    ).count()

    remaining_requests_count = RequestWorker.objects.all(
    ).filter_active(
    ).filter(
        worker=worker.pk,
    ).exclude(
        pk=itemworker.requestworker_id
    ).count()

    worker_ref = '<a href="https://is.gettask.ru{}">{}</a>'.format(
        reverse('the_redhuman_is:worker_detail', kwargs={'pk': worker.pk}),
        worker
    )

    msg_complete = (
        f'выполнил адрес {item.code} в '
        f'<a href="https://is.gettask.ru/rf/delivery/photos_dashboard/'
        f'?request={request.pk}&worker={worker.pk}">заявке №{request.pk}</a>'
    )

    if remaining_items_count == 0 == remaining_requests_count:
        msg_remaining = 'свободен'
    else:
        msg_remaining = (
            f'осталось адресов в этой заявке: {remaining_items_count},'
            f' других заявок: {remaining_requests_count}'
        )

    notify_dispatchers(f'{worker_ref} {msg_complete}, {msg_remaining}.')


def notify_removed_item(request, item):
    customer = request.customer.cust_name
    notify_dispatchers(
        f'Для клиента {customer} был отменен адрес {item.pk} в заявке №{request.pk}'
    )


_REQUEST_ITEM_FIELD_NAMES = {
    'address': 'адрес',
    'carrying_distance': 'пронос',
    'code': 'индекс',
    'customer_comment': 'комментарий клиента',
    'date': 'дату',
    'driver_name': 'фио водителя',
    'driver_phones': 'тел. водителя',
    'floor': 'этаж',
    'has_elevator': 'наличие лифта',
    'mass': 'массу',
    'max_size': 'максимальный габарит',
    'place_count': 'кол-во мест',
    'shipment_type': 'характер груза',
    'time_interval': 'время',
    'interval_begin': 'начало интервала',
    'interval_end': 'конец интервала',
    'volume': 'объем',
    'workers_required': 'число работников',
}


def _bool_to_word(value):
    if value is None:
        return 'неизвестно'
    if value:
        return 'есть'
    else:
        return 'нет'


def notify_updated(request, item, field, prev_value, value):
    # GT-367: ignore 'customer_comment' and 'confirmed' fields
    if field in ('customer_comment', 'customer_confirmation'):
        return

    customer = request.customer.cust_name

    if field == 'status':
        if value == DeliveryRequest.CANCELLED_WITH_PAYMENT:
            message = f'{customer} отменил заявку {request}.'
        elif value == DeliveryRequest.CANCELLED:
            message = f'{customer} удалил заявку {request}.'
        else:
            message = None
    elif field == 'customer_confirmation':
        if value:
            message = f'{customer} подтвердил заявку {request}'
        else:
            message = f'{customer} отменил подтверждение заявки {request}.'

    else:
        field_name = _REQUEST_ITEM_FIELD_NAMES.get(field, field)
        if field == 'driver_phones':
            prev_value = ', '.join(prev_value)
            value = ', '.join(value)
        elif isinstance(value, bool):
            prev_value = _bool_to_word(prev_value)
            value = _bool_to_word(value)
        if item is not None:
            item_name = f', адрес {item.pk}'
        else:
            item_name = ''
        message = (
            f'{customer} изменил {field_name} с "{prev_value}" на "{value}"'
            f' (заявка {request}{item_name}).'
        )

    if message is not None:
        notify_dispatchers(message)


def notify_new_request(delivery_request):
    if delivery_request.location is not None:
        region_names = list(delivery_request.location.locationzonegroup_set.select_related(
            'zone_group'
        ).values_list(
            'zone_group__name',
            flat=True
        ).distinct())
        if region_names:
            region_info = f'регион{"ы"*(len(region_names) > 1)} {", ".join(region_names)}'
        else:
            region_info = f'регион не определен'
    else:
        region_info = 'объект (филиал) не выбран'

    date = string_from_date(delivery_request.date)
    notify_dispatchers(
        f'Заказ от "{delivery_request.customer.cust_name}"'
        f' №{delivery_request.pk} на {date}, {region_info}'
    )


def notify_new_import(customer):
    notify_dispatchers(f'Группа заказов от "{customer.cust_name}"')
