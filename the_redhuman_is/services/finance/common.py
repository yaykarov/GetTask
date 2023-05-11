from django.db.models import Sum

from finance.models import (
    Account,
    Operation,
)

from utils.numbers import ZERO_OO


def lock_root_account_99():
    return Account.objects.select_for_update(nowait=True).get(
        name__startswith='99.',
        parent=None
    )


def get_account_debit_operations(account, first_day, last_day):
    return account.operations('debet').filter(
        timepoint__date__range=(first_day, last_day)
    )


def get_account_credit_operations(account, first_day, last_day):
    return account.operations('credit').filter(
        timepoint__date__range=(first_day, last_day)
    )


def get_account_debit_turnover(account, first_day, last_day):
    return get_account_debit_operations(account, first_day, last_day).aggregate(
        amounts=Sum('amount')
    ).get('amounts', ZERO_OO) or ZERO_OO


def get_account_credit_turnover(account, first_day, last_day):
    return get_account_credit_operations(account, first_day, last_day).aggregate(
        amounts=Sum('amount')
    ).get('amounts', ZERO_OO) or ZERO_OO


def get_account_saldo(account, first_day, last_day):
    return (
        get_account_debit_turnover(account, first_day, last_day) -
        get_account_credit_turnover(account, first_day, last_day)
    )


def close_operations(last_day):
    operations = Operation.objects.filter(
        is_closed=False,
        timepoint__date__lte=last_day
    )
    operations.update(is_closed=True)
