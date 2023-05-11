# -*- coding: utf-8 -*-

from django.db import models
from django.db import transaction

from django.contrib.auth.models import User

from django.utils import timezone


def _performance_file_upload_location(instance, filename):
    return 'vkusvill/performance/{}/{}'.format(
        instance.id,
        filename
    )


class PerformanceFile(models.Model):
    timestamp = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Время создания'
    )
    author = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        verbose_name='Автор'
    )
    data_file = models.FileField(upload_to=_performance_file_upload_location)
    import_timestamp = models.DateTimeField(
        verbose_name='Время импорта данных из файла',
        null=True,
        blank=True
    )

    def on_import_complete(self):
        self.import_timestamp = timezone.now()
        self.save()


@transaction.atomic
def create_performance_file(author, data_file):
    performance_file = PerformanceFile.objects.create(author=author)
    performance_file.data_file = data_file
    performance_file.save()
    return performance_file


def _errors_file_upload_location(instance, filename):
    return 'vkusvill/errors/{}/{}'.format(
        instance.id,
        filename
    )


class ErrorsFile(models.Model):
    timestamp = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Время создания'
    )
    author = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        verbose_name='Автор'
    )
    data_file = models.FileField(upload_to=_errors_file_upload_location)
    first_day = models.DateField(
        verbose_name='Первый день периода'
    )
    last_day = models.DateField(
        verbose_name='Последний день периода'
    )
    import_timestamp = models.DateTimeField(
        verbose_name='Время импорта данных из файла',
        null=True,
        blank=True
    )

    def on_import_complete(self):
        self.import_timestamp = timezone.now()
        self.save()


@transaction.atomic
def create_errors_file(author, data_file, first_day, last_day):
    errors_file = ErrorsFile.objects.create(
        author=author,
        first_day=first_day,
        last_day=last_day
    )
    errors_file.data_file = data_file
    errors_file.save()
    return errors_file
