# -*- coding: utf-8 -*-

import os.path

from django.db import models
from django.db import transaction

from django.contrib.auth.models import User

from utils.date_time import string_from_date


def _kn_sheet_upload_location(instance, filename):
    return 'kuehne_nagel/sheets/{}/{}'.format(
        instance.id,
        filename
    )


class KNSheet(models.Model):
    timestamp = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Время импорта'
    )
    author = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        verbose_name='Автор'
    )

    data_file = models.FileField(
        upload_to=_kn_sheet_upload_location
    )

    def short_filename(self):
        return os.path.basename(str(self.data_file))

    def __str__(self):
        return '{}, {}: {}'.format(
            string_from_date(self.timestamp),
            self.author.username,
            self.short_filename()
        )


@transaction.atomic
def create_kn_sheet(author, data_file):
    kn_sheet = KNSheet.objects.create(author=author)
    kn_sheet.data_file = data_file
    kn_sheet.save()
    return kn_sheet
