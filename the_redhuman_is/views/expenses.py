# -*- coding: utf-8 -*-

import decimal

from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import render

from django.views.decorators.http import require_POST

from the_redhuman_is import models
from the_redhuman_is.models import expenses

from utils.date_time import string_from_date

from the_redhuman_is.views.utils import _get_value
from the_redhuman_is.views.utils import exception_to_json_error
from the_redhuman_is.views.utils import get_first_last_day


# Todo: remove?
@require_POST
@exception_to_json_error()
def create_provider(request):
    provider = models.create_provider(
        name=_get_value(request, 'name'),
        tax_code=_get_value(request, 'tax_code'),
    )

    return JsonResponse({'status': 'ok'})


@require_POST
@exception_to_json_error()
def update_provider(request):
    pk = _get_value(request, 'pk')
    if pk:
        with transaction.atomic():
            provider = models.Provider.objects.get(pk=pk)
            provider.name = _get_value(request, 'name')
            provider.tax_code = _get_value(request, 'tax_code')
            provider.save()
    else:
        provider = models.create_provider(
            name=_get_value(request, 'name'),
            tax_code=_get_value(request, 'tax_code'),
        )

    return JsonResponse({'status': 'ok'})


@exception_to_json_error()
def provider_detail(request):
    provider = models.Provider.objects.get(expense__pk=_get_value(request, 'pk'))

    return JsonResponse(
        {
            'status': 'ok',
            'data': provider.serialize()
        }
    )


@exception_to_json_error()
def expense_detail(request):
    expense = models.Expense.objects.get(pk=_get_value(request, 'pk'))

    if (not request.user.is_superuser) and expense.author != request.user:
        raise Exception('Нет прав для данной операции')

    return JsonResponse(
        {
            'status': 'ok',
            'data': expense.serialize()
        }
    )


# Todo: create_or_edit?
@require_POST
@exception_to_json_error()
def create_expense(request):
    first_day, last_day = get_first_last_day(request, set_initial=False)

    expense = models.update_expense(
        pk=_get_value(request, 'pk'),
        author=request.user,
        provider_pk=_get_value(request, 'provider'),
        amount=decimal.Decimal(_get_value(request, 'amount')),
        cost_type_group=_get_value(request, 'cost_type_group'),
        customer_pk=_get_value(request, 'customer'),
        cost_type_pk=_get_value(request, 'cost_type_pk'),
        first_day=first_day,
        last_day=last_day,
        comment=_get_value(request, 'comment'),
    )

    return JsonResponse({'status': 'ok'})


def _serialize_expense(expense, user):
    actions = []

    if user.is_superuser:
        actions.extend(['edit', 'fill_from'])

    if expense['status'] == 'new':
        if user.is_superuser:
            actions.extend(['confirm', 'reject'])
        if expense['author'] == user.pk:
            actions.append('delete')

    elif expense['confirmed']:
        if user.is_superuser or expense['author'] == user.pk:
            if expense['is_material_expense'] and not expense['supplied']:
                actions.append('confirm_supply')
            actions.append('unconfirm')

    return {
        'id': expense['pk'],
        'author': expense['author_'],
        'debit': expense['expense_debit'],
        'timestamp': string_from_date(expense['timestamp']),
        'provider_pk': expense['provider'],
        'name': expense['provider__name'],
        'customer': expense['customer']['name'],
        'customer_pk': expense['customer']['id'],
        'type': expense['cost_type']['name'],
        'cost_type_group': expense['cost_type']['group'],
        'cost_type_pk': expense['cost_type']['id'],
        'amount': expense['amount'],
        'supplied_amount': expense['supplied_amount'],
        'paid_amount': expense['paid_amount'],
        'sold_amount': expense['sold_amount'],
        'first_day': string_from_date(expense['first_day']),
        'last_day': string_from_date(expense['last_day']),
        'status': expense['status'],
        'comment': expense['comment_'],
        'actions': actions,
    }


@exception_to_json_error()
def actual_expenses(request):
    first_day, last_day = get_first_last_day(request)
    status = _get_value(request, 'status')
    expense_qs = expenses.actual_expenses(
        request.user, first_day, last_day
    )
    if status is not None:
        expense_qs = expense_qs.filter(status=status)

    return JsonResponse(
        {
            'status': 'ok',
            'expenses': [
                _serialize_expense(expense, request.user)
                for expense in expense_qs
            ]
        }
    )


@require_POST
@exception_to_json_error()
def update(request):
    pk = _get_value(request, 'pk')
    expense = models.Expense.objects.get(pk=pk)

    action = _get_value(request, 'action')

    if action == 'delete':
        if expense.author != request.user:
            raise Exception('Нельзя удалить чужой расход')

    if action in ['confirm', 'unconfirm', 'reject']:
        if not request.user.is_superuser:
            raise Exception('Нет прав для данной операции')

    if action == 'delete':
        models.delete_expense(expense, request.user)
    elif action == 'confirm':
        models.confirm_expense(expense, request.user)
    elif action == 'confirm_supply':
        models.make_confirm_operations(expense, request.user)
    elif action == 'unconfirm':
        models.unconfirm_expense(expense)
    elif action == 'reject':
        comment = _get_value(request, 'comment')
        models.reject_expense(expense, request.user, comment)
    else:
        raise Exception('Неизвестная операция {}'.format(action))

    return JsonResponse({'status': 'ok'})


def index(request):
    first_day, last_day = get_first_last_day(request)

    user_groups = request.user.groups.values_list(
        'name',
        flat=True
    )

    return render(
        request,
        'expenses_page.html',
        {
            'industrial_expenses_only': 'Менеджеры' in user_groups,
            'first_day': string_from_date(first_day),
            'last_day': string_from_date(last_day)
        }
    )


@exception_to_json_error()
def expense_account(request):
    pk = _get_value(request, 'pk')
    expense = models.Expense.objects.get(pk=pk)
    account = expense.provider.account_60

    return JsonResponse(
        {
            'status': 'ok',
            'data': {
                'id': account.pk,
                'full_name': account.full_name
            }
        }
    )
