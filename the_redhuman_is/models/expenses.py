# -*- coding: utf-8 -*-

from django.db import (
    models,
    transaction,
)

from django.dispatch import receiver

from django.db.models import (
    Case,
    CharField,
    Exists,
    IntegerField,
    JSONField,
    OuterRef,
    Subquery,
    Sum,
    Value,
    When,
)

from django.db.models.functions import Coalesce, JSONObject

from django.db.models.signals import post_delete

from django.contrib.auth.models import User

from django.core.validators import MinValueValidator

from django.utils import timezone

import finance

from finance.model_utils import get_root_account

from the_redhuman_is.tasks import send_email

from utils import date_time
from utils.numbers import ZERO_OO


class Provider(models.Model):
    name = models.CharField(
        verbose_name='Имя',
        max_length=160
    )
    tax_code = models.CharField(
        verbose_name='Инн',
        max_length=160,
        blank=True,
        null=True
    )

    account_60 = models.OneToOneField(
        finance.models.Account,
        on_delete=models.PROTECT,
        verbose_name='60 поставщик',
        related_name='account_60_provider'
    )

    account_60_fines = models.OneToOneField(
        finance.models.Account,
        on_delete=models.PROTECT,
        verbose_name='60 штрафы/поставщик',
        related_name='account_60_provider_fines',
    )

    def serialize(self):
        data = {
            'pk': self.pk,
            'name': self.name,
        }
        if self.tax_code:
            data['tax_code'] = self.tax_code

        return data

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        self.account_60.name = self.name
        self.account_60.save()

        super(Provider, self).save(*args, **kwargs)


@receiver(post_delete, sender=Provider)
def _post_delete_provider(sender, instance, **kwargs):
    instance.account_60.delete()
    instance.account_60_fines.delete()


def ensure_expense_debit(cost_type_group, customer_pk, cost_type_pk):
    from the_redhuman_is.models.models import (
        AdministrationCostType,
        Customer,
        IndustrialCostType,
        MaterialType,
        get_or_create_customer_10_subaccount,
        get_or_create_customer_industrial_accounts,
    )

    if cost_type_group == 'administration':
        cost_type = AdministrationCostType.objects.get(pk=cost_type_pk)
        return cost_type.account_26
    elif cost_type_group == 'industrial':
        cost_type = IndustrialCostType.objects.get(pk=cost_type_pk)
        customer = Customer.objects.get(pk=customer_pk)
        accounts = get_or_create_customer_industrial_accounts(customer, cost_type)
        return accounts.account_20
    elif cost_type_group == 'material':
        cost_type = MaterialType.objects.get(pk=cost_type_pk)
        customer = Customer.objects.get(pk=customer_pk)
        subaccount = get_or_create_customer_10_subaccount(customer, cost_type)
        return subaccount.account_10
    else:
        raise Exception('Неизвестная группа расходов <{}>.'.format(cost_type_group))


@transaction.atomic
def create_provider(name, tax_code):
    root_60 = get_root_account('60')
    account_60 = finance.model_utils.ensure_account(root_60, name)
    account_60_fines = finance.model_utils.ensure_accounts_chain(
        root_60,
        ['Штрафы', name]
    )

    return Provider.objects.create(
        name=name,
        tax_code=tax_code,
        account_60=account_60,
        account_60_fines=account_60_fines,
    )


class ProviderFine(models.Model):
    operation = models.OneToOneField(
        finance.models.Operation,
        on_delete=models.PROTECT,
    )
    provider = models.ForeignKey(
        Provider,
        verbose_name='Поставщик',
        on_delete=models.PROTECT
    )

    def __str__(self):
        return '{} {}'.format(self.pk, self.operation.comment)


class Expense(models.Model):
    timestamp = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Время создания'
    )
    author = models.ForeignKey(
        User,
        verbose_name='Автор',
        on_delete=models.PROTECT
    )

    provider = models.ForeignKey(
        Provider,
        verbose_name='Поставщик',
        on_delete=models.PROTECT
    )
    amount = models.DecimalField(
        max_digits=30,
        decimal_places=2,
        verbose_name='Сумма',
        validators=[MinValueValidator(ZERO_OO)]
    )
    comment = models.TextField(
        verbose_name='Комментарий'
    )
    first_day = models.DateField(
        verbose_name='Первый день периода',
    )
    last_day = models.DateField(
        verbose_name='Последний день периода'
    )

    expense_debit = models.ForeignKey(
        finance.models.Account,
        on_delete=models.PROTECT,
        verbose_name='дебет расхода',
        related_name='expenses',
    )

    def make_operations_on_confirm(self):
        from the_redhuman_is.models.models import Customer10SubAccount
        return not Customer10SubAccount.objects.filter(account_10=self.expense_debit).exists()

    # Todo - new statuses
    def localized_status(self):
        if ExpensePaymentOperation.objects.filter(expense=self).exists():
            status = 'Оплачен'
        elif ExpenseConfirmation.objects.filter(expense=self).exists():
            status = 'Одобрен'
        elif ExpenseRejection.objects.filter(expense=self).exists():
            status = 'Отклонен'
        else:
            status = 'Новый'

        return status

    def serialize(self):
        from the_redhuman_is.models.models import (
            AdministrationCostType,
            CustomerIndustrialAccounts,
            Customer10SubAccount,
        )

        data = {
            'pk': self.pk,
            'provider': { 'key': self.provider.pk, 'label': self.provider.name },
            'amount': self.amount,
            'comment': self.comment,
            'first_day': date_time.string_from_date(self.first_day),
            'last_day': date_time.string_from_date(self.last_day),

        }
        cost_type = AdministrationCostType.objects.filter(account_26=self.expense_debit)
        if cost_type.exists():
            cost_type = cost_type.get()
            data['cost_type_group'] = 'administration'
            data['administration_cost_type'] = {
                'key': cost_type.pk,
                'label': cost_type.name
            }
            return data

        material_account = Customer10SubAccount.objects.filter(account_10=self.expense_debit)
        if material_account.exists():
            material_account = material_account.get()
            cost_type = material_account.material_type
            customer = material_account.customer
            data['cost_type_group'] = 'material'
            data['customer'] = {
                'key': customer.pk,
                'label': customer.cust_name
            }
            data['material_type'] = {
                'key': cost_type.pk,
                'label': cost_type.name
            }
            return data

        data['cost_type_group'] = 'industrial'
        accounts = CustomerIndustrialAccounts.objects.get(account_20=self.expense_debit)
        data['customer'] = {
            'key': accounts.customer.pk,
            'label': accounts.customer.cust_name
        }
        data['industrial_cost_type'] = {
            'key': accounts.cost_type.pk,
            'label': accounts.cost_type.name
        }

        return data

    def __str__(self):
        return '{} {}, {}, {}'.format(
            self.pk,
            self.author,
            self.provider.name,
            self.amount
        )


def _expense_title(expense, status=None):
    title = '{} расход №{}, "{}", {}р., {} {}'.format(
        status if status else expense.localized_status(),
        expense.pk,
        expense.provider.name,
        expense.amount,
        expense.author.first_name,
        expense.author.last_name
    )
    return title


def _notify_created(expense):
    html = '{} {} создал расход №{} на {}р.<br><br>Комментарий: "{}"<br><br>'.format(
        expense.author.first_name,
        expense.author.last_name,
        expense.pk,
        expense.amount,
        expense.comment
    ) + '<a href="https://is.gettask.ru/rf/expenses/">Ссылка на расходы</a>'

    for user in User.objects.filter(groups__name='Управление расходами'):
        if user.email:
            send_email(user.email, _expense_title(expense), html)


def _notify_updated(expense, force_comment=None):
    html = '{} расход №{} на {}р.<br><br>Комментарий: "{}"<br><br>'.format(
        expense.localized_status(),
        expense.pk,
        expense.amount,
        force_comment if force_comment else expense.comment
    ) + '<a href="https://is.gettask.ru/rf/expenses/">Ссылка на расходы</a>'

    if expense.author.email:
        send_email(expense.author.email, _expense_title(expense), html)

    for user in User.objects.filter(groups__name='Касса'):
        if user.email:
            send_email(user.email, _expense_title(expense), html)


def _notify_deleted(expense, author):
    html = '{} {} удалил расход №{} на {}р.<br><br>Комментарий: "{}"<br><br>'.format(
        author.first_name,
        author.last_name,
        expense.pk,
        expense.amount,
        expense.comment
    ) + '<a href="https://is.gettask.ru/rf/expenses/">Ссылка на расходы</a>'

    for user in User.objects.filter(groups__name__in=['Касса', 'Управление расходами']):
        if user.email:
            send_email(user.email, _expense_title(expense, 'Удален'), html)


def update_expense(
            pk,
            author,
            provider_pk,
            cost_type_group,
            customer_pk,
            cost_type_pk,
            amount,
            first_day,
            last_day,
            comment
        ):

    if (first_day and not last_day) or (last_day and not first_day):
        raise Exception(
            'Интервал не должен быть указан, либо должны быть указаны и начало и конец'
        )

    if not first_day:
        first_day = timezone.now()
        last_day = first_day

    if pk:
        with transaction.atomic():
            expense = Expense.objects.get(pk=pk)
            if (not author.is_superuser) and expense.author != author:
                raise Exception('Нет прав для данной операции')

            expense.provider = Provider.objects.get(pk=provider_pk)
            expense.amount = amount
            expense.comment = comment
            expense.first_day = first_day
            expense.last_day = last_day
            expense.expense_debit = ensure_expense_debit(
                cost_type_group,
                customer_pk,
                cost_type_pk
            )
            expense.save()

            if ExpenseConfirmation.objects.filter(expense=expense).exists():
                do_unconfirm_expense(expense)
                confirm_expense(expense, author, notify=False)

            payment = ExpensePaymentOperation.objects.filter(expense=expense)
            if payment.exists():
                payment = payment.get()
                operation = payment.operation
                finance.models.update_if_changed(
                    operation,
                    amount=expense.amount,
                    debit=expense.provider.account_60,
                    comment=expense.comment
                )
                interval = finance.models.IntervalPayment.objects.filter(operation=operation)
                if interval.exists():
                    interval = interval.get()
                    interval.first_day = expense.first_day
                    interval.last_day = expense.last_day
                    interval.save()

            return expense

    else:
        with transaction.atomic():
            expense = Expense.objects.create(
                author=author,
                provider=Provider.objects.get(pk=provider_pk),
                amount=amount,
                comment=comment,
                first_day=first_day,
                last_day=last_day,
                expense_debit=ensure_expense_debit(cost_type_group, customer_pk, cost_type_pk)
            )

        _notify_created(expense)

        return expense


def delete_expense(expense, author):
    with transaction.atomic():
        pk = expense.pk
        expense.delete()
    expense.pk = pk
    _notify_deleted(expense, author)


def actual_expenses(user, first_day, last_day):
    from the_redhuman_is.models.models import (
        AdministrationCostType,
        Customer10SubAccount,
        CustomerIndustrialAccounts,
        IndustrialCostType,
        MaterialType,
    )

    if user.is_superuser:
        expenses = Expense.objects.filter(
            expenserejection__isnull=True
        )
    else:
        expenses = Expense.objects.filter(
            author=user,
        )

    customer_annotation = {
        'customer_fields': JSONObject(
            id='customer_id',
            name='customer__cust_name',
        )
    }

    cost_type_values = [
        (AdministrationCostType, 'account_26', 'administration'),
        (IndustrialCostType, 'customer_accounts__account_20', 'industrial'),
        (MaterialType, 'customer10subaccount__account_10', 'material'),
    ]
    cost_type_subqueries = [
        Subquery(
            model.objects.filter(
                **{field: OuterRef('expense_debit')}
            ).annotate(
                cost_fields=JSONObject(
                    id='id',
                    name='name',
                    group=Value(group),
                )
            ).values('cost_fields'),
            output_field=JSONField()
        )
        for model, field, group in cost_type_values
    ]

    return expenses.filter(
        timestamp__date__range=(
            first_day,
            last_day
        )
    ).select_related(
        'provider'
    ).annotate(
        confirmed=Exists(
            ExpenseConfirmation.objects.filter(
                expense__pk=OuterRef('pk')
            )
        ),
        rejected=Exists(
            ExpenseRejection.objects.filter(
                expense__pk=OuterRef('pk')
            )
        ),
        supplied=Exists(
            ExpenseOperation.objects.filter(
                expense__pk=OuterRef('pk')
            )
        ),
        paid=Exists(
            ExpensePaymentOperation.objects.filter(
                expense__pk=OuterRef('pk')
            )
        ),
        supplied_amount=Coalesce(
            Subquery(
                finance.models.Operation.objects.filter(
                    expense__expense__pk=OuterRef('pk')
                ).values(
                    'expense__expense__pk'
                ).annotate(
                    Sum('amount', output_field=models.DecimalField())
                ).values('amount__sum'),
                output_field=models.DecimalField()
            ),
            ZERO_OO,
            output_field=models.DecimalField()
        ),
        paid_amount=Coalesce(
            Subquery(
                finance.models.Operation.objects.filter(
                    expense_payment__expense__pk=OuterRef('pk')
                ).values(
                    'expense_payment__expense__pk'
                ).annotate(
                    Sum('amount', output_field=models.DecimalField())
                ).values('amount__sum'),
                output_field=models.DecimalField()
            ),
            ZERO_OO,
            output_field=models.DecimalField()
        ),
        sold_amount=Coalesce(
            Subquery(
                finance.models.Operation.objects.filter(
                    expense_deduction__expense__pk=OuterRef('pk')
                ).values(
                    'expense_deduction__expense__pk'
                ).annotate(
                    Sum('amount', output_field=models.DecimalField())
                ).values('amount__sum'),
                output_field=models.DecimalField()
            ),
            ZERO_OO,
            output_field=models.DecimalField()
        ),
        is_material_expense=Exists(
            MaterialType.objects.filter(
                customer10subaccount__account_10=OuterRef('expense_debit')
            )
        ),
        cost_type=Coalesce(
            *cost_type_subqueries,
            output_field=JSONField()
        ),
        customer=Coalesce(
            Subquery(
                CustomerIndustrialAccounts.objects.filter(
                    account_20=OuterRef('expense_debit')
                ).annotate(
                    **customer_annotation
                ).values(
                    'customer_fields'
                ),
                output_field=JSONField(),
            ),
            Subquery(
                Customer10SubAccount.objects.filter(
                    account_10=OuterRef('expense_debit')
                ).annotate(
                    **customer_annotation
                ).values(
                    'customer_fields'
                ),
                output_field=JSONField()
            ),
            JSONObject(
                id=Value(None, output_field=IntegerField()),
                name=Value('Офис', output_field=CharField()),
            ),
            output_field=JSONField()
        )
    ).annotate(
        comment_=Coalesce(
            'expenserejection__comment',
            'comment',
            output_field=CharField()
        ),
        author_=JSONObject(
            username='author__username',
            first_name='author__first_name',
        ),
        status=Case(
            When(
                paid=True,
                then=Value('paid')
            ),
            When(
                rejected=True,
                then=Value('rejected')
            ),
            When(
                confirmed=True,
                is_material_expense=True,
                supplied=True,
                then=Value('confirmed_supplied'),
            ),
            When(
                confirmed=True,
                is_material_expense=True,
                then=Value('confirmed_waiting_supply'),
            ),
            When(
                confirmed=True,
                then=Value('confirmed'),
            ),
            default=Value('new'),
            output_field=CharField()
        )
    ).values(
        'pk',
        'author_',
        'expense_debit',
        'timestamp',
        'provider',
        'provider__name',
        'customer',
        'cost_type',
        'amount',
        'supplied_amount',
        'paid_amount',
        'sold_amount',
        'first_day',
        'last_day',
        'status',
        'comment_',
        'author',
        'confirmed',
        'is_material_expense',
        'supplied',
    ).order_by(
        '-timestamp'
    )


class ExpenseConfirmation(models.Model):
    timestamp = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Время создания'
    )
    author = models.ForeignKey(
        User,
        verbose_name='Автор',
        on_delete=models.PROTECT
    )

    expense = models.OneToOneField(
        Expense,
        verbose_name='Расход',
        on_delete=models.PROTECT
    )

    def __str__(self):
        return '{} {}, {}'.format(
            self.pk,
            self.author,
            self.expense.amount
        )


class ExpenseOperation(models.Model):
    expense = models.ForeignKey(
        Expense,
        verbose_name='Расход',
        on_delete=models.PROTECT
    )
    operation = models.OneToOneField(
        finance.models.Operation,
        on_delete=models.PROTECT,
        related_name='expense'
    )

    def __str__(self):
        return '{}, {}'.format(
            self.pk,
            self.operation
        )


@transaction.atomic
def make_confirm_operations(expense, author):
    def create_operation(first_day, last_day, amount, comment):
        operation = finance.models.Operation.objects.create(
            timepoint=last_day,
            author=author,
            comment=comment,
            debet=expense.expense_debit,
            credit=expense.provider.account_60,
            amount=amount
        )
        finance.models.IntervalPayment.objects.create(
            operation=operation,
            first_day=first_day,
            last_day=last_day
        )
        ExpenseOperation.objects.create(
            expense=expense,
            operation=operation
        )

    # Todo: see utils.split_by_months
    def _split(first_day, last_day, amount):
        months = date_time.months(expense.first_day, expense.last_day)
        if len(months) == 1:
            return [(first_day, last_day, amount)]

        total_days = (last_day - first_day).days + 1

        result = []
        current_sum = 0

        # first month
        f_year, f_month = months[0]
        _, f_last_day = date_time.first_last_day_from_month(f_year, f_month)
        f_amount = amount * ((f_last_day - first_day).days + 1) / total_days
        current_sum += f_amount
        result.append((first_day, f_last_day, f_amount))

        full_months = months[1:-1]
        for year, month in full_months:
            m_first_day, m_last_day = date_time.first_last_day_from_month(year, month)
            m_amount = amount * ((m_last_day - m_first_day).days + 1) / total_days
            current_sum += m_amount
            result.append((m_first_day, m_last_day, m_amount))

        # last_month
        l_year, l_month = months[-1]
        l_first_day, _ = date_time.first_last_day_from_month(l_year, l_month)
        l_amount = amount - current_sum
        result.append((l_first_day, last_day, l_amount))

        return result

    # Operations
    portions = _split(expense.first_day, expense.last_day, expense.amount)
    index = 1
    for first_day, last_day, amount in portions:
        create_operation(
            first_day,
            last_day,
            amount,
            'Расход №{}, часть {} из {}, с {} по {}, {}'.format(
                expense.pk,
                index,
                len(portions),
                date_time.string_from_date(first_day),
                date_time.string_from_date(last_day),
                expense.comment,
            )
        )
        index += 1


def confirm_expense(expense, author, notify=True):
    with transaction.atomic():
        ExpenseConfirmation.objects.create(
            author=author,
            expense=expense
        )

        if expense.make_operations_on_confirm():
            make_confirm_operations(expense, author)

    if notify:
        _notify_updated(expense)


def do_unconfirm_expense(expense):
    ExpenseConfirmation.objects.get(expense=expense).delete()

    operations = ExpenseOperation.objects.filter(expense=expense)
    for expense_operation in operations:
        operation = expense_operation.operation
        expense_operation.delete()
        operation.delete()


def unconfirm_expense(expense):
    with transaction.atomic():
        if ExpensePaymentOperation.objects.filter(expense=expense).exists():
            raise Exception('Нельзя отменить подтверждение расхода, который уже оплачен.')

        do_unconfirm_expense(expense)

    _notify_updated(expense)


class ExpenseRejection(models.Model):
    timestamp = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Время создания'
    )
    author = models.ForeignKey(
        User,
        verbose_name='Автор',
        on_delete=models.PROTECT
    )

    expense = models.OneToOneField(
        Expense,
        verbose_name='Расход',
        on_delete=models.PROTECT
    )

    comment = models.TextField(
        verbose_name='Комментарий'
    )

    def __str__(self):
        return '{} {}, {}'.format(
            self.pk,
            self.author,
            self.expense.amount
        )


def reject_expense(expense, author, comment):
    ExpenseRejection.objects.create(
        author=author,
        expense=expense,
        comment=comment
    )

    _notify_updated(expense, comment)


class ExpensePaymentOperation(models.Model):
    expense = models.ForeignKey(
        Expense,
        verbose_name='Расход',
        on_delete=models.PROTECT
    )
    operation = models.OneToOneField(
        finance.models.Operation,
        on_delete=models.PROTECT,
        related_name='expense_payment'
    )

    def __str__(self):
        return '{} {}, {}'.format(
            self.pk,
            self.operation.author,
            self.operation
        )


class ExpenseDeductionOperation(models.Model):
    expense = models.ForeignKey(
        Expense,
        verbose_name='Расход',
        on_delete=models.PROTECT
    )
    operation = models.OneToOneField(
        finance.models.Operation,
        on_delete=models.PROTECT,
        related_name='expense_deduction'
    )

    def __str__(self):
        return '{} {}, {}'.format(
            self.pk,
            self.operation.author,
            self.operation
        )
