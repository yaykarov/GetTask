# -*- coding: utf-8 -*-

import datetime
import re

from django.urls import reverse

from django.db.models import Case
from django.db.models import OuterRef
from django.db.models import Q
from django.db.models import SmallIntegerField
from django.db.models import Subquery
from django.db.models import Sum
from django.db.models import Value
from django.db.models import When

from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from django.contrib.auth.decorators import user_passes_test
from django.core.cache import cache
from django.utils.timezone import localdate

import finance

from import1c.models import unimported_operations_count

from ..auth import staff_account_required

from the_redhuman_is.models import WorkerTurnout, TurnoutOperationToPay, TurnoutOperationIsPayed, CustomerService

from the_redhuman_is import forms

from the_redhuman_is import models

from the_redhuman_is.models import fine_utils

from utils.date_time import as_default_timezone
from utils.date_time import string_from_date

from the_redhuman_is.views.utils import get_first_last_day


ACCOUNT_OPERATIONS_PER_PAGE = getattr('settings', 'ACCOUNT_OPERATIONS_PER_PAGE', 100)


def _get_page_from_request(request):
    try:
        return int(request.GET.get('page', 1))
    except ValueError:
        return 1


@staff_account_required
def tree(request):
    today = localdate()
    yesterday = today - datetime.timedelta(days=1)
    operations = finance.models.Operation.objects.filter(
        timepoint__date__gte=yesterday
    ).order_by('-timepoint')

    expense_form = forms.ExpenseSelectionForm()
    expense_form.fields['expense'].required = False

    reconciliation_form = forms.UnpaidReconciliationSelectionForm()
    reconciliation_form.fields['reconciliation'].required = False

    return render(
        request,
        'the_redhuman_is/operating_account_tree.html',
        {
            'expense_form': expense_form,
            'reconciliation_form': reconciliation_form,
            'now': timezone.now(),
            'operations': operations,
            'unimported_operations_count': unimported_operations_count(),
            'form': forms.WorkerSearchForm()
        }
    )


@user_passes_test(lambda user: user.is_superuser)
def cache_clear(request):
    cache.clear()
    return redirect('the_redhuman_is:operating_account_tree')


def _describe_account(account):
    return {
        'name': account.name,
        'fullname': account.full_name,
        'saldo': float(account.turnover_saldo()),
        'account_pk': account.id,
        'has_child': account.children.count() != 0
    }


@staff_account_required
def tree_json(request, pk):
    pk = int(pk)
    if pk == -1:
        accounts = finance.models.Account.objects.filter(
            parent=None,
            closed=False
        ).order_by('name')

    else:
        accounts = finance.models.Account.objects.filter(
            parent__pk=pk,
            closed=False
        ).order_by('name')

    children = [_describe_account(account) for account in accounts]

    return JsonResponse(
        {
            'name': 'Корневые счета',
            'fullname': 'Корневые счета',
            'saldo': '',
            'children': children
        }
    )


def _account_operations(account, first_day, last_day, search_text=None):
    debit_operations = account.operations('debet')
    credit_operations = account.operations('credit')

    def _filter_by_text(operations, search_text):
        return operations.filter(
            Q(comment__icontains=search_text) |
            Q(debet__full_name__icontains=search_text) |
            Q(credit__full_name__icontains=search_text)
        )

    if search_text:
        debit_operations = _filter_by_text(debit_operations, search_text)
        credit_operations = _filter_by_text(credit_operations, search_text)

    if first_day:
        debit_operations = debit_operations.filter(timepoint__date__gte=first_day)
        credit_operations = credit_operations.filter(timepoint__date__gte=first_day)

    if last_day:
        debit_operations = debit_operations.filter(
            timepoint__date__lte=last_day
        )
        credit_operations = credit_operations.filter(
            timepoint__date__lte=last_day
        )

    return debit_operations, credit_operations


@staff_account_required
def detail(request, pk):
    first_day, last_day = get_first_last_day(request, set_initial=False)

    account = get_object_or_404(finance.models.Account, pk=pk)

    debit_operations, credit_operations = _account_operations(account, first_day, last_day)

    debit = finance.models.amount_sum(debit_operations)
    credit = finance.models.amount_sum(credit_operations)
    saldo = debit - credit

    return render(
        request,
        'the_redhuman_is/account.html',
        {
            'interval_form': forms.DaysIntervalForm(
                initial={
                    'first_day': first_day,
                    'last_day': last_day
                }
            ),
            'payment_interval_form': forms.DaysIntervalForm(field_prefix='operation_'),
            'account': account,
            'debit': debit,
            'credit': credit,
            'saldo': saldo,
        }
    )


def _describe_operation(request, operation):
    _URL_TMPL = '<a href="{}" target="_blank">{}</a>'

    amount = '{:,}'.format(operation.amount).replace(',', '&nbsp;')
    if request.user.is_superuser:
        amount = _URL_TMPL.format(
            request.build_absolute_uri(
                reverse(
                    'admin:finance_operation_change',
                    args=[operation.pk]
                )
            ),
            amount
        )

    amount_html = (
        '<button class="btn btn-outline-primary" onClick="do_copy(\'{}\')";>' +
        '<i class=\"fa fa-copy\"></i></button><span>{}</span>'
    ).format(
        str(operation.amount).replace('.', ','),
        amount
    )

    def _account_url(account):
        return _URL_TMPL.format(
            request.build_absolute_uri(
                reverse(
                    'the_redhuman_is:operating_account_detail',
                    args=[account.pk]
                )
            ),
            str(account)
        )

    def _account_html(account):
        return '<button class=\"btn btn-outline-primary\" onClick=\"do_copy(\'{}\');\"><i class=\"fa fa-copy\"></i></button>{}'.format(
            str(account),
            _account_url(account),
        )

    direction = None
    if hasattr(operation, 'direction'):
        direction = operation.direction

    return [
        operation.pk,
        '{:%d.%m.%Y %H:%M}'.format(as_default_timezone(operation.timepoint)),
        _account_html(operation.debet),
        _account_html(operation.credit),
        operation.comment,
        amount_html,
        str(operation.author),
        direction,
        string_from_date(operation.first_day),
        string_from_date(operation.last_day)
    ]


def _order(order_index, order_dir):
    _COLUMNS = {
        2: 'debet',
        3: 'credit',
        4: 'comment',
        5: 'amount',
        6: 'direction'
    }

    column = _COLUMNS.get(order_index, 'timepoint')

    if order_dir == 'asc':
        return '-' + column
    else:
        return column


def detail_json(request, pk):
    draw = request.GET['draw']
    start = int(request.GET.get('start'))
    length = int(request.GET.get('length'))
    order_index = int(request.GET.get('order_index'))
    order_dir = request.GET.get('order_dir')
    search_text = request.GET.get('search_text')

    order = _order(order_index, order_dir)

    account = get_object_or_404(
        finance.models.Account.objects.select_related('parent'),
        pk=pk
    )

    first_day, last_day = get_first_last_day(request, set_initial=False)
    debit_operations, credit_operations = _account_operations(
        account,
        first_day,
        last_day,
        search_text
    )

    all_ops_related_fields = ['debet', 'credit']
    # join parent accounts all the way down
    # looks crazy but drastically reduce number of queries
    for x in range(5):
        all_ops_related_fields.append('debet' + '__parent' * (x + 1))
        all_ops_related_fields.append('credit' + '__parent' * (x + 1))

    all_ops = (debit_operations | credit_operations).select_related(
        *all_ops_related_fields
    ).annotate(
        direction=Case(
            When(pk__in=debit_operations, then=Value(1)),  # debet
            default=Value(-1),  # credit
            output_field=SmallIntegerField()
        ),
        first_day=Subquery(
            finance.models.IntervalPayment.objects.filter(
                operation=OuterRef('pk')
            ).values('first_day')
        ),
        last_day=Subquery(
            finance.models.IntervalPayment.objects.filter(
                operation=OuterRef('pk')
            ).values('last_day')
        ),
    ).order_by(order)

    totalRecords = all_ops.count()
    if totalRecords == 0:
        return JsonResponse({'draw': draw, 'recordsTotal': 0, 'recordsFiltered': 0, 'data': []})
    end = totalRecords
    if length > 0:
        end = min(totalRecords, start+length)
    all_ops = all_ops[start:end]
    data = []
    for op in all_ops:
        data.append(_describe_operation(request, op))

    return JsonResponse(
        {
            'draw': draw,
            'recordsTotal': totalRecords,
            'recordsFiltered': totalRecords,
            'data': data
        }
    )


_DATE_RX = re.compile("^(\d{1,2})\.(\d{2})\.(\d{4})$")
_TIME_RX = re.compile("^(\d{1,2})\:(\d{2})$")

def total_detail(request):
    beginStr = request.GET.get("begin")
    endStr = request.GET.get("end")
    begin = datetime.datetime.strptime(beginStr,"%Y-%d-%m")
    end = datetime.datetime.strptime(endStr,"%Y-%d-%m")
    display = request.GET.get("display")
    if begin == end:
        query = Q(timesheet__sheet_date=begin)
        range_query = Q(timepoint__date=begin)
    else:
        query = Q(timesheet__sheet_date__range=(begin, end))
        range_query = Q(timepoint__date__range=(begin, end))

    customer_id = request.GET.get("customer")
    if customer_id:
        query &= Q(timesheet__customer__pk=customer_id)

    location_id = request.GET.get("location")
    if location_id:
        query &= Q(timesheet__cust_location__pk=location_id)

    service_id = request.GET.get("service")
    if service_id:
        customer_service = CustomerService.objects.get(pk=service_id)
        query &= Q(turnoutservice__customer_service=customer_service)

    sheet_turn = request.GET.get("sheet_turn")
    if sheet_turn:
        query &= Q(timesheet__sheet_turn=sheet_turn)

    customers = models.Customer.objects.all()
    user_groups = request.user.groups.values_list('name', flat=True)
    if 'Менеджеры' in user_groups:
        customers = customers.filter(
            maintenancemanager__worker__workeruser__user=request.user
        )

    mmanager = request.GET.get("mmanager")
    if mmanager:
        customers = customers.filter(
            maintenancemanager__worker__pk=mmanager
        )

    dmanager = request.GET.get("dmanager")
    if dmanager:
        customers = customers.filter(
            developmentmanager__worker__pk=mmanager
        )

    query &= Q(timesheet__customer__in=customers)

    root_70 = finance.model_utils.get_root_account('70.')
    turnouts = WorkerTurnout.objects.filter(query)
    if display == "debet":
        caption = "Выплаты за интервал "+str(begin.date())+" по "+str(begin.date())
        operations = finance.models.Operation.objects.filter(range_query, debet__parent=root_70)
        total_amount = operations.aggregate(amounts=Sum("amount")).get("amounts", 0.0) or 0.0
    elif display == "credit":
        caption = "Начисления за интервал "+str(begin.date())+" по "+str(begin.date())
        turn_operations = TurnoutOperationToPay.objects.filter(turnout__in=turnouts, operation__credit__parent=root_70).values_list("operation")
        operations = finance.models.Operation.objects.filter(pk__in=turn_operations)
        total_amount = operations.aggregate(amounts=Sum("amount")).get("amounts", 0.0) or 0.0
    elif display == "to_pay":
        caption = "Неоплаченные выходы за интервал "+str(begin.date())+" по "+str(begin.date())
        turn_operations = TurnoutOperationToPay.objects.filter(turnout__in=turnouts, turnout__is_payed=False, operation__credit__parent=root_70).values_list("operation")
        operations = finance.models.Operation.objects.filter(pk__in=turn_operations)
        total_amount = operations.aggregate(amounts=Sum("amount")).get("amounts", 0.0) or 0.0
    elif display == "payed":
        caption = "Оплаченные выходы за интервал "+str(begin.date())+" по "+str(begin.date())
        turnouts = TurnoutOperationIsPayed.objects.filter(turnout__in=turnouts, turnout__is_payed=True, operation__debet__parent=root_70).values_list("turnout")
        operations = TurnoutOperationToPay.objects.filter(turnout__in=turnouts, operation__credit__parent=root_70).values_list("operation")
        operations = finance.models.Operation.objects.filter(pk__in=operations)
        total_amount = operations.aggregate(amounts=Sum("amount")).get("amounts", 0.0) or 0.0
    elif display == 'deduct':
        caption = 'Вычеты за интервал с {} по {}.'.format(
            string_from_date(begin.date()),
            string_from_date(end.date())
        )
        if customer_id:
            deduct_accounts = list(fine_utils.deduction_accounts(customer_pk=customer_id))
        else:
            deduct_accounts = list(fine_utils.deduction_accounts(customers=customers))
        operations = finance.models.Operation.objects.filter(
            range_query & Q(credit__in=deduct_accounts),
            debet__worker_account__isnull=False
        )
        total_amount = operations.aggregate(amounts=Sum("amount")).get("amounts") or 0.0
    else:
        raise Exception('Unknown display type {}'.format(display))
    operations = operations.select_related("debet", "credit")
    day_count = (end - begin).days+1 if not begin == end else 1

    return render(
        request,
        'the_redhuman_is/total_finance_detail.html',
        {
            "operations": operations,
            "total_amount": total_amount,
            "average_amount": total_amount / day_count,
            "caption": caption
        }
    )


def _add_operation_error(error_text):
    return JsonResponse({"status": "error", "error_text": error_text})

# Todo: check if all values exists
@staff_account_required
def add_operation(request):
    print(request.POST)
    m = _DATE_RX.match(request.POST["date"])
    # Todo: interval check
    if m:
        day = int(m.group(1))
        month = int(m.group(2))
        year = int(m.group(3))
    else:
        return _add_operation_error("Неправильная дата {}".format(request.POST["date"]))

    m = _TIME_RX.match(request.POST["time"])
    # Todo: interval check
    if m:
        hour = int(m.group(1))
        minute = int(m.group(2))
    else:
        return _add_operation_error("Неправильное время {}".format(request.POST["time"]))

    debet_pk = int(request.POST["debet"])
    credit_pk = int(request.POST["credit"])
    if debet_pk == credit_pk:
        return _add_operation_error("Кредит должен отличаться от Дебета.")

    amount = float(re.sub(",", ".", request.POST["amount"]))
    comment = request.POST.get("comment")

    timepoint = datetime.datetime(
        year=year,
        month=month,
        day=day,
        hour=hour,
        minute=minute
    )
    try:
        expense_pk = request.POST.get('expense')
        reconciliation_pk = request.POST.get('reconciliation')

        if reconciliation_pk:
            comment = 'Оплата по сверке №{}. {}'.format(reconciliation_pk, comment)

        operation = finance.models.Operation.objects.create(
            timepoint=timepoint,
            author=request.user,
            comment=comment,
            debet=finance.models.Account.objects.get(pk=debet_pk),
            credit=finance.models.Account.objects.get(pk=credit_pk),
            amount=amount
        )

        if expense_pk:
            expense = models.Expense.objects.get(pk=expense_pk)
            models.ExpensePaymentOperation.objects.create(
                expense=expense,
                operation=operation
            )
        elif reconciliation_pk:
            reconciliation = models.Reconciliation.objects.get(pk=reconciliation_pk)
            models.ReconciliationPaymentOperation.objects.create(
                reconciliation=reconciliation,
                operation=operation
            )

        return JsonResponse(
            {
                'status': 'ok',
                'operation': {
                    'debet': {
                        'pk':operation.debet.pk,
                        'name': operation.debet.full_name
                    },
                    'credit': {
                        'pk':operation.credit.pk,
                        'name': operation.credit.full_name
                    },
                    'amount': operation.amount,
                    'timepoint': datetime.datetime.strftime(
                        operation.timepoint,'%d.%m.%Y %H:%M'
                    ),
                    'comment': operation.comment,
                    'closed': False
                }
            }
        )
    except Exception as exc:
        return _add_operation_error('Ошибка создания операции: {}'.format(exc.args[0]))


@staff_account_required
def salary_proxy(request):
    form = forms.WorkerSearchForm(data=request.POST)
    if form.is_valid():
        worker = form.cleaned_data["worker"]
        return redirect('the_redhuman_is:to_pay_salary', pk=worker.pk)
    raise Exception('Invalid WorkerSearchForm')

