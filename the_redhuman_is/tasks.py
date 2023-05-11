#
# This file should contain or import all huey tasks
#

import imaplib
import logging
import time
from typing import List
from datetime import timedelta
from functools import wraps

from django.contrib.auth.models import User
from django.db import models
from huey import crontab
from huey.contrib.djhuey import (
    db_periodic_task,
    db_task,
    lock_task,
    task,
)

from the_redhuman_is.async_utils import (
    email,
    push_notifications,
    receipts,
    smsc_sms,
)

from telegram_bot.utils import send_message
from telegram_bot.utils import send_message_to_group
from utils.date_time import UTCFormatter


@task()
def send_push_notification(title, body, data, tag, token):
    print(token)
    response = push_notifications.send_single_message(title, body, data, tag, token)
    # Todo: do something with response?


def send_push_notification_to_user(title, body, tag, user):
    from the_redhuman_is.services.delivery_requests import last_user_fcm_token

    token = last_user_fcm_token(user)
    if token:
        send_push_notification(title, body, None, tag, token.token)


@task()
def send_sms(sender, target, message):
    response = smsc_sms.send_sms(sender, target, message)
    print(response)
    # Todo: do something with response?


@db_task()
def send_tg_alert(message):
    from the_redhuman_is.services.alerts_telegram_bot import send_alert
    send_alert(message)


@db_task()
def send_tg_message(chat_id, message):
    send_message(chat_id, message)


@db_task()
def send_tg_message_to_clerks(message):
    send_message_to_group(message, 'Операционисты')
    send_message_to_group(message, 'Доставка-проверяющий')
    send_message_to_group(message, 'Верификация новых пользователей')


@db_task()
def send_tg_message_to_dispatchers(message):
    send_message_to_group(message, 'Доставка-диспетчер')


@task()
def send_email(to, subject, html, sender='default', attachment=None):
    email.send_email(to, subject, html, sender, attachment)


@db_task()
def normalize_address(delivery_item_pk, version, user):
    from the_redhuman_is.services.delivery.tariffs import do_normalize_address_update_tariff
    do_normalize_address_update_tariff(delivery_item_pk, version, user=user)


@db_task()
def normalize_address_in_bulk(delivery_items_pks, request_id, version, user):
    from the_redhuman_is.services.delivery.tariffs import do_normalize_address_in_bulk
    do_normalize_address_in_bulk(delivery_items_pks, request_id, version, user)


@db_task()
def try_notify_driver_worker_assigned(
        delivery_request_pk: int,
        phones: List[str],
        message: str
) -> None:
    from the_redhuman_is.services.delivery.notifications import \
        do_try_notify_driver_worker_assigned
    do_try_notify_driver_worker_assigned(delivery_request_pk, phones, message)


@db_task()
def import_requests_and_make_report(user_pk, customer_pk, file_pk, notify_dispatchers):
    from the_redhuman_is.views.delivery import do_import_requests_and_make_report
    do_import_requests_and_make_report(user_pk, customer_pk, file_pk, notify_dispatchers)


@db_task(retries=5, retry_delay=timedelta(hours=1).seconds)
def fetch_receipt_image(receipt_pk):
    receipts.fetch_receipt_image(receipt_pk)


@db_task()
def make_paysheet_payments_with_talk_bank(author_id: int, paysheet_id: int):
    from the_redhuman_is.services.paysheet.talk_bank import start_paysheet_payments

    start_paysheet_payments(author_id, paysheet_id)


inbox_connection = None


#@db_periodic_task(crontab())
@lock_task('invalidate_compromised')
def invalidate_compromised_daily_reconciliation_uuids():
    from the_redhuman_is.services import daily_reconciliation
    global inbox_connection
    if inbox_connection is None:
        inbox_connection = email.do_connect_to_mailbox(receiver='gt_docs')
    try:
        daily_reconciliation.invalidate_compromised_uuids(inbox_connection)
    except (TimeoutError, imaplib.IMAP4.error, email.BadStatusError):
        inbox_connection = None


# ### Logging

logger = logging.getLogger('the_redhuman_is.services.delivery.actions')


@task()
def do_log(*args, **kwargs):
    logger.log(*args, **kwargs)


def _model_to_pk(value):
    if isinstance(value, User):
        return f'{value.username}#{value.pk}'
    elif isinstance(value, models.Model):
        return value.pk
    elif isinstance(value, tuple):
        return tuple(_model_to_pk(item) for item in value)
    elif isinstance(value, list):
        return list(_model_to_pk(item) for item in value)
    elif isinstance(value, dict):
        return {k: _model_to_pk(v) for k, v in value.items()}
    else:
        return value


LOG_MESSAGE_FORMAT = '{time} :: {func} | {args} {kwargs} | {res}'


def log(func):
    def proxy(*args, **kwargs):
        log_data = {
            'time': UTCFormatter.format_time(time.time()),
            'func': func.__name__,
            'args': _model_to_pk(args),
            'kwargs': _model_to_pk(kwargs),
        }
        try:
            result = func(*args, **kwargs)
        except Exception as e:
            log_data['res'] = f'{type(e)}: {e}'
            do_log(logging.ERROR, LOG_MESSAGE_FORMAT.format(**log_data))
            raise
        else:
            log_data['res'] = _model_to_pk(result)
            do_log(logging.INFO, LOG_MESSAGE_FORMAT.format(**log_data))
            return result
    return wraps(func)(proxy)
