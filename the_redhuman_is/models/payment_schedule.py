# -*- coding: utf-8 -*-

import decimal

from django.db import models

from django.contrib.auth.models import User

from django.core.validators import MinValueValidator

from django.utils import timezone

import finance


# See finance.models.Operation
class PlannedOperation(models.Model):
    timestamp = models.DateTimeField(
        default=timezone.now,
        verbose_name='Время создания'
    )
    timepoint = models.DateTimeField(
        default=timezone.now,
        verbose_name='Дата и время'
    )
    author = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        verbose_name='Автор'
    )
    comment = models.TextField(
        blank=True,
        null=True,
        verbose_name='Комментарий'
    )

    debet = models.ForeignKey(
        finance.models.Account,
        on_delete=models.PROTECT,
        verbose_name='Дебет',
        related_name='planned_debit_operations'
    )
    credit = models.ForeignKey(
        finance.models.Account,
        on_delete=models.PROTECT,
        verbose_name='Кредит',
        related_name='planned_credit_operations'
    )
    amount = models.DecimalField(
        max_digits=30,
        decimal_places=2,
        verbose_name='Сумма',
        validators=[MinValueValidator(decimal.Decimal('0'))]
    )

    def __str__(self):
        return "{} {} [{}] (Д:{}, К:{})".format(
            self.id,
            self.timepoint.strftime('%d.%m.%Y %H:%M'),
            self.amount,
            self.debet,
            self.credit
        )
