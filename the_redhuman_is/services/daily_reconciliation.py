# -*- coding: utf-8 -*-
import email
import imaplib
import re
from datetime import timedelta

from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.db.models.signals import pre_save
from django.db.utils import IntegrityError
from django.dispatch import receiver
from django.utils import timezone
from redis_sessions.connection import redis_server

import the_redhuman_is.async_utils.email as rh_email
from the_redhuman_is.models.delivery import (
    DailyReconciliation,
    DailyReconciliationConfirmation,
    DailyReconciliationNotification,
    DeliveryRequest,
    DeliveryRequestConfirmation,
)
from the_redhuman_is.services.delivery.utils import catch_lock_error


@receiver(pre_save, sender=DeliveryRequest)
def _delivery_request_pre_save(sender, instance, **kwargs):
    need_to_ensure_daily_reconciliation = False

    if instance.pk is None:
        need_to_ensure_daily_reconciliation = True
    else:
        current_request = DeliveryRequest.objects.get(pk=instance.pk)
        location_changed = current_request.location != instance.location
        date_changed = current_request.date != instance.date
        if date_changed or location_changed:
            need_to_ensure_daily_reconciliation = True

            # Delete reconciliation if there are no requests anymore
            if current_request.location is not None:
                requests_still_exist = DeliveryRequest.objects.filter(
                    date=current_request.date,
                    location=current_request.location
                ).exclude(
                    pk=current_request.pk
                ).exists()
                if not requests_still_exist:
                    try:
                        daily_reconciliation = DailyReconciliation.objects.get(
                            date=current_request.date,
                            location=current_request.location
                        )
                        DailyReconciliationNotification.objects.filter(
                            reconciliation=daily_reconciliation
                        ).delete()
                        daily_reconciliation.delete()
                    except ObjectDoesNotExist:
                        pass

    if instance.location is not None and need_to_ensure_daily_reconciliation:
        try:
            with transaction.atomic():
                DailyReconciliation.objects.create(
                    date=instance.date,
                    location=instance.location
                )
        except IntegrityError:
            pass


@catch_lock_error
@transaction.atomic
def confirm_daily_reconciliation(reconciliation_pk, author):
    reconciliation = DailyReconciliation.objects.select_for_update(
        nowait=True
    ).only(
        'id',
        'date',
        'location_id',
    ).get(pk=reconciliation_pk)
    try:
        with transaction.atomic():
            DailyReconciliationConfirmation.objects.create(
                author=author,
                reconciliation=reconciliation
            )
    except IntegrityError:
        pass

    delivery_requests = DeliveryRequest.objects.filter(
        date=reconciliation.date,
        location=reconciliation.location_id,
        status__in=DeliveryRequest.SUCCESS_STATUSES,
        deliveryrequestconfirmation__isnull=True,
    )

    for delivery_request in delivery_requests:
        try:
            with transaction.atomic():
                DeliveryRequestConfirmation.objects.create(
                    author=author,
                    request=delivery_request
                )
        except IntegrityError:
            pass


@catch_lock_error
@transaction.atomic
def unconfirm_daily_reconciliation(reconciliation_pk):
    reconciliation = DailyReconciliation.objects.select_for_update(
        of=('self',),
        nowait=True
    ).select_related(
        'dailyreconciliationconfirmation'
    ).only(
        'id',
        'dailyreconciliationconfirmation__id',
    ).get(pk=reconciliation_pk)
    try:
        reconciliation.dailyreconciliationconfirmation.delete()
    except DailyReconciliationConfirmation.DoesNotExist:
        pass


UUID_REGEX = re.compile(
    r'[a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}',
    re.IGNORECASE
)
INBOX_CHECK_INTERVAL = 45  # seconds
INBOX_DATE_LOOKBEHIND = timedelta(days=2)


def invalidate_compromised_uuids(connection):
    day_since = imaplib.Time2Internaldate(timezone.now() - INBOX_DATE_LOOKBEHIND)[1:12]
    plaintext_search_term = '/reconciliations/'  # ascii
    last_uid = redis_server.get('INBOX_LAST_UID') or 0
    last_check_timestamp = redis_server.get('INBOX_LAST_CHECK_TIMESTAMP') or 0
    start_timestamp = timezone.now().timestamp()
    if start_timestamp - last_check_timestamp < INBOX_CHECK_INTERVAL:
        return

    status, uids = connection.uid(
        'SEARCH',
        f'UID {last_uid + 1}:* SINCE {day_since} TEXT {plaintext_search_term}'
    )
    if status != 'OK':
        raise rh_email.BadStatusError

    for uid in map(int, uids[0].split()):
        if uid < last_uid:
            continue
        status, message_data = connection.uid('FETCH', f'{uid} (RFC822)')
        if status != 'OK':
            raise rh_email.BadStatusError
        message = email.message_from_bytes(
            message_data[0][1],
            policy=email.policy.default
        )

        for part in message.walk():
            if not part.is_multipart() and part.get_content_type().startswith('text'):
                content = part.get_content()
                uuid_match = UUID_REGEX.search(content)
                if uuid_match is not None:
                    DailyReconciliationNotification.objects.filter(
                        confirmation_key=uuid_match.group()
                    ).update(
                        confirmation_key=None
                    )
        redis_server.set('INBOX_LAST_UID', uid)
    redis_server.set('INBOX_LAST_CHECK_TIMESTAMP', start_timestamp)
