# -*- coding: utf-8 -*-

import datetime

from django.utils import timezone

from applicants.models import Status
from applicants.models import active_applicants


def update_status(name):
    status_to_update = Status.objects.get(name=name)
    today = timezone.now().date()
    applicants = active_applicants().filter(
        status=status_to_update,
        next_date__lte=today
    )

    recall_status = Status.objects.get(name='перезвон')

    for applicant in applicants:
        applicant.status = recall_status
        applicant.next_date = today
        applicant.save()


def update_next_date():
    today = timezone.now().date()
    tomorrow = today + datetime.timedelta(days=1)

    # Today work except of initial
    applicants = active_applicants().filter(
        next_date__lte=today
    )
    for applicant in applicants:
        applicant.next_date = tomorrow
        applicant.save()
