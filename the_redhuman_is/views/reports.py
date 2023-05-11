# -*- coding: utf-8 -*-

import datetime

from django.db.models import (
    Count,
    F,
    OuterRef,
    Subquery,
    Sum,
    Value,
)
from django.db.models.functions import (
    Coalesce,
    Lower,
)

from django.shortcuts import render
from django.utils import timezone

from applicants.models import active_applicants

from finance.models import (
    Account,
    Operation,
)

from the_redhuman_is.auth import staff_account_required

from the_redhuman_is.models import (
    CustomerOrder,
    TimeSheet,
    TurnoutOperationToPay,
    Worker,
    WorkerTurnout,
)

from the_redhuman_is import (
    forms,
    models,
)

from utils.date_time import (
    as_default_timezone,
    date_from_string,
)

from utils.numbers import ZERO_OO

from the_redhuman_is.views.utils import get_first_last_day


def _overdue_timesheets(date, manager):
    timesheets = TimeSheet.objects.filter(
        sheet_date=date
    )
    if manager:
        timesheets = timesheets.filter(
            customer__maintenancemanager__worker__workeruser__user=manager
        )
    before = 0
    after = 0
    for timesheet in timesheets:
        expired, delay = timesheet.creation_delay()
        if expired:
            before += 1
        expired, delay = timesheet.closing_delay()
        if expired:
            after += 1

    return before, after


def _ordered(date, manager):
    orders = CustomerOrder.objects.filter(
        on_date=date
    )
    if manager:
        orders = orders.filter(
            customer__maintenancemanager__worker__workeruser__user=manager
        )
    def _number_of_workers(orders):
        return orders.aggregate(
            Sum('number_of_workers')
        )['number_of_workers__sum'] or 0

    return (
        _number_of_workers(orders.filter(bid_turn='День')),
        _number_of_workers(orders.filter(bid_turn='Ночь'))
    )


def _new_turnouts(date, manager):
    def _new(turnouts):
        count = 0
        for turnout in turnouts:
            if turnout.is_first():
                count += 1
        return count

    turnouts = WorkerTurnout.objects.filter(
        timesheet__sheet_date=date
    )
    if manager:
        turnouts = turnouts.filter(
            timesheet__customer__maintenancemanager__worker__workeruser__user=manager
        )
    return (
        _new(turnouts.filter(worker__citizenship__name='РФ')),
        _new(turnouts.exclude(worker__citizenship__name='РФ')),
    )


def _managers(user=None):
    workers = Worker.objects.filter(
        maintenancemanager__isnull=False
    ).distinct()
    if user:
        workers = workers.filter(
            workeruser__user=user
        )
    return workers


def _noderived(date, manager=None):
    result = []
    for worker in _managers(manager):
        noderived = 0
        timesheets = TimeSheet.objects.filter(
            sheet_date=date,
            customer__maintenancemanager__worker=worker
        )
        for timesheet in timesheets:
            ordered = timesheet.customerorder.number_of_workers
            real = timesheet.worker_turnouts.count()
            if ordered > real:
                noderived += (ordered - real)
        result.append((worker, noderived))
    return result


def _absent(date, manager=None):
    previous_day = date - datetime.timedelta(days=1)
    result = []
    for worker in _managers(manager):
        count = Worker.objects.filter(
            worker_turnouts__timesheet__sheet_date=previous_day,
            worker_turnouts__timesheet__customer__maintenancemanager__worker=worker
        ).exclude(
            worker_turnouts__timesheet__sheet_date=date
        ).distinct(
        ).count()
        result.append((worker, count))
    return result


def _unclosed_orders(date, manager=None):
    result = []
    for worker in _managers(manager):
        orders = CustomerOrder.objects.filter(
            on_date__lte=date,
            customer__maintenancemanager__worker=worker,
            timesheet__isnull=True
        )
        count = orders.aggregate(
            Sum('number_of_workers')
        )['number_of_workers__sum'] or 0
        result.append((worker, count))
    return result


def _turnouts(first_day, last_day):
    timesheets = TimeSheet.objects.filter(
        sheet_date__gte=first_day,
        sheet_date__lte=last_day
    )
    return WorkerTurnout.objects.filter(
        timesheet__in=timesheets
    )


def _money(first_day, last_day):
    turnouts = _turnouts(first_day, last_day)
    customer_accrual = Operation.objects.filter(
        turnoutcustomeroperation__turnout__in=turnouts
    ).distinct(
    ).aggregate(
        Sum('amount')
    )['amount__sum'] or 0

    worker_accrual = Operation.objects.filter(
        turnoutoperationtopay__turnout__in=turnouts
    ).distinct(
    ).aggregate(
        Sum('amount')
    )['amount__sum'] or 0

    return customer_accrual, worker_accrual


def _unpayed(first_day, last_day):
    turnouts = _turnouts(first_day, last_day)
    return TurnoutOperationToPay.objects.filter(
        turnout__in=turnouts,
        turnout__is_payed=False,
    ).distinct().aggregate(
        Sum("operation__amount")
    ).get("operation__amount__sum") or 0


@staff_account_required
def dashboard_root(request):
    show_full_info = request.user.is_superuser

    manager = request.user
    if show_full_info:
        manager = None

    now = as_default_timezone(timezone.now())
    today = now.date()
    yesterday = today - datetime.timedelta(days=1)
    tomorrow = today + datetime.timedelta(days=1)

    ts_overdue_before, ts_overdue_after = _overdue_timesheets(
        yesterday,
        manager
    )

    yesterday_turnouts = WorkerTurnout.objects.filter(
        timesheet__sheet_date=yesterday
    ).distinct()
    if manager:
        yesterday_turnouts = yesterday_turnouts.filter(
            timesheet__customer__maintenancemanager__worker__workeruser__user=manager
        )

    tomorrow_ordered_day, tomorrow_ordered_night = _ordered(
        tomorrow,
        manager
    )

    turnouts_russian, turnouts_not_russian = _new_turnouts(
        yesterday,
        manager
    )

    first_day_of_month = today.replace(day=1)

    data = {
        'search_form': forms.WorkerSearchForm(),

        'yesterday': yesterday,
        'today': today,
        'tomorrow': tomorrow,

        'ts_overdue_before': ts_overdue_before,
        'ts_overdue_after': ts_overdue_after,

        'yesterday_turnouts': yesterday_turnouts.count(),

        'tomorrow_ordered_day': tomorrow_ordered_day,
        'tomorrow_ordered_night': tomorrow_ordered_night,

        'new_turnouts': turnouts_russian + turnouts_not_russian,
        'new_turnouts_russian': turnouts_russian,
        'new_turnouts_not_russian': turnouts_not_russian,

        'noderived': _noderived(yesterday, manager),

        'absent': _absent(yesterday, manager),

        'unclosed_orders': _unclosed_orders(today, manager),
    }

    if show_full_info:
        customers, workers = _money(first_day_of_month, today)
        data['customer_accrual'] = customers
        data['worker_accrual'] = workers
        data['unpayed'] = _unpayed(first_day_of_month, today)

    return render(
        request,
        'the_redhuman_is/reports/dashboard_root.html',
        data
    )


@staff_account_required
def workers_to_link_with_applicants(request):
    apps = active_applicants().filter(
        worker_link__isnull=True
    )

    workers = set()
    for applicant in apps:
        linked_workers = applicant.linked_workers()
        for worker in linked_workers:
            workers.add(worker)

    return render(
        request,
        'the_redhuman_is/reports/workers_to_link_with_applicants.html',
        {
            'workers': workers
        }
    )


def _add_saldo(accounts, is_saldo_credit=True):
    debit_subquery = Subquery(
        Operation.objects.filter(
            debet=OuterRef('pk')
        ).values(
            'debet'
        ).annotate(
            Sum('amount'),
        ).values('amount__sum')
    )

    credit_subquery = Subquery(
        Operation.objects.filter(
            credit=OuterRef('pk')
        ).values(
            'credit'
        ).annotate(
            Sum('amount'),
        ).values('amount__sum')
    )

    annotated = accounts.annotate(
        debit_total=Coalesce(debit_subquery, ZERO_OO),
        credit_total=Coalesce(credit_subquery, ZERO_OO),
    )
    if is_saldo_credit:
        annotated = annotated.annotate(
            saldo=F('credit_total') - F('debit_total')
        )
    else:
        annotated = annotated.annotate(
            saldo=F('debit_total') - F('credit_total')
        )

    return annotated


@staff_account_required
def workers_debtors(request):
    accounts = Account.objects.filter(
        worker_account__isnull=False,
        children__isnull=True,
    )

    accounts = _add_saldo(
        accounts,
        False
    ).select_related(
        'worker_account__worker'
    ).exclude(
        saldo__lte=0
    )

    workers = []
    total = 0
    for account in accounts:
        saldo = account.saldo
        total += saldo
        workers.append((account.worker_account.worker, saldo))

    return render(
        request,
        'the_redhuman_is/reports/workers_debtors.html',
        {
            'workers': workers,
            'total': total
        }
    )


@staff_account_required
def workers_creditors(request):
    first_day = date_from_string(request.GET.get('first_day', '01.01.2015'))
    last_day_param = request.GET.get('last_day')

    if last_day_param:
        last_day = date_from_string(last_day_param)
    else:
        now = as_default_timezone(timezone.now())
        today = now.date()
        last_day = today - datetime.timedelta(days=30)

    workers = Worker.objects.all().annotate(
        last_turnout_date=Subquery(
            models.TimeSheet.objects.filter(
                worker_turnouts__worker__pk=OuterRef('pk')
            ).order_by(
                '-sheet_date'
            ).values(
                'sheet_date'
            )[:1]
        )
    ).filter(
        last_turnout_date__gte=first_day
    ).exclude(
        worker_turnouts__timesheet__sheet_date__gte=last_day
    )

    accounts = _add_saldo(
        Account.objects.filter(
            worker_account__worker__in=workers
        )
    ).annotate(
        worker=F('worker_account__worker')
    ).exclude(
        saldo__lte=0
    )

    creditors = []
    total = 0
    for account in accounts:
        saldo = account.saldo
        total += saldo
        creditors.append((Worker.objects.get(pk=account.worker), saldo))

    return render(
        request,
        'the_redhuman_is/reports/workers_creditors.html',
        {
            'first_day_form': forms.SingleDateForm(
                field_name='first_day',
                initial={
                    'first_day': first_day
                }
            ),
            'last_day_form': forms.SingleDateForm(
                field_name='last_day',
                initial={
                    'last_day': last_day
                }
            ),
            'workers': creditors,
            'total': total
        }
    )


@staff_account_required
def workers_with_deposits(request):
    accounts = _add_saldo(
        Account.objects.filter(
            workerdeposit__isnull=False
        )
    ).select_related(
        'workerdeposit'
    ).exclude(
        saldo=0
    )

    workers = []
    total = 0
    for account in accounts:
        saldo = account.saldo
        total += saldo
        worker = account.workerdeposit.worker
        remainder = -1 * worker.worker_account.account.turnover_saldo()
        workers.append((account, saldo, remainder))

    return render(
        request,
        'the_redhuman_is/reports/workers_with_deposits.html',
        {
            'workers': workers,
            'total': total
        }
    )


@staff_account_required
def applicants_cities(request):
    first_day, last_day = get_first_last_day(request)

    applicants = active_applicants().filter(
        init_date__range=(first_day, last_day)
    ).annotate(
        city_lc=Coalesce(Lower('city'), Value('не заполнен')),
    ).values(
        'city_lc'
    ).annotate(
        city_count=Count('city_lc'),
    ).order_by(
        '-city_count'
    )

    return render(
        request,
        'the_redhuman_is/reports/applicants_cities.html',
        {
            'filter_form': forms.DaysIntervalForm(
                initial={
                    'first_day': first_day,
                    'last_day': last_day
                }
            ),
            'items': applicants,
        }
    )

