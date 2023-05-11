# -*- coding: utf-8 -*-

from django.http import JsonResponse
from django.shortcuts import render

from django.urls import reverse

from django.db.models import (
    OuterRef,
    Q,
    Subquery,
    Sum,
)

import finance

from finance.model_utils import get_root_account

from the_redhuman_is import forms
from the_redhuman_is import models

from the_redhuman_is.views.utils import get_first_last_day

from the_redhuman_is.views.operating_account import _describe_operation
from the_redhuman_is.views.operating_account import _order

from utils.date_time import string_from_date


def _interval_saldo(accounts, first_day, last_day):
    if isinstance(accounts, list):
        return sum([_interval_saldo(a, first_day, last_day) for a in accounts])

    return accounts.interval_saldo(
        first_day,
        last_day,
        exclude={'sheet_close_operation__isnull': False}
    )


def _print_strange_operations(operations, first_day, last_day):
    # For speedup in case if there is no problems
    # Comment this if ivestigation needed
    return
    strange_operations = operations.exclude(
        timepoint__date__range=(first_day, last_day)
    )
    if strange_operations.exists():
        for o in strange_operations:
            print(o)


def _customer_operations(first_day, last_day):
    operations = finance.models.Operation.objects.filter(
        turnoutcustomeroperation__turnout__timesheet__sheet_date__range=(
            first_day,
            last_day
        )
    )

    _print_strange_operations(operations, first_day, last_day)

    return operations


def _turnout_deductions(first_day, last_day):
    operations = finance.models.Operation.objects.filter(
        turnoutdeduction__turnout__timesheet__sheet_date__range=(
            first_day,
            last_day
        )
    )

    _print_strange_operations(operations, first_day, last_day)

    return operations


def _worker_deductions(first_day, last_day):
    operations = finance.models.Operation.objects.filter(
        timepoint__date__range=(first_day, last_day),
        workerdeduction__isnull=False,
        credit__account_10_subaccounts__isnull=True
    )

    _print_strange_operations(operations, first_day, last_day)

    return operations


def _turnout_adjusting_operations(first_day, last_day):
    operations = finance.models.Operation.objects.filter(
        turnoutadjustingoperation__turnout__timesheet__sheet_date__range=(
            first_day,
            last_day
        ),
        debet__worker_account__isnull=False
    )

    _print_strange_operations(operations, first_day, last_day)

    return operations


def _fines(first_day, last_day):
    operations = finance.models.Operation.objects.filter(
        customerfine__turnout__timesheet__sheet_date__range=(
            first_day,
            last_day
        )
    )

    _print_strange_operations(operations, first_day, last_day)

    return operations


def _raw_20_bonuses(first_day, last_day):
    root_70 = get_root_account('70')
    root_20 = get_root_account('20')
    accounts_20 = root_20.descendants()

    return finance.models.Operation.objects.filter(
        turnoutoperationtopay__isnull=True,
        hostelbonusoperation__isnull=True,
        debet__in=accounts_20,
        credit__parent=root_70,
        timepoint__date__range=(first_day, last_day),
    )


def _revenue(first_day, last_day):
    return (
        _customer_operations(first_day, last_day) |
        _turnout_deductions(first_day, last_day) |
        _worker_deductions(first_day, last_day) |
        _turnout_adjusting_operations(first_day, last_day)
    )


def _unknown_revenue(first_day, last_day):
    root_76 = get_root_account('76')
    accounts_76 = root_76.descendants()

    return finance.models.Operation.objects.filter(
        Q(debet__in=accounts_76) | Q(credit__in=accounts_76),
        timepoint__date__range=(first_day, last_day)
    ).exclude(
        turnoutcustomeroperation__isnull=False,
    ).exclude(
        turnoutdeduction__isnull=False,
    ).exclude(
        workerdeduction__isnull=False,
    ).exclude(
        turnoutadjustingoperation__isnull=False,
    )

def split_customer(customer, first_day, last_day):
    legal_entities = models.intersected_legal_entities(
        customer, first_day, last_day
    )
    if not legal_entities.exists():
        raise Exception(
            'На интервале с {} по {} для <{}> не найдено юрлиц'.format(
                string_from_date(first_day),
                string_from_date(last_day),
                customer
            )
        )

    for entity in legal_entities:
        entity_last_day = entity.last_day
        if not entity_last_day or entity_last_day > last_day:
            entity_last_day = last_day
        yield customer, entity, max(first_day, entity.first_day), entity_last_day


def collect_customer_info(customer, first_day, last_day):
    hours_worked = models.WorkerTurnout.objects.filter(
        timesheet__customer=customer,
        timesheet__sheet_date__range=(
            first_day,
            last_day
        )
    ).aggregate(
        s=Sum('hours_worked')
    )['s'] or 0

    customer_amount = finance.models.amount_sum(
        finance.models.Operation.objects.filter(
            turnoutcustomeroperation__turnout__timesheet__customer=customer,
            turnoutcustomeroperation__turnout__timesheet__sheet_date__range=(
                first_day,
                last_day
            )
        )
    )

    deductions = finance.models.amount_sum(
        finance.models.Operation.objects.filter(
            turnoutdeduction__turnout__timesheet__customer=customer,
            turnoutdeduction__turnout__timesheet__sheet_date__range=(
                first_day,
                last_day
            )
        )
    )

    fines = finance.models.amount_sum(
        finance.models.Operation.objects.filter(
            customerfine__turnout__timesheet__customer=customer,
            customerfine__turnout__timesheet__sheet_date__range=(
                first_day,
                last_day
            )
        )
    )

    return hours_worked, customer_amount, deductions, fines


def efficiency_report(request):
    first_day, last_day = get_first_last_day(request)

    customers = models.Customer.objects.filter(
        timesheets__sheet_date__range=(first_day, last_day)
    ).distinct(
    ).order_by(
        'cust_name'
    )

    split_customers = []
    for customer in customers:
        for c, e, f, l in split_customer(customer, first_day, last_day):
            split_customers.append((c, e, f, l))

    # Группируем некоторые субсчета счетов 20/клиент/*
    account_20_industrial = {}
    for customer, entity, interval_first_day, interval_last_day in split_customers:
        customer_interval = (customer, interval_first_day, interval_last_day)
        account_20_industrial[customer_interval] = {}
        industrial = models.CustomerIndustrialAccounts.objects.filter(
            customer=customer
        )
        for accounts in industrial:
            account = accounts.account_20
            saldo = _interval_saldo(account, interval_first_day, interval_last_day)
            if saldo != 0 or hasattr(account, 'account_20_foremans'):
                account_20_industrial[customer_interval][accounts.cost_type.name] = (
                    account.pk,
                    saldo
                )

    account_20_industrial_titles = []

    for c, accounts in account_20_industrial.items():
        for name in accounts.keys():
            if name not in account_20_industrial_titles:
                account_20_industrial_titles.append(name)

    account_20_industrial_titles.sort()

    def _efficiency(profit, revenue):
        if revenue > 0:
            return 100 * profit / revenue
        else:
            return 0

    vat_total = 0

    class Result(object):
        pass

    results = []

    for customer, legal_entity, interval_first_day, interval_last_day in split_customers:
        result = Result()
        results.append(result)

        result.first_day = interval_first_day
        result.last_day = interval_last_day

        result.customer = customer

        hours_worked, customer_amount, deductions, fines = collect_customer_info(
            customer,
            interval_first_day,
            interval_last_day
        )

        result.hours_worked = hours_worked
        result.customer_amount = customer_amount
        result.deductions = deductions
        result.fines = fines

        result.legal_entity = legal_entity

        result.revenue = result.customer_amount + result.deductions

        # НДС
        if legal_entity.legal_entity.uses_simple_tax_system():
            count_vat = False
            result.vat_amount = 0
        else:
            count_vat = True
            result.vat_amount = models.vat_20(result.customer_amount)
            vat_total += result.vat_amount
            result.vat_amount = round(result.vat_amount, 2)

        accounts = customer.customer_accounts

        account_20 = accounts.account_20_root
        production_costs = _interval_saldo(account_20, interval_first_day, interval_last_day)
        result.costs = production_costs + result.fines
        if count_vat:
            result.costs += result.vat_amount

        result.detailed_costs = []

        customer_interval = (customer, interval_first_day, interval_last_day)

        for title in account_20_industrial_titles:
            result.detailed_costs.append(
                account_20_industrial[customer_interval].get(title)
            )

        result.profit = result.revenue - result.costs
        result.efficiency = _efficiency(result.profit, result.revenue)
        result.efficiency_wo_vat = _efficiency(
            result.profit,
            result.revenue - result.vat_amount
        )

        result.services = []
        services = models.CustomerService.objects.filter(
            customer=customer
        )

        result.profit = round(result.profit, 2)

        for service in services:
            service_hours_general = models.TurnoutService.objects.filter(
                customer_service=service,
                turnout__timesheet__customer=customer,
                turnout__timesheet__sheet_date__range=(interval_first_day, interval_last_day),
            ).distinct(
            ).exclude(
                turnout__turnoutoperationtopay__operation__debet__account_20_selfemployed_work_service__isnull=False
            ).aggregate(
                s=Sum('turnout__hours_worked')
            )['s'] or 0
            service_hours_selfemployed = models.TurnoutService.objects.filter(
                customer_service=service,
                turnout__timesheet__customer=customer,
                turnout__timesheet__sheet_date__range=(interval_first_day, interval_last_day),
                turnout__turnoutoperationtopay__operation__debet__account_20_selfemployed_work_service__isnull=False
            ).distinct(
            ).aggregate(
                s=Sum('turnout__hours_worked')
            )['s'] or 0
            if service_hours_general == 0 and service_hours_selfemployed == 0:
                continue

            service_amount_general = finance.models.amount_sum(
                finance.models.Operation.objects.filter(
                    turnoutcustomeroperation__turnout__timesheet__customer=customer,
                    turnoutcustomeroperation__turnout__timesheet__sheet_date__range=(
                        interval_first_day,
                        interval_last_day
                    ),
                    turnoutcustomeroperation__turnout__turnoutservice__customer_service=service,
                ).exclude(
                    turnoutcustomeroperation__turnout__turnoutoperationtopay__operation__debet__account_20_selfemployed_work_service__isnull=False,
                ).distinct()
            )
            service_amount_selfemployed = finance.models.amount_sum(
                finance.models.Operation.objects.filter(
                    turnoutcustomeroperation__turnout__timesheet__customer=customer,
                    turnoutcustomeroperation__turnout__timesheet__sheet_date__range=(
                        interval_first_day,
                        interval_last_day
                    ),
                    turnoutcustomeroperation__turnout__turnoutservice__customer_service=service,
                    turnoutcustomeroperation__turnout__turnoutoperationtopay__operation__debet__account_20_selfemployed_work_service__isnull=False,
                ).distinct()
            )

            service_costs_general = _interval_saldo(
                [service.account_20_general_work, service.account_20_general_taxes],
                interval_first_day,
                interval_last_day
            )

            service_costs_selfemployed = _interval_saldo(
                [service.account_20_selfemployed_work, service.account_20_selfemployed_taxes],
                interval_first_day,
                interval_last_day
            )

            if count_vat:
                service_vat_general = round(models.vat_20(service_amount_general), 2)
                service_vat_selfemployed = round(models.vat_20(service_amount_selfemployed), 2)

                service_costs_general += service_vat_general
                service_costs_selfemployed += service_vat_selfemployed
            else:
                service_vat_general = 0
                service_vat_selfemployed = 0

            service_profit_general = service_amount_general - service_costs_general
            service_profit_selfemployed = service_amount_selfemployed - service_costs_selfemployed

            service_efficiency_general = _efficiency(
                service_profit_general,
                service_amount_general
            )
            service_efficiency_selfemployed = _efficiency(
                service_profit_selfemployed,
                service_amount_selfemployed
            )

            service_efficiency_wo_vat_general = _efficiency(
                service_profit_general,
                service_amount_general - service_vat_general
            )
            service_efficiency_wo_vat_selfemployed = _efficiency(
                service_profit_selfemployed,
                service_amount_selfemployed - service_vat_selfemployed
            )

            result.services.append((
                f'{service.service.name} (обычные)',
                service_hours_general,
                service_amount_general,
                service.account_20_root.pk,
                round(service_costs_general, 2),
                service_vat_general,
                round(service_profit_general, 2),
                service_efficiency_general,
                service_efficiency_wo_vat_general
            ))
            result.services.append((
                f'{service.service.name} (самозанятые)',
                service_hours_selfemployed,
                service_amount_selfemployed,
                service.account_20_root.pk,
                round(service_costs_selfemployed, 2),
                service_vat_selfemployed,
                round(service_profit_selfemployed, 2),
                service_efficiency_selfemployed,
                service_efficiency_wo_vat_selfemployed
            ))

    titles = []
    titles.extend(account_20_industrial_titles)

    # Рентабельность общая
    # часы
    total_hours = models.WorkerTurnout.objects.filter(
        timesheet__sheet_date__range=(
            first_day,
            last_day
        )
    ).aggregate(
        s=Sum('hours_worked')
    )['s'] or 0

    # выручка
    customer_amount = finance.models.amount_sum(
        _customer_operations(first_day, last_day)
    )
    turnout_deductions = finance.models.amount_sum(
        _turnout_deductions(first_day, last_day)
    )
    worker_deductions = finance.models.amount_sum(
        _worker_deductions(first_day, last_day)
    )
    turnout_adjustings = finance.models.amount_sum(
        _turnout_adjusting_operations(first_day, last_day)
    )
    revenue = (
        customer_amount +
        turnout_deductions +
        worker_deductions +
        turnout_adjustings
    )

    # расходы
    fines = finance.models.amount_sum(
        _fines(first_day, last_day)
    )

    root_10 = get_root_account('10')
    root_20 = get_root_account('20')
    root_26 = get_root_account('26')

    costs_10 = _interval_saldo(root_10, first_day, last_day)
    costs_20 = abs(_interval_saldo(root_20, first_day, last_day))
    costs_26 = abs(_interval_saldo(root_26, first_day, last_day))

    costs = sum([
        vat_total,
        fines,
        costs_10,
        costs_20,
        costs_26,
    ])

    raw_20_bonus = finance.models.amount_sum(
        _raw_20_bonuses(first_day, last_day)
    )

    profit = revenue - costs
    efficiency = _efficiency(profit, revenue)
    efficiency_wo_vat = _efficiency(profit, revenue - vat_total)

    return render(
        request,
        'the_redhuman_is/reports/efficiency.html',
        {
            'first_day': first_day,
            'last_day': last_day,
            'interval_form': forms.DaysIntervalForm(
                initial={
                    'first_day': first_day,
                    'last_day': last_day
                }
            ),
            'costs_20_titles': titles,
            'results': results,

            'total_hours': total_hours,
            'revenue': round(revenue, 2),
            'turnout_deductions': turnout_deductions,
            'worker_deductions': worker_deductions,

            'costs': round(costs, 2),
            'vat_total': round(vat_total, 2),
            'fines': fines,
            'costs_10': costs_10,
            'costs_20': costs_20,
            'raw_20_bonus': raw_20_bonus,
            'costs_26': costs_26,

            'account_10': root_10.pk,
            'account_20': root_20.pk,
            'account_26': root_26.pk,

            'profit': round(profit, 2),
            'efficiency': efficiency,
            'efficiency_wo_vat': efficiency_wo_vat,
        }
    )


_FILTERS = {
    'customeroperations': _customer_operations,
    'turnoutdeductions': _turnout_deductions,
    'workerdeductions': _worker_deductions,
    'turnoutadjustings': _turnout_adjusting_operations,
    'fines': _fines,
    'raw20bonuses': _raw_20_bonuses,
    'revenue': _revenue,
    'unknown_revenue': _unknown_revenue,
}


def operations_list(request, filter):
    filter_func = _FILTERS[filter]

    first_day, last_day = get_first_last_day(request, set_initial=False)

    total_sum = finance.models.amount_sum(filter_func(first_day, last_day))

    operations_url = request.build_absolute_uri(
        reverse(
            'the_redhuman_is:report_efficiency_operations_list_json',
            kwargs={
                'filter': filter
            }
        )
    )
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
            'total_sum': total_sum,
            'operations_url': operations_url,
        }
    )


# see detail_json() at operating_account.py
def operations_list_json(request, filter):
    draw = request.GET['draw']
    start = int(request.GET.get('start'))
    length = int(request.GET.get('length'))
    order_index = int(request.GET.get('order_index'))
    order_dir = request.GET.get('order_dir')

    order = _order(order_index, order_dir)

    filter_func = _FILTERS[filter]

    first_day, last_day = get_first_last_day(request, set_initial=False)

    all_operations = filter_func(first_day, last_day).annotate(
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
    ).order_by(
        order
    )
    total_count = all_operations.count()

    end = total_count
    if length > 0:
        end = min(total_count, start + length)
    operations = all_operations[start:end]

    data = []
    if total_count > 0:
        data = [_describe_operation(request, o) for o in operations]

    return JsonResponse(
        {
            'draw': draw,
            'recordsTotal': total_count,
            'recordsFiltered': total_count,
            'data': data
        }
    )

