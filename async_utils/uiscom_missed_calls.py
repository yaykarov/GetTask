# -*- coding: utf-8 -*-

import datetime
import pytz
import re

from django.utils import timezone

from applicants import models

from async_utils.models import get_last_uiscom_calls_import_timepoint
from async_utils.models import update_last_uiscom_calls_import_timepoint
from .uiscom_old_api import get_missed_calls


def import_uiscom_missed_calls():
    moscow_tz = pytz.timezone('Europe/Moscow')

    begin = get_last_uiscom_calls_import_timepoint() - datetime.timedelta(minutes=5)
    end = timezone.now() + datetime.timedelta(minutes=5)
    missed_calls = get_missed_calls(
        begin.astimezone(moscow_tz),
        end.astimezone(moscow_tz)
    )

    valid_dst = ['74951048240']
    date_rx = re.compile('^(.+?)\.\d+$')

    for phone, dst, date_str in missed_calls:
        if dst not in valid_dst:
            continue
        if not phone:
            print(phone)
            print(dst)
            print(date_str)
            continue

        m = date_rx.match(date_str)
        if m:
            date_str = m.group(1)

        date = datetime.datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')

        applicants = models.Applicant.objects.filter(phone=phone)
        if not applicants.exists():
            initial_status = models.StatusInitial.objects.get().status
            source = models.ApplicantSource.objects.get(name='недозвон на 8-800')
            now = timezone.now().astimezone(moscow_tz)
            models.Applicant.objects.create(
                phone=phone,
                type='in',
                status=initial_status,
                name='Неизвестно',
                source=source,
                next_date=now,
                comment='Пропущенный звонок {}'.format(
                    date.strftime('%H:%M %d.%m')
                ),
            )

    update_last_uiscom_calls_import_timepoint()

