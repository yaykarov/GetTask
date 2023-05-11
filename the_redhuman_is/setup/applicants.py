# -*- coding: utf-8 -*-

from applicants import models


def create_standard_statuses():
    initial_status = models.Status.objects.create(name='отклик')
    models.StatusInitial.objects.create(status=initial_status)

    final_status = models.Status.objects.create(name='выход')
    models.StatusFinal.objects.create(status=final_status)

    STANDARD_STATUSES = [
        'встреча в офисе',
        'встреча на объекте',
        'не подходит',
        'не согласен',
        'отказ СБ',
        'отправлен на объект',
        'отправлен на проверку СБ',
        'перезвон',
        'приглашен на оформление',
        'резерв',
    ]

    for name in STANDARD_STATUSES:
        models.Status.objects.create(name=name)
