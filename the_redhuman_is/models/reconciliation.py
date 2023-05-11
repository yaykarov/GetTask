# -*- coding: utf-8 -*-

import datetime
import itertools
from functools import cached_property

from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError

from django.db import (
    OperationalError,
    models,
    transaction,
)

from django.db.models import (
    Case,
    CharField,
    Count,
    DateField,
    DecimalField,
    Exists,
    ExpressionWrapper,
    F,
    IntegerField,
    Max,
    OuterRef,
    Q,
    QuerySet,
    Subquery,
    Sum,
    Value,
    When,
)
from django.db.models.functions import (
    Cast,
    Coalesce,
    Concat,
)

from finance.models import (
    IntervalPayment,
    Operation,
    amount_sum,
)

from the_redhuman_is.models.models import (
    Customer,
    CustomerLegalEntity,
    CustomerLocation,
    CustomerOperatingAccounts,
    TimeSheet,
    WorkerTurnout,
    intersected_legal_entities,
)
from the_redhuman_is.models.legal_entity import vat_20
from the_redhuman_is.models.worker import Worker
from the_redhuman_is.models.photo import Photo

from the_redhuman_is.models.fine_utils import (
    OperationsPack,
    OperationsPackItem,
)

from utils.date_time import (
    split_by_months,
    string_from_date,
)
from utils.functools import all_equal

from utils.numbers import ZERO_OO


RECONCILIATION_DEADLINE = datetime.timedelta(days=14)


class ReconciliationQuerySet(QuerySet):

    @staticmethod
    def _get_subquery(field):
        """
        A Reconciliation relates to an Operation through two model chains:

        Operation -< TurnoutCustomerOperation -- WorkerTurnout >- TimeSheet >- Customer -< Reconciliation
                                                                  TimeSheet >- CustomerLocation -< Reconciliation

        and

        Operation -- CustomerFine >- WorkerTurnout >- TimeSheet >- Customer -< Reconciliation
                                                      TimeSheet >- CustomerLocation -< Reconciliation

        This method returns a Subquery to annotate a Reconciliation
        with the sum of Operation.amount entries related to it through either chain.

        The chains are similar enough that it is possible to encapsulate
        the logic of both subqueries in one method.

        :param field: model name, either 'turnoutcustomeroperation' or 'customerfine'
        :return: Subquery to annotate reconciliation queryset with aggregate sums
        """
        return Subquery(
            Operation.objects.filter(
                **{
                    f'{field}__turnout__timesheet__customer': OuterRef('customer'),
                    f'{field}__turnout__timesheet__sheet_date__gte': OuterRef('first_day'),
                    f'{field}__turnout__timesheet__sheet_date__lte': OuterRef('last_day'),
                }
            ).annotate(
                _sentinel=Value(1, output_field=IntegerField),
                recon_location=ExpressionWrapper(
                    OuterRef('location'),
                    output_field=IntegerField()
                )
            ).filter(
                Q(**{f'{field}__turnout__timesheet__cust_location': OuterRef('location')}) |
                Q(recon_location__isnull=True)
            ).order_by(
            ).values(
                '_sentinel'
            ).annotate(
                summ=Sum(
                    'amount',
                    output_field=DecimalField()
                )
            ).values(
                'summ'
            ),
            output_field=DecimalField()
        )

    def with_customer_sum(self):
        return self.annotate(
            sum_customer_=Coalesce(
                self._get_subquery('turnoutcustomeroperation'),
                0,
                output_field=DecimalField()
            )
        )

    def with_fines_sum(self):
        return self.annotate(
            sum_fines_=Coalesce(
                self._get_subquery('customerfine'),
                0,
                output_field=DecimalField()
            )
        )

    def with_total_sum(self):
        return self.with_customer_sum(
        ).with_fines_sum(
        ).annotate(
            sum_total_=F('sum_customer_') - F('sum_fines_')
        )

    def with_is_ready_to_close(self):
        return self.annotate(
            is_ready_to_close_=Exists(
                Photo.objects.filter(
                    content_type=ContentType.objects.get_for_model(Reconciliation),
                    object_id=OuterRef('pk')
                )
            )
        )

    def with_short_name(self):
        return self.annotate(
            short_name_=Concat(
                F('customer__cust_name'),
                Case(
                    When(
                        location__isnull=False,
                        then=Value('/')
                    ),
                    output_field=CharField()
                ),
                F('location__location_name'),
                output_field=CharField()
            )
        )

    def with_has_photos(self):
        return self.annotate(
            has_photos_=Exists(
                Photo.objects.filter(
                    content_type=ContentType.objects.get_for_model(Reconciliation),
                    object_id=OuterRef('pk')
                )
            )
        )

    def with_deadline(self):
        return self.annotate(
            deadline_=Cast(
                ExpressionWrapper(
                    F('last_day') + Value(RECONCILIATION_DEADLINE),
                    output_field=DateField()
                ),
                output_field=DateField()
            )
        )

    def with_payment_date(self):
        return self.annotate(
            payment_date_=Cast(
                Subquery(
                    ReconciliationPaymentOperation.objects.filter(
                        reconciliation=OuterRef('pk')
                    ).order_by(
                        '-operation__timepoint'
                    ).values(
                        'operation__timepoint'
                    )[:1],
                    output_field=DateField()
                ),
                output_field=DateField()
            )
        )

    def with_legal_entity(self):
        return self.annotate(
            legal_entity_=Subquery(
                CustomerLegalEntity.objects.filter(
                    Q(last_day__isnull=True) |
                    Q(last_day__gte=OuterRef('last_day')),
                    first_day__lte=OuterRef('first_day'),
                    customer=OuterRef('customer')
                ).values(
                    'legal_entity__short_name'
                )[:1]
            )
        )

    def with_status(self):
        return self.with_has_photos().annotate(
            status_=Case(
                When(
                    payment_operation__isnull=False,
                    then=Value('paid')
                ),
                When(
                    has_photos_=True,
                    then=Value('in_payment')
                ),
                When(
                    confirmation__isnull=False,
                    then=Value('confirmed')
                ),
                default=Value('new'),
                output_field=CharField()
            )
        )

    def with_invoice_number(self):
        return self.annotate(
            invoice_number=Coalesce(
                Subquery(
                    ReconciliationInvoice.objects.filter(
                        reconciliation=OuterRef('pk')
                    ).values(
                        'number'
                    )
                ),
                Value('не заполнен')
            )
        )

    def with_suspension_date(self):
        return self.annotate(
            last_unpaid_date=Subquery(
                Reconciliation.objects.annotate(
                    outer_location=ExpressionWrapper(
                        OuterRef('location'), output_field=IntegerField()
                    )
                ).filter(
                    Q(location=OuterRef('location')) |
                    Q(outer_location__isnull=True),
                    customer=OuterRef('customer'),
                    payment_operation__isnull=True,
                ).order_by(
                    'last_day'
                ).values(
                    'last_day'
                )[:1],
                output_field=DateField()
            )
        ).annotate(
            suspension_date=Cast(
                F('last_unpaid_date') + Value(datetime.timedelta(days=21)),
                output_field=DateField()
            )
        )


class Reconciliation(models.Model):
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
        verbose_name='Клиент',
    )
    location = models.ForeignKey(
        CustomerLocation,
        on_delete=models.PROTECT,
        related_name='reconciliations',
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
        verbose_name='Подписан акт'
    )

    objects = ReconciliationQuerySet.as_manager()

    def __str__(self):
        return 'Сверка №{}, {}, с {} по {}'.format(
            self.pk,
            self.short_name,
            string_from_date(self.first_day),
            string_from_date(self.last_day)
        )

    class ReconException(Exception):
        pass

    def timesheets(self):
        sheets = TimeSheet.objects.filter(
            customer=self.customer,
            sheet_date__range=(self.first_day, self.last_day)
        )
        if self.location:
            sheets = sheets.filter(
                cust_location=self.location
            )
        return sheets.select_related(
            'customer',
            'customerorder',
            'cust_location',
        ).annotate(
            Count('worker_turnouts'),
            Sum('worker_turnouts__hours_worked'),
            customer_amount=Sum('worker_turnouts__turnoutcustomeroperation__operation__amount'),
        ).order_by(
            'sheet_date'
        )

    def turnouts(self):
        return WorkerTurnout.objects.filter(
            timesheet__in=self.timesheets()
        )

    def fines(self):
        operations = Operation.objects.filter(
            customerfine__turnout__timesheet__customer=self.customer,
            customerfine__turnout__timesheet__sheet_date__range=(self.first_day, self.last_day)
        )
        if self.location:
            operations = operations.filter(
                customerfine__turnout__timesheet__cust_location=self.location,
            )
        return operations.annotate(
            worker_name=Subquery(
                Worker.objects.filter(
                    worker_turnouts__customerfine__operation__pk=OuterRef('pk')
                ).with_full_name(
                ).values(
                    'full_name'
                ),
                output_field=CharField()
            ),
            worker_pk=Subquery(
                Worker.objects.filter(
                    worker_turnouts__customerfine__operation__pk=OuterRef('pk')
                ).values('pk'),
            ),
        ).order_by(
            'timepoint'
        )

    def total_hours(self):
        return self.turnouts(
        ).aggregate(
            hours=Sum('hours_worked')
        )['hours'] or 0

    def customer_operations(self):
        return Operation.objects.filter(
            turnoutcustomeroperation__turnout__timesheet__in=self.timesheets()
        )

    @cached_property
    def sum_customer(self):
        if not hasattr(self, 'sum_customer_',):
            return Reconciliation.objects.with_customer_sum(
            ).values_list(
                'sum_customer_',
                flat=True
            ).get(pk=self.pk)
        return getattr(self, 'sum_customer_')

    @cached_property
    def sum_fines(self):
        if not hasattr(self, 'sum_fines_'):
            return Reconciliation.objects.with_fines_sum(
            ).values_list(
                'sum_fines_',
                flat=True
            ).get(pk=self.pk)
        return getattr(self, 'sum_fines_')

    @cached_property
    def sum_total(self):
        if not hasattr(self, 'sum_total_'):
            return Reconciliation.objects.with_total_sum(
            ).values_list(
                'sum_total_',
                flat=True
            ).get(pk=self.pk)
        return getattr(self, 'sum_total_')

    @cached_property
    def is_ready_to_close(self):
        if not hasattr(self, 'is_ready_to_close_'):
            return Reconciliation.objects.with_is_ready_to_close(
            ).values_list(
                'is_ready_to_close_',
                flat=True
            ).get(pk=self.pk)
        return getattr(self, 'is_ready_to_close_')

    @cached_property
    def short_name(self):
        if not hasattr(self, 'short_name_'):
            return Reconciliation.objects.with_short_name(
            ).values_list(
                'short_name_',
                flat=True
            ).get(pk=self.pk)
        return getattr(self, 'short_name_')

    @cached_property
    def has_photos(self):
        if not hasattr(self, 'has_photos_'):
            return Reconciliation.objects.with_has_photos(
            ).values_list(
                'has_photos_',
                flat=True
            ).get(pk=self.pk)
        return getattr(self, 'has_photos_')

    @cached_property
    def deadline(self):
        if not hasattr(self, 'deadline_'):
            return Reconciliation.objects.with_deadline(
            ).values_list(
                'deadline_',
                flat=True
            ).get(pk=self.pk)
        return getattr(self, 'deadline_')

    @cached_property
    def payment_date(self):
        if not hasattr(self, 'payment_date_'):
            return Reconciliation.objects.with_payment_date(
            ).values_list(
                'payment_date_',
                flat=True
            ).get(pk=self.pk)
        return getattr(self, 'payment_date_')

    @cached_property
    def legal_entity(self):
        if not hasattr(self, 'legal_entity_'):
            return Reconciliation.objects.with_legal_entity(
            ).values_list(
                'legal_entity_',
                flat=True
            ).get(pk=self.pk)
        return getattr(self, 'legal_entity_')

    @cached_property
    def status(self):
        if not hasattr(self, 'status_'):
            return Reconciliation.objects.with_status(
            ).values_list(
                'status_',
                flat=True
            ).get(pk=self.pk)
        return getattr(self, 'status_')

    @transaction.atomic
    def close(self, author, legal_entity):
        if self.is_closed:
            raise Reconciliation.ReconException(
                f'Вызов close() у завершенной сверки №{self.pk}'
            )
        try:
            current_legal_entity = intersected_legal_entities(
                self.customer,
                self.first_day,
                self.last_day
            ).get()
        except (CustomerLegalEntity.MultipleObjectsReturned, CustomerLegalEntity.DoesNotExist):
            raise Reconciliation.ReconException(
                'На интервале с {} по {} у {} либо не установлено юрлицо,'
                ' либо их несколько'.format(
                    string_from_date(self.first_day),
                    string_from_date(self.last_day),
                    self.customer,
                )
            )
        if current_legal_entity.legal_entity != legal_entity:
            raise Reconciliation.ReconException(
                'Похоже, с момента открытия страницы со сверкой у клиента изменилось юрлицо,'
                ' откройте сверку заново'
            )
        try:
            Reconciliation.objects.select_for_update(
                nowait=True
            ).get(
                pk=self.pk
            )
        except OperationalError:
            raise Reconciliation.ReconException(
                f'Вызов close() у закрываемой сверки №{self.pk}'
            )

        accounts = CustomerOperatingAccounts.objects.get(
            customer=self.customer
        )

        operations_pack = OperationsPack.objects.create(
            author=author,
            comment=str(self)
        )

        def _create_operation(debit, credit, first_day, last_day, amount, comment):
            operation = Operation.objects.create(
                author=author,
                timepoint=datetime.datetime.combine(
                    last_day,
                    datetime.time(23, 59),
                ),
                comment=comment,
                debet=debit,
                credit=credit,
                amount=amount,
                is_closed=True
            )
            IntervalPayment.objects.create(
                operation=operation,
                first_day=first_day,
                last_day=last_day
            )
            OperationsPackItem.objects.create(
                pack=operations_pack,
                operation=operation
            )

        def _create_operations(
                debit,
                credit,
                debit_operations,
                credit_operations,
                comment_suffix,
                amount_func=amount_sum
        ):

            if not debit_operations.exists():
                if not credit_operations or not credit_operations.exists():
                    # Nothing to do
                    return

            intervals = split_by_months(self.first_day, self.last_day)
            for i, (i_first_day, i_last_day) in enumerate(intervals):
                amount = amount_func(
                    debit_operations.filter(
                        timepoint__date__range=(i_first_day, i_last_day)
                    )
                )
                if credit_operations:
                    amount = amount - amount_func(
                        credit_operations.filter(
                            timepoint__date__range=(i_first_day, i_last_day)
                        )
                    )
                _create_operation(
                    debit=debit,
                    credit=credit,
                    first_day=i_first_day,
                    last_day=i_last_day,
                    amount=amount,
                    comment=f'Часть {i + 1} из {len(intervals)}, {comment_suffix}'
                )

        def _vat_amount(operations):
            return vat_20(amount_sum(operations))

        # Д90.2/клиент <- К76/штрафы/клиент
        all_fines = self.fines()
        all_fines.update(is_closed=True)
        _create_operations(
            debit=accounts.account_90_2_root,
            credit=accounts.account_76_fines,
            debit_operations=all_fines,
            credit_operations=None,
            comment_suffix='{}, штрафы'.format(str(self)),
        )

        # Д62/клиент <- К76/непроактированные долги/клиент
        all_operations = self.customer_operations()
        all_operations.update(is_closed=True)
        total_amount = self.sum_total
        if total_amount > 0:
            _create_operation(
                debit=accounts.account_62_root,
                credit=accounts.account_76_debts,
                first_day=self.first_day,
                last_day=self.last_day,
                amount=total_amount,
                comment='{}, сумма'.format(str(self)),
            )

            if not legal_entity.uses_simple_tax_system():
                entity_accounts = legal_entity.legal_entity_general_tax_system_accounts
                _create_operations(
                    debit=accounts.account_90_3_root,
                    credit=entity_accounts.account_68_02,
                    debit_operations=all_operations,
                    credit_operations=self.fines(),
                    comment_suffix='{}, НДС'.format(str(self)),
                    amount_func=_vat_amount
                )

        for service in self.customer.customerservice_set.all():
            # Д76/непроактированные продажи/клиент/услуга <- К90.1/клиент/услуга
            operations = all_operations.filter(
                credit__account_76_service=service
            )
            _create_operations(
                debit=service.account_76,
                credit=service.account_90_1,
                debit_operations=operations,
                credit_operations=None,
                comment_suffix='{}, {}'.format(str(self), service.service.name),
            )

        self.is_closed = True
        self.save()

    @cached_property
    def total_vat_accured(self):
        try:
            pack = OperationsPack.objects.get(comment=str(self))
            operations = Operation.objects.filter(
                pack_items__pack=pack,
                comment__icontains='НДС',
            )

            return amount_sum(operations)

        except OperationsPack.DoesNotExist:
            pass

        return ZERO_OO

    @cached_property
    def total_vat_calculated(self):
        return vat_20(self.sum_total)


class ReconciliationInvoice(models.Model):
    reconciliation = models.OneToOneField(
        Reconciliation,
        related_name='invoice',
        on_delete=models.PROTECT
    )
    number = models.CharField(
        max_length=40,
        verbose_name='Номер счета',
    )
    date = models.DateField(
        verbose_name='Дата счета',
    )


def _partial_validate_fixed_first_last_day(customer, location, interval):
    if interval.start > interval.stop:
        raise ValidationError(
            'Первый день (%(start)s) не должен быть после последнего (%(stop)s)',
            params={
                'start': interval.start,
                'stop': interval.stop,
            },
            code='invalid'
        )
    # New consistency check
    locations = CustomerLocation.objects.filter(
        customer_id=customer
    ).with_last_reconciliation_date()
    if location:
        locations = locations.filter(pk=location.pk)

    errors = []
    if all(loc.last_reconciliation_date is None for loc in locations):
        return
    for loc in locations:
        if loc.last_reconciliation_date is None:
            errors.append(
                ValidationError(f'Нет сверок для объекта {loc}', code='invalid')
            )
        elif loc.last_reconciliation_date + datetime.timedelta(days=1) > interval.start:
            errors.append(
                ValidationError(
                    f'Попытка создать новую сверку с {interval.start},'
                    f' тогда как последний день предыдущего интервала'
                    f' для объекта {loc} - {loc.last_reconciliation_date}.'
                    f' Пересечений быть не должно.',
                    code='invalid'
                )
            )
        elif loc.last_reconciliation_date + datetime.timedelta(days=1) < interval.start:
            errors.append(
                ValidationError(
                    f'Попытка создать новую сверку с {interval.start},'
                    f' тогда как последний день предыдущего интервала'
                    f' для объекта {loc} - {loc.last_reconciliation_date}.'
                    f' Промежутков быть не должно.',
                    code='invalid'
                )
            )
    if errors:
        raise ValidationError(errors)


def get_reconciliation_interval(customer, location, interval):
    last_day = interval.stop
    locations = CustomerLocation.objects.filter(
        customer_id=customer
    ).with_last_reconciliation_date(
    ).filter(  # exclude new locations with no timesheets
        first_timesheet_date__isnull=False
    )
    if location:
        locations = locations.filter(pk=location.pk)

    first_day = None
    if all_equal(loc.last_reconciliation_date for loc in locations):
        try:
            last_reconciliation_date = next(iter(locations)).last_reconciliation_date
            if last_reconciliation_date is not None:
                first_day = last_reconciliation_date + datetime.timedelta(days=1)
        except StopIteration:
            pass
    else:
        raise ValidationError(
            [
                ValidationError(
                    f'Объект {loc}, последняя сверка {loc.last_reconciliation_date}',
                    code='invalid'
                )
                for loc in locations
            ]
        )

    if first_day is None:
        timesheets = TimeSheet.objects.filter(
            customer=customer
        ).order_by(
            'sheet_date'
        )
        if location:
            timesheets = timesheets.filter(cust_location=location)
        first_day = timesheets.order_by(
            'sheet_date'
        ).values_list(
            'sheet_date',
            flat=True
        ).first()
        if first_day is None:
            raise ValidationError(
                'Предыдущие сверки и заявки отсутствуют.'
                ' Невозможно определить начальную дату.',
                code='invalid'
            )

    if first_day > last_day:
        raise ValidationError(
            f'Последний день сверки для {customer}, {location}'
            f' не может быть раньше {first_day}',
            code='invalid'
        )
    return slice(first_day, last_day)


def _validate_intersected_legal_entities(customer, interval):
    legal_entities = list(
        intersected_legal_entities(
            customer, interval.start, interval.stop
        ).values('legal_entity__short_name', 'first_day', 'last_day')
    )
    if len(legal_entities) == 0:
        raise ValidationError(
            'На интервале с %(start)s по %(stop)s у %(customer)s не установлено юрлицо',
            params={
                'start': string_from_date(interval.start),
                'stop': string_from_date(interval.stop),
                'customer': customer,
            },
            code='invalid'
        )
    elif len(legal_entities) > 1:
        raise ValidationError(
            'На интервале с %(start)s по %(stop)s у %(customer)s'
            ' более одного юрлица: %(entities)s',
            params={
                'start': string_from_date(interval.start),
                'stop': string_from_date(interval.stop),
                'customer': customer,
                'entities': ', '.join(
                    '{legal_entity__short_name} ({first_day} - {last_day})'.format(**entity)
                    for entity in legal_entities
                )
            },
            code='invalid'
        )


def clean_reconciliation(customer, location, interval):
    if interval.start is not None:
        _validate_intersected_legal_entities(customer, interval)
        _partial_validate_fixed_first_last_day(customer, location, interval)
    else:
        interval = get_reconciliation_interval(customer, location, interval)
        _validate_intersected_legal_entities(customer, interval)
    return interval


@transaction.atomic
def create_reconciliation(author, customer, location, first_day, last_day):
    interval = clean_reconciliation(customer, location, slice(first_day, last_day))
    reconciliation = Reconciliation.objects.create(
        author=author,
        customer=customer,
        location=location,
        first_day=interval.start,
        last_day=interval.stop
    )
    return reconciliation


@transaction.atomic
def bulk_create_reconciliations(author, customer, last_day):
    locations = CustomerLocation.objects.filter(
        customer_id=customer
    ).with_last_reconciliation_date(
    ).annotate(
        first_unreconciled_date=Subquery(
            TimeSheet.objects.annotate(
                has_turnouts=Exists(
                    WorkerTurnout.objects.filter(
                        timesheet=OuterRef('pk')
                    )
                )
            ).filter(
                has_turnouts=True,
                cust_location=OuterRef('pk'),
                sheet_date__gt=Coalesce(  # include new locations with no reconciliations
                    OuterRef('last_reconciliation_date'),
                    datetime.date(1970, 1, 1)
                )
            ).order_by(
                'sheet_date'
            ).values(
                'sheet_date'
            )[:1]
        )
    ).filter(
        first_unreconciled_date__isnull=False
    )
    if not locations.exists():
        raise ValidationError(
            f'У клиента {customer} нет заявок для сверки.'
        )
    latest_reconciliation_date = locations.aggregate(
        Max('last_reconciliation_date')
    )['last_reconciliation_date__max']
    if latest_reconciliation_date is not None and last_day <= latest_reconciliation_date:
        raise ValidationError(
            f'Попытка создать новые сверки по {last_day},'
            f' тогда как последний день предыдущих интервалов'
            f' для клиента {customer} - {latest_reconciliation_date}.'
            f' Пересечений быть не должно.',
            code='invalid'
        )
    min_recon_start = min(
        itertools.chain(
            (
                loc.first_unreconciled_date
                for loc in locations
            ),
            (
                loc.last_reconciliation_date + datetime.timedelta(days=1)
                for loc in locations
                if loc.last_reconciliation_date is not None
            )
        )
    )
    _validate_intersected_legal_entities(customer, slice(min_recon_start, last_day))
    for loc in locations:
        if loc.last_reconciliation_date is not None:
            first_day = loc.last_reconciliation_date + datetime.timedelta(days=1)
        else:
            first_day = loc.first_unreconciled_date
        Reconciliation.objects.create(
            author=author,
            customer=customer,
            location=loc,
            first_day=first_day,
            last_day=last_day
        )


class ReconciliationConfirmation(models.Model):
    timestamp = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Время создания'
    )
    author = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        verbose_name='Автор'
    )

    reconciliation = models.OneToOneField(
        Reconciliation,
        on_delete=models.CASCADE,
        verbose_name='Сверка',
        related_name='confirmation'
    )

    def __str__(self):
        return '{}, {}, {}'.format(
            self.reconciliation.pk,
            self.author,
            string_from_date(self.timestamp)
        )


def confirm_reconciliation(reconciliation_pk, author):
    reconciliations = Reconciliation.objects.filter(
        customer__customeraccount__user=author  # Kind of access rights check
    )
    if hasattr(author, 'locationaccount'):
        reconciliations = reconciliations.filter(
            location__locationaccount__user=author
        )
    reconciliation = reconciliations.get(
        pk=reconciliation_pk
    )
    ReconciliationConfirmation.objects.create(
        author=author,
        reconciliation=reconciliation
    )


class ReconciliationPaymentOperation(models.Model):
    reconciliation = models.ForeignKey(
        Reconciliation,
        on_delete=models.CASCADE,
        verbose_name='Сверка',
        related_name='payment_operation'
    )
    operation = models.ForeignKey(
        Operation,
        on_delete=models.PROTECT,
        related_name='reconciliation_payment'
    )

    def __str__(self):
        return '{}, {}, {}'.format(
            self.reconciliation.pk,
            self.operation.author,
            self.operation
        )
