# -*- coding: utf-8 -*-

import datetime
from functools import cached_property

from django.contrib.auth.models import User
from django.db import (
    models,
    transaction,
)
from django.db.models import (
    DecimalField,
    Exists,
    OuterRef,
    Subquery,
    Sum,
)
from django.db.models.functions import Coalesce

from django.utils import timezone

import finance

from the_redhuman_is.models.models import (
    Customer,
    CustomerLocation,
    SalaryPayment,
    set_accountable_person,
)
from the_redhuman_is.models.paysheet_v2 import (
    PaysheetBaseQueryset,
    Paysheet_v2,
    Paysheet_v2Entry,
    _workers_for_paysheet,
)
from the_redhuman_is.models.worker import Worker

from utils.date_time import string_from_date


class PrepaymentQuerySet(PaysheetBaseQueryset):

    def with_total_amount(self):
        amount_sq = Subquery(
            WorkerPrepayment.objects.filter(
                amount__gte=0,
                prepayment=OuterRef('pk')
            ).annotate(
                # note: fields are coalesced on a per-entry basis.
                res=Coalesce('operation__amount', 'amount', output_field=DecimalField())
            ).values(
                'prepayment'
            ).annotate(
                amount_sum=Sum('res', output_field=DecimalField())
            ).values(
                'amount_sum'
            ),
            output_field=DecimalField()
        )
        return self.annotate(total_sum=Coalesce(amount_sq, 0, output_field=DecimalField()))

    def with_is_closed(self):
        return self.annotate(
            closed=~Exists(
                WorkerPrepayment.objects.filter(
                    prepayment=OuterRef('pk'),
                    operation__isnull=True
                )
            )
        )


# Аванс
class Prepayment(models.Model):
    timestamp = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Время создания'
    )
    author = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        verbose_name='Автор'
    )
    customer = models.ForeignKey(
        Customer,
        on_delete=models.PROTECT,
        related_name='prepayments',
        verbose_name='Клиент'
    )
    location = models.ForeignKey(
        CustomerLocation,
        on_delete=models.PROTECT,
        related_name='prepayments',
        verbose_name='Объект',
        blank=True,
        null=True
    )

    first_day = models.DateField(
        verbose_name='Первый день периода',
    )
    last_day = models.DateField(
        verbose_name='Последний день периода',
    )

    objects = PrepaymentQuerySet.as_manager()

    def __str__(self):
        return '{} с {} по {}'.format(
            self.description,
            string_from_date(self.first_day),
            string_from_date(self.last_day)
        )

    @property
    def description(self):
        return 'Аванс №{} ({})'.format(
            self.pk,
            self.short_description
        )

    @cached_property
    def short_description(self):
        if not hasattr(self, 'short_desc',):
            return Prepayment.objects.with_short_description(
            ).values_list(
                'short_desc',
                flat=True
            ).get(pk=self.pk)
        return getattr(self, 'short_desc')

    @cached_property
    def is_closed(self):
        if not hasattr(self, 'closed',):
            return Prepayment.objects.with_is_closed(
            ).values_list(
                'closed',
                flat=True
            ).get(pk=self.pk)
        return getattr(self, 'closed')

    # Todo: merge with Paysheet_v2?
    @transaction.atomic
    def close(self, author, payment_account):
        for item in self.workers.all():
            if item.operation:
                raise Exception(
                    'Final operation already exists in entry.'
                )
            worker_account = item.worker.worker_account.account
            operation = finance.models.Operation.objects.create(
                author=author,
                timepoint=datetime.datetime.combine(
                    self.last_day,
                    datetime.time(23, 59)
                ),
                comment=str(self),
                debet=worker_account,
                credit=payment_account,
                amount=item.amount,
                is_closed=True
            )
            item.operation = operation
            item.save()
            # Todo: check if it is necessary
            SalaryPayment.objects.create(operation=operation)

    # Todo: merge with Paysheet_v2?
    @cached_property
    def total_amount(self):
        if not hasattr(self, 'total_sum',):
            return Prepayment.objects.with_total_amount(
            ).values_list(
                'total_sum',
                flat=True
            ).get(pk=self.pk)
        return getattr(self, 'total_sum')


class WorkerPrepayment(models.Model):
    prepayment = models.ForeignKey(
        Prepayment,
        on_delete=models.PROTECT,
        related_name='workers',
        verbose_name='Авансовая ведомость'
    )
    worker = models.ForeignKey(
        Worker,
        on_delete=models.PROTECT,
        verbose_name='Работник'
    )
    amount = models.DecimalField(
        max_digits=30,
        decimal_places=2,
        verbose_name="Сумма"
    )
    operation = models.OneToOneField(
        finance.models.Operation,
        on_delete=models.PROTECT,
        null=True,
        blank=True
    )

    def real_amount(self):
        if self.operation:
            return self.operation.amount
        return self.amount

    def __str__(self):
        return '{} {} {} {}'.format(
            self.pk,
            self.worker,
            self.amount,
            self.prepayment
        )


# Todo: merge with prepayment
@transaction.atomic
def create_prepayment(
        author,
        accountable_person,
        first_day,
        last_day,
        customer,
        location,
        workers=None):

    prepayment = Prepayment.objects.create(
        author=author,
        customer=customer,
        location=location,
        first_day=first_day,
        last_day=last_day
    )

    if accountable_person:
        set_accountable_person(prepayment, accountable_person)

    workers = _workers_for_paysheet(
        customer,
        location,
        first_day,
        last_day
    )
    for worker in workers:
        WorkerPrepayment.objects.create(
            prepayment=prepayment,
            worker=worker,
            amount=0
        )

    return prepayment


class TalkBankClient(models.Model):
    worker = models.OneToOneField(
        Worker,
        on_delete=models.PROTECT,
        verbose_name='Работник'
    )
    client_id = models.TextField(
        verbose_name='ID клиента'
    )

    def __str__(self):
        return f'{self.client_id}: {self.worker} ({self.worker.id})'


class TalkBankBindStatus(models.Model):
    timestamp = models.DateTimeField(
        verbose_name='Время получения',
        default=timezone.now
    )

    worker = models.ForeignKey(
        Worker,
        on_delete=models.PROTECT,
        verbose_name='Работник'
    )

    is_bound = models.BooleanField(
        verbose_name='Самозанятый привязан к ТокБанку',
    )
    operation_result = models.TextField(
        verbose_name='Код результата операции привязки'
    )
    operation_result_description = models.TextField(
        verbose_name='Расшифровка результата операции привязки'
    )


class TalkBankWebhookRequest(models.Model):
    timestamp = models.DateTimeField(
        verbose_name='Время получения',
        default=timezone.now
    )

    request_body = models.TextField(
        verbose_name='Тело запроса',
        null=True,
    )

    def __str__(self):
        return str(self.timestamp)


class PaysheetEntryTalkBankIncomeRegistration(models.Model):
    timestamp = models.DateTimeField(
        verbose_name='Время создания',
        default=timezone.now,
    )
    author = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        verbose_name='Автор'
    )

    paysheet = models.ForeignKey(
        Paysheet_v2,
        on_delete=models.PROTECT,
        verbose_name='Ведомость'
    )
    worker = models.ForeignKey(
        Worker,
        on_delete=models.PROTECT,
        verbose_name='Работник'
    )

    income_registration_request = models.TextField(
        verbose_name='Id запроса'
    )
    date = models.DateField(
        verbose_name='Дата чека',
    )
    # For debugging purposes
    amount = models.DecimalField(
        max_digits=30,
        decimal_places=2,
        verbose_name='Фактическая сумма'
    )


class PaysheetEntryTalkBankPayment(models.Model):
    paysheet_entry = models.OneToOneField(
        Paysheet_v2Entry,
        verbose_name='Запись в ведомости',
        on_delete=models.PROTECT
    )

    tax_number = models.TextField(
        verbose_name='ИНН'
    )
    amount = models.DecimalField(
        max_digits=30,
        decimal_places=2,
        verbose_name='Фактическая сумма'
    )
    bank_account = models.TextField(
        verbose_name='Счет'
    )
    bank_name = models.TextField(
        verbose_name='Банк'
    )
    bank_identification_code = models.TextField(
        verbose_name='Бик'
    )

    completed = models.BooleanField(
        verbose_name='Завершена',
    )
    status = models.TextField(
        verbose_name='Статус'
    )
    order_slug = models.TextField(
        verbose_name='ID операции'
    )
    talk_bank_commission = models.DecimalField(
        max_digits=30,
        decimal_places=2,
        verbose_name='Комиссия ТокБанка',
        blank=True,
        null=True
    )
    beneficiary_partner_commission = models.DecimalField(
        max_digits=30,
        decimal_places=2,
        verbose_name='Комиссия партнеров',
        blank=True,
        null=True
    )

    def __str__(self):
        # Todo!
        return f'{self.pk}'


class PaysheetEntryTalkBankPaymentAttempt(models.Model):
    paysheet = models.ForeignKey(
        Paysheet_v2,
        on_delete=models.PROTECT,
        verbose_name='Ведомость'
    )
    worker = models.ForeignKey(
        Worker,
        on_delete=models.PROTECT,
        verbose_name='Работник'
    )

    status = models.TextField(
        verbose_name='Результат операции выплаты'
    )
    description = models.TextField(
        verbose_name='Описание результата операции выплаты'
    )
    service_description = models.TextField(
        verbose_name='Описание услуги',
        null=True,
        blank=True,
    )

    def __str__(self):
        return 'Ведомость №{}, {}: {} ({})'.format(
            self.paysheet.pk,
            self.worker,
            self.status,
            self.description
        )


class PaysheetTalkBankPaymentStatus(models.Model):
    IN_PROGRESS = 'payment_in_progress'
    COMPLETE = 'payment_complete'
    ERROR = 'payment_error' # wtf?

    STATUS_DICT = {
        IN_PROGRESS: 'В процессе оплаты',
        COMPLETE: 'Успешно завершена',
        ERROR: 'Ошибка',
    }

    STATUS_CHOICES = [(key, value) for key, value in STATUS_DICT.items()]

    timestamp = models.DateTimeField(
        verbose_name='Время создания',
        default=timezone.now,
    )
    author = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        verbose_name='Автор'
    )

    paysheet = models.OneToOneField(
        Paysheet_v2,
        on_delete=models.PROTECT,
        verbose_name='Ведомость'
    )

    status = models.CharField(
        verbose_name='Статус',
        max_length=200,
        choices=STATUS_CHOICES,
        default=IN_PROGRESS
    )

    def __str__(self):
        # Todo!
        return f'{self.pk}'

