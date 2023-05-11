# -*- coding: utf-8 -*-

import datetime

from django.db import models
from django.utils import timezone


class LastUiscomCallsImportTimepoint(models.Model):
    timepoint = models.DateTimeField(
        default=timezone.now,
        verbose_name="Время последней выгрузки")


def get_last_uiscom_calls_import_timepoint():
    if LastUiscomCallsImportTimepoint.objects.all().exists():
        return LastUiscomCallsImportTimepoint.objects.get().timepoint
    return datetime.datetime(year=2000, month=1, day=1)


def update_last_uiscom_calls_import_timepoint():
    if not LastUiscomCallsImportTimepoint.objects.all().exists():
        LastUiscomCallsImportTimepoint.objects.create()
    else:
        timepoint = LastUiscomCallsImportTimepoint.objects.get()
        timepoint.timepoint = timezone.now()
        timepoint.save()
