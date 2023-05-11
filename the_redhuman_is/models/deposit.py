# -*- coding: utf-8 -*-

import decimal

from django.db import models
from django.db import transaction

import finance
from finance.model_utils import ensure_account

from .models import Customer
from .worker import Worker


def set_deposit_amount(customer_pk, amount):
    customer = Customer.objects.get(pk=customer_pk)
    deposit_filter = CustomerDepositAmount.objects.filter(customer=customer)
    if deposit_filter.exists():
        deposit = deposit_filter.first()
        deposit.amount = amount
        deposit.save()
    else:
        deposit = CustomerDepositAmount.objects.create(
            customer=customer, amount=amount)


def get_deposit_amount(worker):
    if hasattr(worker, 'deposit'):
        return -1 * worker.deposit.account.turnover_saldo()

    return decimal.Decimal(0.0)


def clear_deposit_setting(customer_pk):
    customer = Customer.objects.get(pk=customer_pk)
    deposit_filter = CustomerDepositAmount.objects.filter(customer=customer)
    if deposit_filter.exists():
        deposit_filter.first().delete()


@transaction.atomic
def ensure_worker_deposit(worker):
    deposit_filter = WorkerDeposit.objects.filter(worker=worker)
    if deposit_filter.exists():
        return deposit_filter.get()

    root = finance.model_utils.get_account("76")
    deposits = ensure_account(root, "Депозиты")
    worker_deposit_account = finance.models.Account.objects.create(
        parent=deposits,
        name=str(worker)
    )
    return WorkerDeposit.objects.create(
        worker=worker,
        account=worker_deposit_account
    )


def update_worker_deposit(customer, worker, author):
    deposit_setting = CustomerDepositAmount.objects.filter(customer=customer)
    if deposit_setting.exists():
        amount = -1 * deposit_setting.first().amount
        deposit = ensure_worker_deposit(worker)
        worker_account = worker.worker_account.account
        if deposit.account.turnover_saldo() > amount and worker_account.turnover_saldo() < 0:
            delta = deposit.account.turnover_saldo() - amount

            finance.models.Operation.objects.create(
                author=author,
                comment='Удержание залога',
                debet=worker_account,
                credit=deposit.account,
                amount=min(delta, -1 * worker_account.turnover_saldo())
            )


def return_deposit_to_worker(worker, author):
    deposit_filter = WorkerDeposit.objects.filter(worker=worker)
    if deposit_filter.exists():
        deposit = deposit_filter.first()
        saldo = deposit.account.turnover_saldo()
        if saldo < 0:
            finance.models.Operation.objects.create(
                author=author,
                comment='Возврат залога',
                debet=deposit.account,
                credit=worker.worker_account.account,
                amount=(-1 * saldo)
            )


# Настройка размера залога, который сначала отрабатывает работник при работе
# с данным клиентом
class CustomerDepositAmount(models.Model):
    customer = models.OneToOneField(
        Customer,
        on_delete=models.PROTECT,
        verbose_name='Клиент',
        related_name='deposit_setting'
    )
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name='Размер залога'
    )


class WorkerDeposit(models.Model):
    worker = models.OneToOneField(
        Worker,
        on_delete=models.CASCADE,
        verbose_name='Работник',
        related_name='deposit'
    )
    account = models.OneToOneField(
        finance.models.Account,
        on_delete=models.PROTECT,
        verbose_name='Залоговый счет'
    )
