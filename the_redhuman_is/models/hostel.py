# -*- coding: utf-8 -*-

import datetime

from django.db import models
from django.db import transaction
from django.db.models import Q
from django.db.models import Sum

from django.contrib.auth.models import User

import finance

from utils.date_time import string_from_date

from .worker import Worker
from .models import (
    WorkerTurnout,
    CustomerIndustrialAccounts,
    IndustrialCostType,
    get_or_create_customer_industrial_accounts,
)


@transaction.atomic
def update_hostel_bonus(turnout, author):
    worker = turnout.worker
    day = turnout.timesheet.sheet_date

    turnouts = WorkerTurnout.objects.filter(
        worker=worker,
        timesheet__sheet_date=day
    ).order_by(
        'pk'
    )

    bonus_operations = HostelBonusOperation.objects.filter(
        turnout__in=turnouts
    )

    if bonus_operations.count() > 1:
        raise Exception(
            'У работника {} за {} несколько надбавок за непроживание, сообщите Алексею!'.format(
                worker,
                string_from_date(day)
            )
        )

    if bonus_operations.exists():
        bonus_operation = bonus_operations.get().operation
        # Игнорируем закрытые компенсации. Не очевидно, хорошо это или нет.
        if bonus_operation.is_closed:
            return
    else:
        bonus_operation = None

    bonus = HostelBonus.objects.filter(
        Q(last_day__gte=day) | Q(last_day__isnull=True),
        worker=worker,
        first_day__lte=day
    )

    worker_account = worker.worker_account.account
    cost_type = IndustrialCostType.objects.get(name='Проживание')
    customer_accounts = get_or_create_customer_industrial_accounts(
        customer=turnout.timesheet.customer,
        cost_type=cost_type
    )
    debit = customer_accounts.account_20

    industrial_account = CustomerIndustrialAccounts.objects.get(
        cost_type__name='Проживание',
        customer=turnout.timesheet.customer
    ).account_20

    if bonus.exists():
        hours = min(
            turnouts.aggregate(
                Sum('hours_worked')
            )['hours_worked__sum'] or 0,
            11
        )
        amount = bonus.get().amount * hours / 11
        if bonus_operation is None:
            operation = finance.models.Operation.objects.create(
                author=author,
                timepoint=datetime.datetime.combine(
                    day,
                    datetime.time(23, 45)
                ),
                comment='Компенсация проживания за {}'.format(
                    string_from_date(day)
                ),
                credit=worker_account,
                debet=debit,
                amount=amount
            )
            HostelBonusOperation.objects.create(
                turnout=turnout,
                operation=operation
            )
    else:
        amount = 0

    if bonus_operation:
        finance.models.update_if_changed(
            bonus_operation,
            amount,
            credit=worker_account,
            debit=debit
        )


class HostelBonus(models.Model):
    timestamp = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Время создания'
    )
    author = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        verbose_name='Автор'
    )

    worker = models.ForeignKey(
        Worker,
        on_delete=models.PROTECT,
        verbose_name='Рабочий'
    )
    amount = models.PositiveIntegerField()
    first_day = models.DateField(
        verbose_name='Первый день'
    )
    last_day = models.DateField(
        verbose_name='Последний день',
        blank=True,
        null=True
    )

    def __str__(self):
        description = '{}; {}р. за смену с {}'.format(
            self.worker,
            self.amount,
            string_from_date(self.first_day)
        )
        if self.last_day:
            description += ' по {}'.format(
                string_from_date(self.last_day)
            )

        return description


class HostelBonusOperation(models.Model):
    turnout = models.ForeignKey(
        WorkerTurnout,
        on_delete=models.PROTECT,
        verbose_name="Выход"
    )
    operation = models.ForeignKey(
        finance.models.Operation,
        on_delete=models.PROTECT,
        verbose_name="Операция"
    )

    def __str__(self):
        return "{} {}".format(self.turnout, self.operation)
