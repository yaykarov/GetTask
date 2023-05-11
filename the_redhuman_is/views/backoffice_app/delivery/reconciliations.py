import io
import itertools
import operator
from datetime import (
    datetime,
    timedelta,
)
from uuid import uuid4
from zipfile import ZipFile

import openpyxl
from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.db.models import Q
from django.http import JsonResponse
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import (
    PermissionDenied,
    Throttled,
    ValidationError,
)

from the_redhuman_is.models.delivery import (
    DailyReconciliation,
    DailyReconciliationNotification,
)
from the_redhuman_is.models.models import CustomerLocation
from the_redhuman_is.services import (
    confirm_daily_reconciliation,
    unconfirm_daily_reconciliation,
)
from the_redhuman_is.tasks import send_email
from the_redhuman_is.views.backoffice_app.auth import bo_api
from the_redhuman_is.views.delivery import (
    _fill_details_sheet,
    _add_images_to_zip,
)
from the_redhuman_is.views.utils import get_first_last_day
from utils.functools import strtobool


@bo_api(['GET'])
def calendar(request):
    try:
        first_day, last_day = get_first_last_day(request)
    except ValueError:
        raise ValidationError('Bad first or last date')
    if first_day > last_day:
        raise ValidationError(f'First day {first_day} is later than last day {last_day}')

    daily_reconciliations = DailyReconciliation.objects.filter(
        date__range=(first_day, last_day),
    ).with_request_count(
    ).with_request_count(
        paid_only=True
    ).with_status(
    ).with_worker_count(
    ).with_worked_hours(
    ).values(
        'id',
        'location',
        'date',
        'status',
        'requests_total',
        'requests_paid',
        'worker_count',
        'worked_hours',
    ).order_by(
        'location',
        'date',
    )
    cell_data = {}
    for location, group in itertools.groupby(
            daily_reconciliations,
            key=operator.itemgetter('location')
    ):
        cell_data[location] = {e['date'].isoformat(): e for e in group}

    customer_locations = CustomerLocation.objects.filter(
        pk__in=cell_data.keys()
    ).values_list(
        'id', 'customer_id__cust_name', 'location_name'
    ).order_by(
        'customer_id__cust_name', 'location_name'
    )
    row_labels = [
        dict(zip(['id', 'customer', 'location'], location))
        for location in customer_locations
    ]
    column_labels = [
        (first_day + timedelta(days=x)).isoformat()
        for x in range((last_day - first_day).days + 1)
    ]
    return JsonResponse(
        {
            'rows': row_labels,
            'columns': column_labels,
            'cells': cell_data,
            'actions': {
                'confirm_unconfirm': request.user.is_superuser
            }
        },
        json_dumps_params={'ensure_ascii': False}
    )


@bo_api(['GET'])
def detail(request, pk):
    daily_reconciliation = DailyReconciliation.objects.with_status(
    ).with_last_notifications(
    ).with_confirmation(
    ).values(
        'id',
        'status',
        'last_notifications',
        'confirmation',
    ).get(
        pk=pk
    )
    last_notifications = daily_reconciliation['last_notifications']
    if not last_notifications:
        daily_reconciliation['last_notifications'] = None
    else:
        daily_reconciliation['last_notifications'] = {
            'is_ok': last_notifications[0]['is_ok'],
            'timestamp': last_notifications[0]['timestamp'],
            'attachment': last_notifications[0]['attachment'],
            'recipient_emails': list(dict.fromkeys(
                notification['recipient_email']
                for notification in last_notifications
            ))
        }
    return JsonResponse(
        daily_reconciliation,
        json_dumps_params={'ensure_ascii': False}
    )


@bo_api(['POST'])
def confirm_unconfirm(request, pk):
    try:
        confirm = strtobool(request.data['confirm'])
        if not isinstance(confirm, bool):
            raise ValidationError('`confirm` must be true or false.')
        if confirm:
            confirm_daily_reconciliation(pk, request.user)
        elif not confirm:
            unconfirm_daily_reconciliation(pk)
    except KeyError:
        raise ValidationError('`confirm` is required.')
    else:
        return JsonResponse({}, status=status.HTTP_204_NO_CONTENT)


EMAIL_INTERVAL = timedelta(seconds=2*60)


@bo_api(['POST'])
def send_notification_email(request, pk):
    reconciliation = DailyReconciliation.objects.all(
    ).select_related(
        'location'
    ).with_zone_name(
    ).with_status(
    ).with_worked_hours(
    ).get(
        pk=pk
    )

    DailyReconciliationNotification.objects.filter(
        reconciliation=reconciliation
    ).update(
        confirmation_key=None
    )
    if reconciliation.status == 'confirmed':
        if (
            reconciliation.last_notification is not None
            and reconciliation.last_notification['is_ok']
        ):
            return JsonResponse({}, status=status.HTTP_204_NO_CONTENT)
        # else send congrats

    elif reconciliation.status == 'notification_sent':
        time_to_wait = (datetime.strptime(
            reconciliation.last_notification['timestamp'],
            '%Y-%m-%dT%H:%M:%S.%f%z'
        ) + EMAIL_INTERVAL - timezone.now()).total_seconds()
        if time_to_wait > 0:
            raise Throttled(wait=time_to_wait)
        # else send another request to confirm

    elif reconciliation.status != 'ready_for_notification':
        raise PermissionDenied(
            f'Send notification emails for a reconciliation'
            f' with status {reconciliation.status} is not allowed.'
        )
    # else send first request to confirm

    send_daily_reconciliation_report(reconciliation, request.user)
    return JsonResponse({}, status=status.HTTP_202_ACCEPTED)


def _send_email_notification(notification, zone_name, attachment):
    formatted_date = notification.reconciliation.date.strftime('%d.%m.%Y')
    subject = f'Отчет ГетТаск, {zone_name}, за {formatted_date}'
    if notification.confirmation_key:
        url = (
            'https://lk.gettask.ru/daily_reconciliation/' +
            f'{notification.confirmation_key}'
        )
        body = f"""<p>Здравствуйте!</p>
<p>Мы приложили отчет о выполненных работах за {formatted_date}.</p>
<p>Если у Вас нет замечаний, пожалуйста, <a href="{url}" target="_blank">пройдите по ссылке</a> и подтвердите работы.</p>
<p>А если замечания есть, напишите нам о них в ответном письме. Мы обязательно со всем разберемся!</p>"""
    else:
        body = f"""<p>Здравствуйте.</p>
<p>Приложен отчет о выполненных работах за {formatted_date}.</p>
<p>Благодарим за подтверждение заявок.</p>"""
    send_email(
        to=notification.recipient_email,
        subject=subject,
        html=body,
        sender='gt_docs',
        attachment=attachment
    )


def send_daily_reconciliation_report(daily_reconciliation, author):
    # reconciliation needs to be annotated

    recipients = list(
        {
            'email': email,
            'ids': list(user['id'] for user in users),
        }
        for email, users in itertools.groupby(
            User.objects.filter(
                Q(locationaccount__location=daily_reconciliation.location_id) |
                Q(locationaccount__isnull=True),
                customeraccount__customer=daily_reconciliation.location.customer_id_id,
                is_active=True
            ).values(
                'id',
                'email',
            ),
            key=operator.itemgetter('email')
        )
    )
    if not recipients:
        return

    wb = openpyxl.Workbook(write_only=True)
    workers, hours, amount = _fill_details_sheet(
        wb.create_sheet(),
        daily_reconciliation.date,
        daily_reconciliation.location.customer_id,
        daily_reconciliation.location_id,
    )
    excel_report = io.BytesIO()
    wb.save(excel_report)

    images_archive = io.BytesIO()
    with ZipFile(images_archive, 'w') as zip_file:
        _add_images_to_zip(
            zip_file,
            daily_reconciliation.date,
            daily_reconciliation.location.customer_id,
        )

    if daily_reconciliation.all_requests_confirmed:
        confirm_daily_reconciliation(daily_reconciliation.pk, author=author)

    attachment = [
        {
            'filename': 'Сводка {} {}.xlsx'.format(
                daily_reconciliation.zone_name,
                daily_reconciliation.date.strftime('%d.%m.%Y'),
            ),
            'body': excel_report.getvalue(),
            'mime_type': ('application', 'vnd.ms-excel')
        },
        {
            'filename': 'Фото {} {}.zip'.format(
                daily_reconciliation.zone_name,
                daily_reconciliation.date.strftime('%d.%m.%Y'),
            ),
            'body': images_archive.getvalue(),
            'mime_type': ('application', 'zip')
        },
    ]

    def _get_key_getter():
        if daily_reconciliation.all_requests_confirmed:
            def empty():
                return None
            return empty
        else:
            return uuid4

    notification_values = dict(
        reconciliation=daily_reconciliation,
        author=author,
        hours=daily_reconciliation.worked_hours,
        amount=amount,
        is_ok=daily_reconciliation.all_requests_confirmed,
    )

    key_getter = _get_key_getter()
    first_notification = DailyReconciliationNotification.objects.create(
        **notification_values,
        recipient_email=recipients[0]['email'],
        recipient_id=recipients[0]['ids'][0],
        confirmation_key=key_getter()
    )
    first_notification.attachment = ContentFile(
        excel_report.getvalue(),
        name=f'{daily_reconciliation.pk}_{first_notification.pk}.xlsx'
    )
    first_notification.save(update_fields=['attachment'])
    DailyReconciliationNotification.objects.bulk_create(
        [
            DailyReconciliationNotification(
                **notification_values,
                recipient_email=first_notification.recipient_email,
                recipient_id=recipient_pk,
                attachment=first_notification.attachment,
                confirmation_key=first_notification.confirmation_key,
            )
            for recipient_pk in recipients[0]['ids'][1:]
        ]
    )
    _send_email_notification(first_notification, daily_reconciliation.zone_name, attachment)
    for same_email_users in recipients[1:]:
        confirmation_key = key_getter()
        notifications = DailyReconciliationNotification.objects.bulk_create(
            [
                DailyReconciliationNotification(
                    **notification_values,
                    recipient_email=same_email_users['email'],
                    recipient_id=recipient_pk,
                    attachment=first_notification.attachment,
                    confirmation_key=confirmation_key
                )
                for recipient_pk in same_email_users['ids']
            ]
        )
        _send_email_notification(notifications[0], daily_reconciliation.zone_name, attachment)
