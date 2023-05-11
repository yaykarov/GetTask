# -*- coding: utf-8 -*-

import datetime
import decimal
import math
from functools import cached_property

from django.apps import apps
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.db import (
    models,
    transaction,
)
from django.db.models import (
    BooleanField,
    Case,
    CharField,
    Count,
    DecimalField,
    Exists,
    ExpressionWrapper,
    F,
    IntegerField,
    JSONField,
    Max,
    Min,
    OuterRef,
    Q,
    Subquery,
    Sum,
    TextField,
    Value,
    When,
)
from django.db.models.functions import (
    Coalesce,
    JSONObject,
    NullIf,
    TruncDate,
)
from django.db.models.signals import pre_delete
from django.dispatch import receiver

from django.utils import timezone

import finance
from utils.date_time import string_from_date
from utils.expressions import PostgresConcatWS
from .models import (
    AccountableDocumentOperation,
    AccountablePerson,
    Customer,
    CustomerLocation,
    DocumentWithAccountablePerson,
    MaintenanceManager,
    WorkerTurnout,
    get_accountable_person,
    set_accountable_person,
)
from .photo import get_photos
from .worker import (
    Worker,
    WorkerSelfEmploymentData,
)


# Todo: helper function in finance?
def _saldo(debit_operations, credit_operations):
    debit = debit_operations.aggregate(
        Sum('amount')
    )['amount__sum'] or 0
    credit = credit_operations.aggregate(
        Sum('amount')
    )['amount__sum'] or 0
    return credit - debit


def _exclude_workers_with_active_paysheets(workers):
    from .paysheet import WorkerPrepayment
    return workers.annotate(
        is_in_active_paysheet=Exists(
            Paysheet_v2Entry.objects.filter(
                worker=OuterRef('pk'),
                paysheet__is_closed=False,
            )
        ),
        has_active_prepayment=Exists(
            WorkerPrepayment.objects.filter(
                worker=OuterRef('pk'),
                operation__isnull=True,
            )
        )
    ).filter(
        is_in_active_paysheet=False,
        has_active_prepayment=False,
    )


def _workers_for_paysheet(customer, location, first_day, last_day, workers=None):
    if workers is None:
        turnout_sq = WorkerTurnout.objects.filter(
            timesheet__sheet_date__range=(first_day, last_day),
            worker=OuterRef('pk'),
        )
        if location:
            turnout_sq = turnout_sq.filter(
                timesheet__cust_location=location
            )
        elif customer:
            turnout_sq = turnout_sq.filter(
                timesheet__customer=customer
            )
        workers = Worker.objects.annotate(
            has_turnout=Exists(
                turnout_sq
            )
        ).filter(
            has_turnout=True
        )

    # Нельзя добавлять работника, который есть в открытых ведомостях
    workers = _exclude_workers_with_active_paysheets(workers)

    return workers


class PaysheetBaseQueryset(models.QuerySet):
    _item_model = None
    _model_rel_name = None

    @property
    def item_model(self):
        if self._item_model is None:
            self._set_model_properties()
        return self._item_model

    @property
    def model_rel_name(self):
        if self._model_rel_name is None:
            self._set_model_properties()
        return self._model_rel_name

    def _set_model_properties(self):
        # Note: QuerySet.__deepcopy__() prevents setting these in __init__()
        if self.model is Paysheet_v2:
            self._item_model = Paysheet_v2Entry
            self._model_rel_name = 'paysheet'
        else:
            prepayment_model = apps.get_model('the_redhuman_is', 'Prepayment')
            if self.model is prepayment_model:
                self._item_model = apps.get_model('the_redhuman_is', 'WorkerPrepayment')
                self._model_rel_name = 'prepayment'
            else:
                raise NotImplementedError

    def with_worker_count(self):
        workers_sq = Subquery(
            self.item_model.objects.filter(
                **{self.model_rel_name: OuterRef('pk')}
            ).values(
                self.model_rel_name
            ).annotate(
                count=Count('worker', distinct=True)
            ).values('count'),
            output_field=IntegerField()
        )
        return self.annotate(worker_count=Coalesce(workers_sq, 0))

    def with_data(self, deadline):
        return self.annotate(
            accountable_name=Subquery(
                Worker.objects.filter(
                    accountableperson__documentwithaccountableperson__content_type=ContentType.objects.get_for_model(
                        self.model
                    ),
                    accountableperson__documentwithaccountableperson__object_id=OuterRef('pk'),
                ).with_full_name(
                ).values('full_name'),
                output_field=CharField()
            ),
            money_issued=Exists(
                DocumentWithAccountablePerson.objects.filter(
                    accountabledocumentoperation__isnull=False,
                    content_type=ContentType.objects.get_for_model(self.model),
                    object_id=OuterRef('pk')
                )
            ),
            expired=Exists(
                AccountableDocumentOperation.objects.filter(
                    document__content_type=ContentType.objects.get_for_model(self.model),
                    document__object_id=OuterRef('pk'),
                    operation__timestamp__lte=deadline
                )
            )
        )

    def with_short_description(self):
        worker_name_sq = Subquery(
            self.item_model.objects.filter(
                **{self.model_rel_name: OuterRef('pk')}
            ).annotate(
                w_full_name=PostgresConcatWS(
                    Value(' '),
                    F('worker__last_name'),
                    F('worker__name'),
                    NullIf(F('worker__patronymic'), Value('')),
                    output_field=TextField()
                ),
            ).values(
                'w_full_name'
            )[:1]
        )
        return self.with_worker_count(
        ).annotate(
            repr_worker_name=worker_name_sq
        ).annotate(
            short_desc=PostgresConcatWS(
                Value('/'),
                Coalesce(NullIf(F('customer__cust_name'), Value('')), Value('Без названия')),
                NullIf(F('location__location_name'), Value('')),
                Case(
                    When(worker_count=1, then='repr_worker_name'),
                    output_field=CharField()
                )
            ),
        )

    def with_issued_amount(self):
        return self.annotate(
            issued_amount=Coalesce(
                Subquery(
                    finance.models.Operation.objects.filter(
                        accountabledocumentoperation__document__object_id=OuterRef('pk'),
                        accountabledocumentoperation__document__content_type=ContentType.objects.get_for_model(self.model),
                    ).values(
                        'amount'
                    ),
                    output_field=DecimalField()
                ),
                0,
                output_field=DecimalField()
            )
        )

    def filter_by_accountable_user(self, user_pk):
        return self.annotate(
            is_mm=Exists(
                MaintenanceManager.objects.filter(
                    customer=OuterRef('customer'),
                    worker__workeruser__user=user_pk
                )
            ),
            is_accountable=Exists(
                DocumentWithAccountablePerson.objects.filter(
                    accountable_person__worker__workeruser__user=user_pk,
                    content_type=ContentType.objects.get_for_model(self.model),
                    object_id=OuterRef('pk')
                )
            )
        ).filter(
            Q(is_mm=True) | Q(is_accountable=True)
        )


class PaysheetQuerySet(PaysheetBaseQueryset):

    def with_total_amount(self, normal_only=False):
        paysheet_entry_sq = Paysheet_v2Entry.objects.filter(
            amount__gte=0,
            paysheet=OuterRef('pk')
        )
        if normal_only:
            paysheet_entry_sq = paysheet_entry_sq.all(
            ).with_is_worker_selfemployed(
            ).filter(
                is_worker_selfemployed=False,
            )
            field_name = 'total_sum_normal'
        else:
            field_name = 'total_sum'
        amount_sq = Subquery(
            paysheet_entry_sq.annotate(
                res=Case(
                    When(
                        ExpressionWrapper(OuterRef('is_closed'), output_field=BooleanField()),
                        then='operation__amount'
                    ),
                    default='amount',
                    output_field=DecimalField()
                )
            ).values(
                'paysheet'
            ).annotate(
                amount_sum=Sum('res', output_field=DecimalField())
            ).values(
                'amount_sum'
            ),
            output_field=DecimalField()
        )
        return self.annotate(**{
            field_name: Coalesce(amount_sq, 0, output_field=DecimalField())
        })

    def with_talk_bank_payment_status(self):
        return self.annotate(
            talk_bank_payment_status=F('paysheettalkbankpaymentstatus__status')
        )


class Paysheet_v2(models.Model):
    timestamp = models.DateTimeField(
        verbose_name='Время создания',
        default=timezone.now
    )
    author = models.ForeignKey(
        User,
        verbose_name='Автор',
        on_delete=models.PROTECT,
    )
    customer = models.ForeignKey(
        Customer,
        on_delete=models.PROTECT,
        related_name='paysheets',
        verbose_name='Клиент',
        blank=True,
        null=True
    )
    location = models.ForeignKey(
        CustomerLocation,
        on_delete=models.PROTECT,
        related_name='paysheets',
        verbose_name='Объект',
        blank=True,
        null=True
    )

    first_day = models.DateField(
        verbose_name='Первый день периода'
    )
    last_day = models.DateField(
        verbose_name='Последний день периода'
    )

    is_closed = models.BooleanField(
        default=False,
        verbose_name='Закрытая?'
    )

    is_locked = models.BooleanField(
        default=True,
        verbose_name='Входящие операции блокируются'
    )

    objects = PaysheetQuerySet.as_manager()

    ALLOWED_DISCREPANCY = decimal.Decimal(5)  # максимально разрешенная невязка при закрытии ведомости

    def __str__(self):
        return '{} с {} по {}'.format(
            self.description,
            string_from_date(self.first_day),
            string_from_date(self.last_day)
        )

    @property
    def description(self):
        return 'Ведомость №{} ({})'.format(
            self.pk,
            self.short_description
        )

    @cached_property
    def short_description(self):
        if not hasattr(self, 'short_desc',):
            return Paysheet_v2.objects.with_short_description(
            ).values_list(
                'short_desc',
                flat=True
            ).get(pk=self.pk)
        return getattr(self, 'short_desc')

    @transaction.atomic
    def toggle_lock(self):
        if self.is_closed and self.is_locked:
            raise Exception(
                'Вызов toggle_lock() у закрытой ведомости {}'.format(self.pk)
            )

        self.is_locked = not self.is_locked
        self.operations().update(
            is_closed=self.is_locked
        )
        self.save()

    def operations(self):
        return finance.models.Operation.objects.filter(
            paysheet_entry_operation__entry__paysheet=self
        )

    def account_operations(self, account_pk, day=None):
        operations = self.operations()
        if day:
            operations = operations.filter(
                timepoint__date=day
            )

        return (
            operations.filter(debet__pk=account_pk),
            operations.filter(credit__pk=account_pk)
        )

    def amount(self, worker):
        if self.is_closed:
            return self.paysheet_entries.get(worker=worker).operation.amount
        else:
            return self.paysheet_entries.get(worker=worker).amount

    def _operation_param(self):
        if self.is_closed:
            return 'operation__amount'
        else:
            return 'amount'

    # Todo: merge with Prepayment?
    @cached_property
    def total_amount(self):
        if not hasattr(self, 'total_sum',):
            return Paysheet_v2.objects.with_total_amount(
            ).values_list(
                'total_sum',
                flat=True
            ).get(pk=self.pk)
        return getattr(self, 'total_sum')

    @cached_property
    def normal_workers_total_amount(self):
        if not hasattr(self, 'total_sum_normal',):
            return Paysheet_v2.objects.with_total_amount(
                normal_only=True
            ).values_list(
                'total_sum_normal',
                flat=True
            ).get(pk=self.pk)
        return getattr(self, 'total_sum_normal')

    def workers(self):
        return Worker.objects.annotate(
            on_this_paysheet=Exists(
                Paysheet_v2Entry.objects.filter(
                    paysheet=self,
                    worker=OuterRef('pk')
                )
            )
        ).filter(on_this_paysheet=True)

    def add_worker(self, worker, filter_payments_by_customer=True):
        entry, created = Paysheet_v2Entry.objects.get_or_create(
            paysheet=self,
            worker=worker,
        )

        if not created:
            return False

        account = worker.worker_account.account

        # Todo: more nice way to filter operations?
        operations = finance.models.Operation.objects.filter(
            # Paysheet_v2Entry (завершающая операция)
            paysheet_v2_operation__isnull=True,
        ).exclude(
            # Для случая, когда оба счета операции - счета работников
            # Тогда она может попасть в 2 ведомости, или 2 раза в одну
            paysheet_entry_operation__entry__worker=worker
        )

        # Todo: check if it is correct interval selection
        operations = operations.filter(
            Q(debet=account) | Q(credit=account),
            timepoint__date__range=(self.first_day, self.last_day),
        )
        if self.customer_id is not None and filter_payments_by_customer:
            if self.location:
                operations = operations.filter(
                    Q(turnoutoperationtopay__isnull=True) |
                    Q(turnoutoperationtopay__turnout__timesheet__cust_location=self.location),
                )
            else:
                operations = operations.filter(
                    Q(turnoutoperationtopay__isnull=True) |
                    Q(turnoutoperationtopay__turnout__timesheet__customer=self.customer),
                )

        if self.is_locked:
            operations.update(is_closed=True)

        for operation in operations:
            Paysheet_v2EntryOperation.objects.create(
                entry=entry,
                operation=operation
            )

        entry.update_amount()

        return True

    def remove_worker(self, worker_pk):
        entry = self.paysheet_entries.get(worker__pk=worker_pk)
        entry.delete()

    def reset_workers(self, workers_pks, filter_payments_by_customer=True):
        with transaction.atomic():
            for worker_pk in workers_pks:
                worker = Worker.objects.get(pk=worker_pk)
                self.remove_worker(worker.pk)
                self.add_worker(worker, filter_payments_by_customer)

    @transaction.atomic
    def recreate(self):
        self.paysheet_entries.all().delete()
        workers = _workers_for_paysheet(
            self.customer,
            self.location,
            self.first_day,
            self.last_day
        )
        for worker in workers:
            self.add_worker(worker)

    def remove_operation(self, operation_pk):
        entry = self.paysheet_entries.get(
            paysheet_entry_operations__operation__pk=operation_pk
        )
        entry.remove_operation(operation_pk)

    def ready_to_close(self):
        entries_qs = self.paysheet_entries.all(
        ).with_is_worker_selfemployed(
        )
        # Если в ведомости есть несамозанятые, то должны быть фотки
        if (entries_qs.filter(is_worker_selfemployed=False).exists()
                and not get_photos(self).exists()):
            return False

        # У всех самозанятых должен быть чек, или в реестре, или привязанный к записи
        entries_without_receipt_qs = entries_qs.filter(
            is_worker_selfemployed=True
        ).annotate(
            has_registry_receipt=Exists(
                WorkerReceiptRegistryNum.objects.filter(
                    registry_num__paysheetregistry__paysheet=OuterRef('paysheet'),
                    worker_receipt__worker=OuterRef('worker'),
                )
            ),
            has_alternate_receipt=Exists(
                WorkerReceiptPaysheetEntry.objects.filter(
                    paysheet_entry=OuterRef('pk')
                )
            )
        ).exclude(
            has_registry_receipt=True
        ).exclude(
            has_alternate_receipt=True
        )
        if entries_without_receipt_qs.exists():
            return False

        # Закрывать можно только ведомость, в которой у каждого работника
        # остаток на счету не меньше того, что заработано на интервале.
        # И отрицательного сальдо в рамках операций в ведомости не должно быть.
        for entry in self.paysheet_entries.select_related('worker__worker_account__account'):
            account = entry.worker.worker_account.account
            if entry.amount < 0:
                return False
            if entry.amount >= (-1 * account.turnover_saldo()) + Paysheet_v2.ALLOWED_DISCREPANCY:
                return False

        return True

    @transaction.atomic
    def close(self, author, payment_account):
        if self.is_closed:
            raise Exception(
                'Вызов close() у закрытой ведомости {}'.format(self.pk)
            )

        for entry in self.paysheet_entries.all():
            account = entry.worker.worker_account.account
            if entry.operation:
                raise Exception(
                    'Final operation already exists in entry.'
                )
            operation = finance.models.Operation.objects.create(
                author=author,
                timepoint=datetime.datetime.combine(
                    self.last_day,
                    datetime.time(23, 59)
                ),
                comment=str(self),
                debet=account,
                credit=payment_account,
                amount=entry.amount,
                is_closed=True
            )
            entry.operation = operation
            entry.save()

        if not self.is_locked:
            self.toggle_lock()

        self.is_closed = True
        self.save()

    def close_with_default_payment_account(self, author):
        accountable_person = get_accountable_person(self)
        account = accountable_person.account_71

        self.close(author, account)


# Todo: merge with paysheet
@transaction.atomic
def create_paysheet(
        author,
        accountable_person,
        first_day,
        last_day,
        customer,
        location,
        workers=None
):

    paysheet = Paysheet_v2.objects.create(
        author=author,
        customer=customer,
        location=location,
        first_day=first_day,
        last_day=last_day,
    )
    if accountable_person:
        set_accountable_person(paysheet, accountable_person)

    if workers is not None:
        workers = _exclude_workers_with_active_paysheets(workers)
        if workers.count() == 0:  # compiler bug workaround
            raise Exception(
                'Похоже, что выбранный работник уже есть в другой открытой ведомости'
            )
    else:
        workers = _workers_for_paysheet(
            customer,
            location,
            first_day,
            last_day
        )

    workers = workers.select_related('worker_account__account')

    for worker in workers:
        paysheet.add_worker(worker)

    registry_num = RegistryNum.objects.create()
    PaysheetRegistry.objects.create(
        paysheet=paysheet,
        registry_num=registry_num
    )

    return paysheet


class PaysheetEntryQuerySet(models.QuerySet):
    def with_is_worker_selfemployed(self):
        return self.annotate(
            is_worker_selfemployed=Exists(
                WorkerSelfEmploymentData.objects.filter(
                    deletion_ts__isnull=True,
                    worker=OuterRef('worker_id')
                )
            )
        )

    def with_has_successful_talkbank_payment(self):
        from .paysheet import PaysheetEntryTalkBankPayment

        return self.annotate(
            has_successful_talkbank_payment=Exists(
                PaysheetEntryTalkBankPayment.objects.filter(
                    paysheet_entry=OuterRef('pk')
                )
            )
        )


class Paysheet_v2Entry(models.Model):
    paysheet = models.ForeignKey(
        Paysheet_v2,
        on_delete=models.CASCADE,
        related_name='paysheet_entries',
        verbose_name='Ведомость'
    )

    worker = models.ForeignKey(
        Worker,
        on_delete=models.PROTECT,
        related_name='paysheet_v2_entries',
        verbose_name='Работник'
    )

    amount = models.DecimalField(
        max_digits=30,
        decimal_places=2,
        default=0,
        verbose_name='Фактическая сумма'
    )

    operation = models.OneToOneField(
        finance.models.Operation,
        on_delete=models.PROTECT,
        related_name='paysheet_v2_operation',
        verbose_name='Завершающая операция',
        null=True,
        blank=True
    )

    objects = PaysheetEntryQuerySet.as_manager()

    def __str__(self):
        return 'Запись {} в ведомости {}, {} [{}]'.format(
            self.pk,
            self.paysheet.pk,
            self.worker,
            self.amount
        )

    def update_amount(self, amount=None):
        if self.operation:
            raise Exception('update_amount for already closed Paysheet_v2Entry')

        account = self.worker.worker_account.account

        if amount is None:
            operations = finance.models.Operation.objects.filter(
                paysheet_entry_operation__entry=self
            )
            saldo = _saldo(
                operations.filter(debet=account),
                operations.filter(credit=account)
            )
            amount = max(
                0,
                min(
                    saldo,
                    -1 * account.turnover_saldo()
                )
            )
            if self.worker.selfemployment_data.filter(deletion_ts__isnull=True).first() is None:
                amount = math.floor(amount / decimal.Decimal(100.0)) * 100
        else:
            amount = max(0, min(amount, -1 * account.turnover_saldo()))

        self.amount = amount
        self.save()

    def remove_operation(self, operation_pk):
        operation = self.paysheet_entry_operations.get(
            operation__pk=operation_pk
        )
        operation.delete()
        self.update_amount()


def find_closest_paysheet_entry(worker, day, amount):
    first_day = day - datetime.timedelta(days=6)
    last_day = day

    max_amount = amount + 5
    min_amount = amount * decimal.Decimal(0.93)

    entries = Paysheet_v2Entry.objects.filter(
        worker=worker,
        operation__isnull=False,
        operation__timepoint__date__range=(first_day, last_day),
        operation__amount__range=(min_amount, max_amount),
        operation__importednode__isnull=True,
    )

    if not entries.exists():
        return None

    entries = list(entries)

    entry = entries[0]

    min_distance = last_day - entry.operation.timepoint.date()

    for e in entries[1:]:
        dst = last_day - e.operation.timepoint.date()
        if dst < min_distance:
            entry = e
            min_distance = dst

    return entry


# Todo: deprecate at some point in near future (asap)
def fix_entry_amount_if_need_to(entry, amount, author):
    operation = entry.operation

    delta = amount - operation.amount

    if delta > 0:
        entry_operation = entry.paysheet_entry_operations.order_by(
            '-operation__timepoint'
        ).first()

        compensation = finance.models.Operation.objects.create(
            author=author,
            timepoint=operation.timepoint-datetime.timedelta(seconds=1),
            comment='Дополнительное начисление в связи с самозанятостью',
            debet=entry_operation.operation.debet,   # < v These are dangerous
            credit=entry_operation.operation.credit, #
            amount=delta,
        )

        Paysheet_v2EntryOperation.objects.create(
            entry=entry,
            operation=compensation
        )


class Paysheet_v2EntryOperation(models.Model):
    entry = models.ForeignKey(
        Paysheet_v2Entry,
        on_delete=models.CASCADE,
        related_name='paysheet_entry_operations',
        verbose_name='Запись в ведомости'
    )

    operation = models.ForeignKey(
        finance.models.Operation,
        on_delete=models.PROTECT,
        related_name='paysheet_entry_operation',
        verbose_name='Операция'
    )

    def __str__(self):
        return str(self.operation)


@receiver(pre_delete, sender=Paysheet_v2EntryOperation)
def _paysheet_entry_operation_pre_delete(sender, instance, **kwargs):
    finance.models.Operation.objects.filter(
        pk=instance.operation.pk
    ).update(
        is_closed=False
    )


class PaysheetParams(models.Model):
    timestamp = models.DateTimeField(
        verbose_name='Время создания',
        default=timezone.now
    )

    kind = models.CharField(
        verbose_name='Тип',
        max_length=32,
        choices=(
            ('prepayment', 'Авансовая'),
            ('paysheet', 'Зарплатная'),
        )
    )
    customer = models.ForeignKey(
        Customer,
        on_delete=models.PROTECT,
        verbose_name='Клиент',
    )
    location = models.ForeignKey(
        CustomerLocation,
        on_delete=models.PROTECT,
        verbose_name='Объект',
        blank=True,
        null=True
    )
    first_day = models.DateField(
        verbose_name='Первый день периода'
    )
    last_day = models.DateField(
        verbose_name='Последний день периода'
    )
    pay_day = models.DateField(
        verbose_name='Планируемая дата выплаты'
    )
    accountable_person = models.ForeignKey(
        AccountablePerson,
        on_delete=models.PROTECT,
        verbose_name='Подотчетное лицо',
    )

    def __str__(self):
        if self.location:
            description = '{}/{}'.format(
                self.customer,
                self.location.location_name
            )
        else:
            description = str(self.customer)

        kind = 'Аванс' if self.kind == 'prepayment' else 'Ведомость'
        return '{} {} c {} по {} (выплата {})'.format(
            kind,
            description,
            self.first_day.strftime('%d.%m'),
            self.last_day.strftime('%d.%m'),
            self.pay_day.strftime('%d.%m')
        )


class RegistryNum(models.Model):
    pass


class PaysheetRegistry(models.Model):
    paysheet = models.ForeignKey(
        Paysheet_v2,
        verbose_name='Ведомость',
        on_delete=models.CASCADE,
    )
    registry_num = models.OneToOneField(
        RegistryNum,
        verbose_name='Номер реестра',
        on_delete=models.PROTECT,
    )

    def __str__(self):
        return f'Ведомость №{self.paysheet.pk}, реестр №{self.registry_num_id}'


#Todo: this is a temporary model
class TestRegistry(models.Model):
    day = models.DateField(
        verbose_name='День создания'
    )
    registry_num = models.ForeignKey(
        RegistryNum,
        verbose_name='Номер реестра',
        on_delete=models.PROTECT,
    )


class WorkerReceiptQueryset(models.QuerySet):
    def with_paysheet_workdays(self, paysheet_id):
        from the_redhuman_is.services.paysheet import annotate_with_paysheet_workdays
        return annotate_with_paysheet_workdays(
            self,
            paysheet_id,
            OuterRef('worker')
        )


class WorkerReceipt(models.Model):
    timestamp = models.DateTimeField(
        verbose_name='Время создания',
        default=timezone.now
    )
    author = models.ForeignKey(
        User,
        verbose_name='Автор',
        on_delete=models.PROTECT,
    )

    worker = models.ForeignKey(
        Worker,
        verbose_name='Работник',
        on_delete=models.PROTECT,
    )
    url = models.URLField(
        verbose_name='Адрес чека',
        max_length=200,
        unique=True,
    )
    date = models.DateField(
        verbose_name='Дата чека',
    )

    objects = WorkerReceiptQueryset.as_manager()

    def __str__(self):
        return f'{self.worker}'


class WorkerReceiptRegistryNum(models.Model):
    worker_receipt = models.OneToOneField(
        WorkerReceipt,
        verbose_name='Чек',
        on_delete=models.PROTECT,
    )
    registry_num = models.ForeignKey(
        RegistryNum,
        verbose_name='Номер реестра',
        on_delete=models.PROTECT,
    )

    def __str__(self):
        return f'{self.worker_receipt.worker} {self.registry_num_id}'


class WorkerReceiptPaysheetEntry(models.Model):
    worker_receipt = models.OneToOneField(
        WorkerReceipt,
        verbose_name='Чек',
        on_delete=models.PROTECT,
    )
    paysheet_entry = models.OneToOneField(
        Paysheet_v2Entry,
        verbose_name='Запись в ведомости',
        on_delete=models.PROTECT
    )

    def __str__(self):
        return str(self.worker_receipt.worker)


class PayoutRequest(models.Model):
    timestamp = models.DateTimeField(
        verbose_name='Время создания',
        default=timezone.now
    )
    author = models.ForeignKey(
        User,
        verbose_name='Автор',
        on_delete=models.PROTECT,
    )

    worker = models.ForeignKey(
        Worker,
        verbose_name='Работник',
        on_delete=models.PROTECT,
    )
    paysheet_entry = models.ForeignKey(
        Paysheet_v2Entry,
        verbose_name='Запись в ведомости',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['worker'],
                condition=Q(paysheet_entry__isnull=True),
                name='unique_outstanding_payout_request',
            )
        ]


def annotate_with_paysheet_workdays(
        queryset,
        paysheet_ref,
        worker_ref,
):
    from the_redhuman_is.models import TurnoutOperationToPay
    tzinfo = timezone.get_current_timezone()
    return queryset.annotate(
        paysheet_workdays=Subquery(
            Paysheet_v2EntryOperation.objects.annotate(
                has_turnout_operation_to_pay=Exists(
                    TurnoutOperationToPay.objects.filter(
                        operation=OuterRef('operation'),
                    )
                )
            ).filter(
                entry__paysheet=paysheet_ref,
                entry__worker=worker_ref,
            ).values(
                'entry__worker'
            ).annotate(
                workday_fields=JSONObject(
                    start=TruncDate(Min('operation__timepoint'), tzinfo=tzinfo),
                    end=TruncDate(Max('operation__timepoint'), tzinfo=tzinfo),
                )
            ).values(
                'workday_fields'
            ),
            output_field=JSONField()
        )
    )
