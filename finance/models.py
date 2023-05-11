# -*- coding: utf-8 -*-

import datetime
import decimal
import pytz

from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q, Count
from django.db.models.signals import (
    pre_delete,
#    post_save,
)
from django.utils import timezone

from utils.date_time import string_from_date


# Todo: payment interval?
def update_if_changed(
            operation,
            amount,
            debit=None,
            credit=None,
            comment=None,
            timepoint=None
        ):

    changed = False
    if operation.amount != amount:
        changed = True
        operation.amount = amount
    if debit and operation.debet != debit:
        changed = True
        operation.debet = debit
    if credit and operation.credit != credit:
        changed = True
        operation.credit = credit
    if comment and operation.comment != comment:
        changed = True
        operation.comment = comment
    if timepoint:
        timepoint = datetime.datetime(
            year=timepoint.year,
            month=timepoint.month,
            day=timepoint.day
        ).astimezone(
            pytz.timezone('Europe/Moscow')
        )
        if operation.timepoint != timepoint:
            changed = True
            operation.timepoint = timepoint

    if changed:
        operation.save()

    return changed


def amount_sum(operations):
    return operations.aggregate(
        models.Sum('amount')
    )['amount__sum'] or decimal.Decimal(0.0)


class Account(models.Model):
    name = models.CharField(
        max_length=100
    )
    full_name = models.CharField(
        max_length=1000,
        null=True,
        blank=True
    )
    parent = models.ForeignKey(
        'self',
        on_delete=models.PROTECT,
        related_name='children',
        null=True,
        blank=True,
    )
    created = models.DateTimeField(
        default=timezone.now
    )
    closed = models.BooleanField(
        default=False
    )

    class Meta:
        ordering = ('full_name',)

    def save(self, *args, **kwargs):
        if self.parent:
            self.full_name = "{} > {}".format(self.parent, self.name)
        else:
            self.full_name = self.name
        super(Account, self).save(*args, **kwargs)
        # update child
        if self.pk:
            children = Account.objects.filter(parent=self.id)
            for item in children:
                item.save()

    def __str__(self):
        if self.full_name is not None:
            return f'{self.full_name}'
        else:
            return f'{self.name}'

    def turnover_debet(self):
        return self._turnover('debet')

    def turnover_credit(self):
        return self._turnover('credit')

    def turnover_saldo(self):
        return self._turnover('saldo')

    def interval_saldo(self, first_day, last_day, exclude=None):
        debit_operations = self.operations('debet')
        credit_operations = self.operations('credit')
        if exclude:
            debit_operations = debit_operations.exclude(**exclude)
            credit_operations = credit_operations.exclude(**exclude)

        # Операции, которые не имеют интервала оплаты
        simple_debit_operations = debit_operations.filter(
            intervalpayment__isnull=True,
            timepoint__date__range=(first_day, last_day),
        )
        simple_credit_operations = credit_operations.filter(
            intervalpayment__isnull=True,
            timepoint__date__range=(first_day, last_day),
        )

        debit = amount_sum(simple_debit_operations)
        credit = amount_sum(simple_credit_operations)

        # Операции, у которых есть интервал "оплаты"
        def _filter_interval_operations(operations):
            return operations.filter(
                Q(
                    (
                        Q(intervalpayment__first_day__gte=first_day) &
                        Q(intervalpayment__first_day__lte=last_day)
                    ) |
                    (
                        Q(intervalpayment__last_day__gte=first_day) &
                        Q(intervalpayment__last_day__lte=last_day)
                    )
                ),
                intervalpayment__isnull=False
            )
        interval_debit_operations = _filter_interval_operations(debit_operations)
        interval_credit_operations = _filter_interval_operations(credit_operations)

        def _interval_sum(operations):
            s = 0
            for operation in operations:
                interval = operation.intervalpayment
                total_days = (interval.last_day - interval.first_day).days + 1
                intersection_first_day = max(first_day, interval.first_day)
                intersection_last_day = min(last_day, interval.last_day)
                intersection_days = (intersection_last_day - intersection_first_day).days + 1
                amount = operation.amount * intersection_days / total_days
                s += amount
            return s

        debit += _interval_sum(interval_debit_operations)
        credit += _interval_sum(interval_credit_operations)

        saldo = round(debit - credit, 2)
        return saldo

    def _ctt_cache_key(self):
        return 'fin:acc:{0}:ctt'.format(self.pk)

    def _cache_to_tag_get(self):
        val = cache.get(self._ctt_cache_key())
        if val is None:
            val = self._cache_to_tag_inc()
        return val

    def _cache_to_tag_inc(self):
        key = self._ctt_cache_key()
        try:
            return cache.incr(key, 1)
        except ValueError:
            cache.set(key, 1, None)
            return 1

    def _turnover_cache_key(self, opertype):
        return 'fin:acc:{0}:{1}{2}'.format(self.pk, opertype, self._cache_to_tag_get())

    def _turnover(self, opertype):
        key = self._turnover_cache_key(opertype)
        cached = cache.get(key)
        if cached is not None:
            return cached
        if opertype == 'saldo':
            value = self._turnover('debet') - self._turnover('credit')
        else:
            value = amount_sum(self.operations(opertype))
        cache.set(key, value, 60 * 60 * 6)  # 6h
        return value

    def operations(self, opertype, model=None):
        assert opertype in ('debet', 'credit'), "operation type should be 'debet' or 'credit'"

        if model is None:
            model = Operation

        accounts = set()

        def add_children(acc):
            accounts.add(acc)
            for child in acc.children.filter(closed=False).iterator():
                add_children(child)

        add_children(self)  # fetch all children

        if opertype == 'debet':
            filters = Q(debet__in=accounts)
        else:  # opertype == 'credit':
            filters = Q(credit__in=accounts)

        return model.objects.filter(filters).order_by('pk')

    def drop_turnover_cache(self):
        reset_list = [self] + self.ancestors()
        for acc in reset_list:
            acc._cache_to_tag_inc()

    def ancestors(self):
        ancestors = []
        parent = self.parent
        while parent:
            ancestors.append(parent)
            parent = parent.parent
        return ancestors

    def descendants(self, include_self=False):
        descendants = []
        curr_level = 0

        def _children(acc):
            nonlocal curr_level
            acc.level = curr_level
            descendants.append(acc)
            for child in acc.children.annotate(num_children=Count('children')).filter(closed=False):
                if child.num_children > 0:
                    curr_level += 1
                    _children(child)
                    curr_level -= 1
                else:
                    child.level = curr_level + 1
                    descendants.append(child)  # add leaf. no need to go deeper

        _children(self)
        if not include_self:
            del descendants[0]
        return descendants

    def fullname(self):
        fullpath = self.ancestors()
        fullpath.reverse()
        fullpath.append(self)
        return "-".join([ancestor.name for ancestor in fullpath])


class Operation(models.Model):
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
        verbose_name='Комментарий',
        blank=True,
        null=True,
    )

    debet = models.ForeignKey(
        Account,
        on_delete=models.PROTECT,
        verbose_name="Дебет",
        related_name="debet_operations"
    )
    credit = models.ForeignKey(
        Account,
        on_delete=models.PROTECT,
        verbose_name="Кредит",
        related_name="credit_operations"
    )
    amount = models.DecimalField(
        max_digits=30,
        decimal_places=2,
        verbose_name="Сумма",
        validators=[MinValueValidator(decimal.Decimal('0'))]
    )

    is_closed = models.BooleanField(
        default=False,
        verbose_name="Операцию запрещено редактировать"
    )

    def save(self, *args, **kwargs):
        if self.amount < 0:
            self.amount = -self.amount
            tmp = self.debet
            self.debet = self.credit
            self.credit = tmp

        if self.debet.children.exists() or self.credit.children.exists():
            raise Exception("Can't save operation with parent account.")

        # Новая операция
        if self.pk is None:
            if self.is_operation_closed():
                raise Exception("Период закрыт. Запрещено создавать операции.")
        else:
            if self.is_closed:
                raise Exception("Операцию {} запрещено редактировать.".format(self.pk))

        super(Operation, self).save(*args, **kwargs)

        self.debet.drop_turnover_cache()
        self.credit.drop_turnover_cache()

    def __str__(self):
        return "{} {} [{}] (Д:{}, К:{})".format(
            self.id,
            self.timepoint.strftime("%Y.%m.%d %H:%M"),
            self.amount,
            self.debet,
            self.credit)

    def is_operation_closed(self):
        from the_redhuman_is.services.finance.period_closure import is_period_closed
        if not is_period_closed(self.timepoint):
            return False
        debet_fullname = str(self.debet)
        credit_fullname = str(self.credit)
        closable_roots = ['20', '26', '90', '99']
        for root in closable_roots:
            if debet_fullname.startswith(root) or credit_fullname.startswith(root):
                return True
        return False

# Todo: look at the commit d12ec02a9597c13c18ff27461aea63cabc793afe and cleanup
#    @classmethod
#    def post_save(cls, sender, instance, created, *args, **kwargs):
#        instance.debet.drop_turnover_cache()
#        instance.credit.drop_turnover_cache()
#
#        # Операции комиссии
#        banks_service_params = the_redhuman_is.models.BankServiceParams.objects.all()
#
#        debit_accounts = {}
#        credit_accounts = {}
#
#        for param in banks_service_params:
#            all_debit_accounts = [param.service.debit]
#
#            # Получаем субсчета
#            all_debit_accounts = cls.__get_debit_sub_accounts(instance, param.service.debit, all_debit_accounts)
#
#            debit_accounts[param.pk] = all_debit_accounts
#            credit_accounts[param.pk] = param.bank.account_51
#
#        for key in debit_accounts:
#            for i in range(len(debit_accounts[key])):
#
#                if instance.debet == debit_accounts[key][i] and instance.credit == credit_accounts[key]:
#
#                    banks_service_param = the_redhuman_is.models.BankServiceParams.objects.get(pk=key)
#                    commission_operations = the_redhuman_is.models.CommissionOperation.objects.filter(
#                        operation=instance)
#
#                    if commission_operations:
#                        commission_operation = commission_operations[0]
#                        commission = commission_operation.commission
#                        commission.amount = banks_service_param.calculator.get_amount(instance)
#                        commission.save()
#                    else:
#                        commission = Operation()
#                        commission.debet = banks_service_param.account
#                        commission.credit = banks_service_param.bank.account_51
#                        commission.amount = banks_service_param.calculator.get_amount(instance)
#                        commission.author = instance.author
#                        commission.comment = "Комиссия за " + banks_service_param.service.type + " в размере " + str(
#                            banks_service_param.calculator.val)
#                        commission.save()
#                        the_redhuman_is.models.CommissionOperation.objects.create(operation=instance,
#                                                                                  commission=commission)
#
#                    break


    @classmethod
    def pre_delete(cls, sender, instance, *args, **kwargs):
        instance.debet.drop_turnover_cache()
        instance.credit.drop_turnover_cache()

# Todo: look at the commit d12ec02a9597c13c18ff27461aea63cabc793afe and cleanup
#    # Получение субсчетов рекурсией
#    def __get_debit_sub_accounts(self, account, accounts):
#
#        if account.children.exists():
#            for ac in account.children.all():
#                accounts.append(ac)
#                self.__get_debit_sub_accounts(ac, accounts)
#
#        return accounts


class IntervalPayment(models.Model):
    operation = models.OneToOneField(
        Operation,
        on_delete=models.CASCADE,
        verbose_name='Операция',
    )

    first_day = models.DateField(
        verbose_name='Первый день периода',
    )
    last_day = models.DateField(
        verbose_name='Последний день периода',
    )

    def __str__(self):
        return 'С {} по {}, {}р., операция №{}'.format(
            string_from_date(self.first_day),
            string_from_date(self.last_day),
            self.operation.amount,
            self.operation.pk
        )


# Todo: look at the commit d12ec02a9597c13c18ff27461aea63cabc793afe and cleanup
#post_save.connect(Operation.post_save, sender=Operation)
pre_delete.connect(Operation.pre_delete, sender=Operation)
