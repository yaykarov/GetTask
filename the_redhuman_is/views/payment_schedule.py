# -*- coding: utf-8 -*-

import datetime

from django.http import JsonResponse

from django.shortcuts import render

from django.views.decorators.http import require_POST

from django.utils import timezone

import finance

from the_redhuman_is import models

from utils.date_time import date_from_string
from utils.date_time import days_from_interval
from utils.date_time import string_from_date

from the_redhuman_is.views.utils import _get_value
from the_redhuman_is.views.utils import exception_to_json_error
from the_redhuman_is.views.utils import get_first_last_day


def _get_first_last_day(request):
    first_day, last_day = get_first_last_day(request, set_initial=False)
    if first_day is None or last_day is None:
        now = timezone.now()

        if first_day is None:
            first_day = now - datetime.timedelta(days=now.weekday() + 7)

        if last_day is None:
            last_day = now + datetime.timedelta(days=13 - now.weekday())

    return first_day, last_day


def index(request):
    first_day, last_day = _get_first_last_day(request)

    return render(
        request,
        'payment_schedule.html',
        {
            'first_day': string_from_date(first_day),
            'last_day': string_from_date(last_day)
        }
    )


def _root_accounts(first_day, last_day):
    prefixes = ['50.', '51.', '71.']

    root_accounts = finance.models.Account.objects.none()
    for prefix in prefixes:
        root_accounts = root_accounts.union(
            finance.models.Account.objects.filter(name__istartswith=prefix, parent=None)
        )

    root_accounts = root_accounts.order_by('name')

    accounts = []

    now = timezone.now()

    for root in root_accounts:
        children = finance.models.Account.objects.filter(
            parent=root
        )
        for child in children:
            filters = [
                child.operations('debet'),
                child.operations('credit'),
                child.operations('debet', models.PlannedOperation).filter(
                    timepoint__gt=now
                ),
                child.operations('credit', models.PlannedOperation).filter(
                    timepoint__gt=now
                )
            ]
            def _has_operations():
                for f in filters:
                    f = f.filter(
                        timepoint__date__range=(
                            first_day - datetime.timedelta(days=30),
                            last_day
                        )
                    )
                    if f.exists():
                        return True
                return False

            if _has_operations():
                accounts.append(child)

    return accounts


@exception_to_json_error()
def schedule(request):
    first_day, last_day = _get_first_last_day(request)

    days = days_from_interval(first_day, last_day)

    accounts = _root_accounts(first_day, last_day)

    def _day_sum(operations, day):
        return finance.models.amount_sum(
            operations.filter(
                timepoint__date=day,
            )
        )

    def _initial_sum(operations):
        return finance.models.amount_sum(
            operations.filter(
                timepoint__date__lt=first_day
            )
        )

    grid = []

    now = timezone.now()

    for account in accounts:
        balance = []
        debit = []
        credit = []

        turnover_debit = 0
        turnover_credit = 0

        debit_operations = account.operations('debet')
        planned_debit_operations = account.operations('debet', models.PlannedOperation).filter(
            timepoint__gt=now
        )
        credit_operations = account.operations('credit')
        planned_credit_operations = account.operations('credit', models.PlannedOperation).filter(
            timepoint__gt=now
        )

        current_balance = (
            _initial_sum(debit_operations) +
            _initial_sum(planned_debit_operations) -
            _initial_sum(credit_operations) -
            _initial_sum(planned_credit_operations)
        )

        for day in days:
            balance.append(current_balance)

            planned_day_debit = _day_sum(planned_debit_operations, day)
            day_debit = (
                _day_sum(debit_operations, day) + planned_day_debit
            )
            planned_day_credit = _day_sum(planned_credit_operations, day)
            day_credit = (
                _day_sum(credit_operations, day) + planned_day_credit
            )

            turnover_debit += day_debit
            turnover_credit += day_credit

            current_balance = current_balance + day_debit - day_credit

            debit.append(
                {
                    'amount': day_debit,
                    'has_planned_operations': planned_day_debit != 0
                }
            )
            credit.append(
                {
                    'amount': day_credit,
                    'has_planned_operations': planned_day_credit != 0
                }
            )

        grid.append(
            {
                'pk': account.pk,
                'parent': account.parent.pk if account.parent else None,
                'name': account.full_name,
                'balance': balance,
                'debit': debit,
                'credit': credit,
                'turnover_debit': turnover_debit,
                'turnover_credit': turnover_credit,
            }
        )

    return JsonResponse(
        {
            'status': 'ok',
            'data': grid
        }
    )


@exception_to_json_error()
def operations(request):
    first_day, last_day = _get_first_last_day(request)
    account_pk = _get_value(request, 'account')
    operations_type = _get_value(request, 'type')

    now = timezone.now()

    account = finance.models.Account.objects.get(pk=account_pk)
    if operations_type == 'debit':
        operations = account.operations('debet').filter(
            timepoint__date__range=(
                first_day - datetime.timedelta(days=30),
                last_day
            )
        )
        accounts = finance.models.Account.objects.filter(
            credit_operations__in=operations
        )
        planned_operations = account.operations('debet', models.PlannedOperation).filter(
            timepoint__date__range=(first_day, last_day),
            timepoint__gt=now,
        )
        accounts = accounts.union(
            finance.models.Account.objects.filter(
                planned_credit_operations__in=planned_operations
            )
        )
    elif operations_type == 'credit':
        operations = account.operations('credit').filter(
            timepoint__date__range=(
                first_day - datetime.timedelta(days=30),
                last_day
            )
        )
        accounts = finance.models.Account.objects.filter(
            debet_operations__in=operations
        )
        planned_operations = account.operations('credit', models.PlannedOperation).filter(
            timepoint__date__range=(first_day, last_day),
            timepoint__gt=now,
        )
        accounts = accounts.union(
            finance.models.Account.objects.filter(
                planned_debit_operations__in=planned_operations
            )
        )
    else:
        raise Exception('Unknown type value: {}'.format(operations_type))

    accounts = accounts.order_by('full_name').distinct()
    days = days_from_interval(first_day, last_day)

    grid = []

    for corresponding_account in accounts:
        amounts = []

        turnover = 0

        for day in days:
            day_operations = operations.filter(
                timepoint__date=day
            )
            day_planned_operations = planned_operations.filter(
                timepoint__date=day
            )
            if operations_type == 'debit':
                day_operations = day_operations.filter(
                    credit=corresponding_account
                )
                day_planned_operations = day_planned_operations.filter(
                    credit=corresponding_account
                )
            else:
                day_operations = day_operations.filter(
                    debet=corresponding_account
                )
                day_planned_operations = day_planned_operations.filter(
                    debet=corresponding_account
                )

            amount = (
                finance.models.amount_sum(day_operations) +
                finance.models.amount_sum(day_planned_operations)
            )
            amounts.append(
                {
                    'amount': amount,
                    'has_planned_operations': day_planned_operations.exists()
                }
            )

            turnover += amount

        grid.append(
            {
                'pk': corresponding_account.pk,
                'name': corresponding_account.full_name,
                'operations': amounts,
                'turnover': turnover
            }
        )

    return JsonResponse(
        {
            'status': 'ok',
            'data': grid
        }
    )


@exception_to_json_error()
def day_operations(request):
    day = date_from_string(_get_value(request, 'day'))
    root_account_pk = _get_value(request, 'root_account')
    corresponding_account_pk = _get_value(request, 'corresponding_account')
    operations_type = _get_value(request, 'type')

    now = timezone.now()

    account = finance.models.Account.objects.get(pk=root_account_pk)
    if operations_type == 'debit':
        operations = account.operations('debet')
        planned_operations = account.operations('debet', models.PlannedOperation).filter(
            timepoint__gt=now
        )

        if corresponding_account_pk:
            operations = operations.filter(
                credit__pk=corresponding_account_pk
            )

            planned_operations = planned_operations.filter(
                credit__pk=corresponding_account_pk
            )

    elif operations_type == 'credit':
        operations = account.operations('credit')
        planned_operations = account.operations('credit', models.PlannedOperation).filter(
            timepoint__gt=now
        )

        if corresponding_account_pk:
            operations = operations.filter(
                debet__pk=corresponding_account_pk
            )

            planned_operations = planned_operations.filter(
                debet__pk=corresponding_account_pk
            )

    else:
        raise Exception('Unknown type value: {}'.format(operations_type))

    operations = operations.filter(
        timepoint__date=day,
    ).select_related(
        'debet',
        'credit'
    )
    planned_operations = planned_operations.filter(
        timepoint__date=day
    ).select_related(
        'debet',
        'credit'
    )

    data = {
        'operations': [],
        'planned_operations': []
    }

    def _serialize(operation):
        return {
            'pk': operation.pk,
            'debit': operation.debet.pk,
            'debit_name': operation.debet.full_name,
            'credit': operation.credit.pk,
            'credit_name': operation.credit.full_name,
            'comment': operation.comment,
            'amount': operation.amount
        }

    for operation in operations:
        data['operations'].append(_serialize(operation))

    for operation in planned_operations:
        data['planned_operations'].append(_serialize(operation))

    return JsonResponse(
        {
            'status': 'ok',
            'data': data
        }
    )


@require_POST
@exception_to_json_error()
def create_planned_operation(request):
    models.PlannedOperation.objects.create(
        timepoint=date_from_string(_get_value(request, 'date')),
        author=request.user,
        comment=_get_value(request, 'comment', ''),
        debet=finance.models.Account.objects.get(pk=_get_value(request, 'debit')),
        credit=finance.models.Account.objects.get(pk=_get_value(request, 'credit')),
        amount=_get_value(request, 'amount')
    )

    return JsonResponse({'status': 'ok'})


@require_POST
@exception_to_json_error()
def delete_planned_operation(request):
    models.PlannedOperation.objects.get(
        pk=_get_value(request, 'pk')
    ).delete()

    return JsonResponse({'status': 'ok'})
