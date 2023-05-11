# -*- coding: utf-8 -*-

import os.path

from django.db import models
from django.db import transaction

from django.contrib.auth.models import User

from the_redhuman_is.models.worker import Worker

from utils.date_time import string_from_date


class K2KAlias(models.Model):
    timestamp = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Время создания'
    )
    author = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        verbose_name='Автор'
    )

    alias = models.CharField(
        'Написание Ителлы',
        max_length=256
    )
    worker = models.ForeignKey(
        Worker,
        on_delete=models.PROTECT,
        verbose_name='Рабочий'
    )

    def __str__(self):
        return '{} -> {}'.format(
                self.alias,
                self.worker
            )


def _k2k_sheet_upload_location(instance, filename):
    return 'itella/sheets/{}/{}'.format(
        instance.id,
        filename
    )


class K2KSheet(models.Model):
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
        upload_to=_k2k_sheet_upload_location
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
def create_k2k_sheet(author, data_file):
    k2k_sheet = K2KSheet.objects.create(author=author)
    k2k_sheet.data_file = data_file
    k2k_sheet.save()
    return k2k_sheet

