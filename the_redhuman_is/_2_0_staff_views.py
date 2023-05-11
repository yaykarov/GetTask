# -*- coding: utf-8 -*-

import datetime
import json
import logging
import xlwt

from datetime import timedelta

from decimal import *

from urllib.parse import quote_plus

from django.urls import reverse
from django.db.models import (
    Count,
    F,
    OuterRef,
    Q,
    Subquery,
    Sum,
)
from django.db.models.functions import (
    Coalesce,
    Greatest,
)
from django.http import HttpResponse
from django.shortcuts import render

import finance

from the_redhuman_is import models
from the_redhuman_is.auth import staff_account_required
from the_redhuman_is.forms import CalendarForm

from the_redhuman_is.models import (
    Contract,
    Customer,
    CustomerOrder,
    TimeSheet,
    TurnoutOperationIsPayed,
    TurnoutOperationToPay,
    Worker,
    WorkerPatent,
    WorkerTurnout,
    fine_utils,
)

logger = logging.getLogger(__name__)


# Will be deprecated
@staff_account_required
def list_workers(request):
    user_groups = request.user.groups.values_list('name', flat=True)
    if request.user.is_superuser or 'Менеджеры' not in user_groups:
        workers = Worker.objects.all()
    else:
        customers = Customer.objects.filter(
            maintenancemanager__worker__workeruser__user=request.user
        )
        workers = Worker.objects.filter(
            Q(timesheet__customer__in=customers) |
            Q(worker_turnouts__timesheet__customer__in=customers)
        ).distinct()

    q = request.GET.get('q')
    if q:
        workers = workers.filter(last_name__icontains=q)

    show_last_turnouts = request.GET.get(
        'show_last_turnouts',
        'false'
    ) == 'true'

    if show_last_turnouts:
        workers = workers.annotate(
            Count('worker_turnouts', distinct=True),
            Count('contract', distinct=True),
            last_turnout_date=Subquery(
                TimeSheet.objects.filter(
                    worker_turnouts__worker__pk=OuterRef('pk')
                ).order_by(
                    '-sheet_date'
                ).values('sheet_date')[:1]
            ),
            last_turnout_customer=Subquery(
                TimeSheet.objects.filter(
                    worker_turnouts__worker__pk=OuterRef('pk')
                ).order_by(
                    '-sheet_date'
                ).values('customer__cust_name')[:1]
            ),
        )
    else:
        workers = workers.annotate(
            Count('worker_turnouts', distinct=True),
            Count('contract', distinct=True),
        )

    workers = workers.prefetch_related(
        'position',
        'citizenship'
    ).order_by(
        '-input_date'
    )

    return render(
        request,
        'the_redhuman_is/list_workers.html',
        {
            'workers': workers,
            'show_last_turnouts': show_last_turnouts
        }
    )


# Календарь
@staff_account_required
def workers_in_calendar(request):
    return render(
        request,
        "the_redhuman_is/calendar.html",
        {
            "form": CalendarForm.create()
        }
    )


def next_month(datepoint):
    if datepoint.month==12:
        return datepoint.replace(month=1).replace(year=datepoint.year+1).replace(day=1)
    else:
        return datepoint.replace(month=datepoint.month+1).replace(day=1)


def next_sunday(datepoint):
    if datepoint.weekday() == 6:
        return datepoint + datetime.timedelta(days=7)
    while not datepoint.weekday() == 6:
        datepoint = datepoint + timedelta(days=1)
    return datepoint


def get_intervals(date_begin, date_end, period_type):
    week_names = ["пн", "вт", "ср", "чт", "пт", "сб", "вс"]
    month_names = ["Января", "Февраля", "Марта", "Апреля", "Мая", "Июня", "Июля", "Августа", "Сентября", "Октября",
                   "Ноября", "Декабря"]
    if date_begin.year != date_end.year:
        few_years = True
    else:
        few_years = False
    period_begin = date_begin
    period_end = period_begin
    first_row = []
    second_row = []
    intervals = []
    while period_end <= date_end:
        if period_type == 'day':
            if few_years:
                year = "."+str(period_end.year)
            else:
                year = ""
            first_row.append(str(period_end.day)+"."+str(period_end.month)+year)
            second_row.append(week_names[period_end.weekday()])
            intervals.append([period_end, period_end])
            period_end += datetime.timedelta(days=1)
        else:
            if period_type == 'week':
                period_end = min(next_sunday(period_begin), date_end)
            else:
                period_end = min(next_month(period_begin) - datetime.timedelta(days=1), date_end)
            if few_years:
                year_begin = " "+str(period_begin.year)
                year_end = " "+str(period_end.year)
            else:
                year_begin = ""
                year_end = ""
            first_row.append(str(period_begin.day)+" "+month_names[period_begin.month-1]+year_begin)
            second_row.append(str(period_end.day)+" "+month_names[period_end.month-1]+year_end)
            intervals.append([period_begin, period_end])
            period_begin = period_end + datetime.timedelta(days=1)
            period_end = period_begin
    return first_row, second_row, intervals


@staff_account_required
def calendar_average_content(request):
    end = datetime.date.today()
    begin = datetime.date(end.year, end.month, 1)
    last_time = datetime.datetime.now()

    FORMAT = "%d.%m.%Y"
    day_begin = request.GET.get("begin_date")
    if day_begin:
        begin = datetime.datetime.strptime(day_begin, FORMAT).date()
    day_end = request.GET.get("end_date")
    if day_end:
        end = datetime.datetime.strptime(day_end, FORMAT).date()

    display = request.GET.get("display")
    if not display:
        display = "hours"

    report_type = request.GET.get("report_type")

    avg_or_sum = request.GET.get("avg_or_sum")
    if not avg_or_sum:
        avg_or_sum = "avg"

    turnouts = WorkerTurnout.objects.filter(
        timesheet__sheet_date__range=(begin, end))

    customers0 = None
    user_groups = request.user.groups.values_list('name', flat=True)
    if 'Менеджеры' in user_groups:
        customers0 = models.Customer.objects.filter(
            maintenancemanager__worker__workeruser__user=request.user
        )
        turnouts = turnouts.filter(
            timesheet__customer__in=customers0
        )

    customer_id = request.GET.get("customer")
    if customer_id:
        turnouts = turnouts.filter(timesheet__customer__pk=customer_id)

    location_id = request.GET.get("location")
    if location_id:
        turnouts = turnouts.filter(timesheet__cust_location__pk=location_id)

    service_id = request.GET.get("service")
    if service_id:
        customer_service = models.CustomerService.objects.get(pk=service_id)
        turnouts = turnouts.filter(turnoutservice__customer_service=customer_service)

    sheet_turn = request.GET.get("sheet_turn")
    if sheet_turn:
        turnouts = turnouts.filter(timesheet__sheet_turn=sheet_turn)

    customers1 = None
    mmanager = request.GET.get("mmanager")
    if mmanager:
        manager_set = models.MaintenanceManager.objects.filter(worker=mmanager)
        customers1 = []
        for manager in manager_set:
            customers1.append(manager.customer.pk)

        turnouts = turnouts.filter(timesheet__customer__in=customers1)

    customers2 = None
    dmanager = request.GET.get("dmanager")
    if dmanager:
        manager_set = models.DevelopmentManager.objects.filter(worker=dmanager)
        customers2 = []
        for manager in manager_set:
            customers2.append(manager.customer.pk)

        turnouts = turnouts.filter(timesheet__customer__in=customers2)

    turnouts = turnouts.select_related("timesheet", "worker")
    workers = turnouts.order_by("worker_id").distinct("worker_id").values_list("worker_id")

    customer_query = ~Q(pk=-1)
    # Если выбран клиент
    if customer_id:
        customer_query &= Q(customer__pk=customer_id)
    if customers0:
        customer_query &= Q(customer__in=customers0)
    # Если выбран менеджер по ведению
    if customers1:
        customer_query &= Q(customer__in=customers1)
    # Если выбран менеджер по развитию
    if customers2:
        customer_query &= Q(customer__in=customers2)

    operations = finance.models.Operation.objects.filter(
        timepoint__date__range=(begin, end)
    ).select_related("debet", "credit")

    accounts = models.WorkerOperatingAccount.objects.filter(
        worker__in=workers
    ).values('account_id').distinct()
    root_70 = finance.model_utils.get_root_account('70.')
    root_76 = finance.model_utils.get_root_account('76.')
    customer_orders = CustomerOrder.objects.filter(
        customer_query & Q(on_date__range=(begin, end)))
    if sheet_turn:
        customer_orders = customer_orders.filter(
            bid_turn=sheet_turn
        )
    total_location_set = TimeSheet.objects.filter(customer_query & Q(sheet_date__range=(begin, end)))
    credit_operations = operations.filter(credit__in=accounts)
    debet_operations = operations.filter(debet__parent=root_70)
    deduct_accounts = list(fine_utils.deduction_accounts(customer_id))

    period_performance = []
    period_hours = []
    period_turns = []
    period_payed = []
    period_to_pay = []
    period_credit = []
    period_debet = []
    period_ordered_workers = []
    period_noderived = []
    period_locations = []
    period_deducts = []

    first_row, second_row, intervals = get_intervals(begin, end, report_type)

    for interval in intervals:
        period_begin = interval[0]
        period_end = interval[1]
        day_count = (period_end - period_begin).days+1 if avg_or_sum == "avg" and not report_type == 'day' else 1
        period_turnouts = turnouts.filter(
            timesheet__sheet_date__range=(period_begin, period_end)
        )
        period_values = period_turnouts.aggregate(
            perfs=Sum("performance"),
            period_hours=Sum("hours_worked"),
            turns=Count("pk")
        )
        perfs = period_values.get("perfs", 0.0) or 0.0
        hours = period_values.get("period_hours", 0.0) or 0.0
        turns = period_values.get("turns", 0.0) or 0
        period_performance.append(float(perfs)/day_count)
        period_hours.append(float(hours)/day_count)
        period_turns.append(float(turns)/day_count)
        payed_turnouts = TurnoutOperationIsPayed.objects.filter(
            turnout__in=period_turnouts,
            turnout__is_payed=True,
            operation__debet__parent=root_70
        ).values_list("turnout__pk")

        payed = TurnoutOperationToPay.objects.filter(
            turnout__in=payed_turnouts,
            operation__credit__parent=root_70
        ).aggregate(
            amounts=Sum("operation__amount")
        ).get("amounts", 0.0) or Decimal(0.0)

        to_pay = TurnoutOperationToPay.objects.filter(
            turnout__in=period_turnouts,
            turnout__is_payed=False,
            operation__credit__parent=root_70
        ).aggregate(
            amounts=Sum("operation__amount")
        ).get("amounts", 0.0) or Decimal(0.0)

        period_payed.append(float(payed)/day_count)
        period_to_pay.append(float(to_pay)/day_count)

        credit = TurnoutOperationToPay.objects.filter(
            turnout__in=period_turnouts,
            operation__credit__parent=root_70
        )
        if credit.exists():
            credit_value = credit.aggregate(
                amounts=Sum("operation__amount")
            ).get("amounts", 0.0) or Decimal(0.0)
            period_credit.append(float(credit_value)/day_count)
        else:
            period_credit.append(0.0)
        debet = debet_operations.filter(
            timepoint__date__range=(period_begin, period_end)
        )
        if debet.exists():
            debet_value = debet.aggregate(
                amounts=Sum("amount")
            ).get("amounts", 0.0) or Decimal(0.0)
            period_debet.append(float(debet_value)/day_count)
        else:
            period_debet.append(0.0)
        deduct = operations.filter(
            debet__in=accounts,
            credit__in=deduct_accounts,
            timepoint__date__range=(period_begin, period_end)
        ).aggregate(amounts=Sum("amount")).get("amounts") or 0.0
        period_deducts.append(float(deduct)/day_count)

        ordered_workers_number = customer_orders.filter(
            on_date__range=(period_begin, period_end)
        ).aggregate(
            total_workers=Coalesce(Sum('number_of_workers'), 0)
        ).get(
            'total_workers'
        )
        period_ordered_workers.append(ordered_workers_number/day_count)

        noderived = customer_orders.filter(
            on_date__range=(period_begin, period_end)
        ).annotate(
            noderived=Greatest(
                F('number_of_workers') - Count('timesheet__worker_turnouts'),
                0
            )
        ).aggregate(
            noderived_sum=Coalesce(Sum('noderived'), 0)
        ).get('noderived_sum')

        period_noderived.append(float(noderived)/day_count)

        if avg_or_sum == "avg" and not report_type == 'day':
            locations = total_location_set.filter(
                sheet_date__range=(period_begin, period_end)
            ).values(
                "sheet_date"
            ).annotate(
                day_locations=Count("cust_location_id", distinct=True)
            ).aggregate(
                locations=Sum("day_locations")
            ).get("locations", 0) or 0
        else:
            locations = total_location_set.filter(
                sheet_date__range=(period_begin, period_end)
            ).aggregate(
                locations=Count("cust_location_id", distinct=True)
            ).get("locations", 0) or 0
        period_locations.append(float(locations)/day_count)
    total_turnout_values = turnouts.aggregate(
        perfs=Sum("performance"),
        total_hours=Sum("hours_worked"),
        turns=Count("pk")
    )
    total_payed_turnouts = TurnoutOperationIsPayed.objects.filter(
        turnout__in=turnouts,
        turnout__is_payed=True,
        operation__debet__parent=root_70
    ).values_list("turnout__pk")
    total_payed = TurnoutOperationToPay.objects.filter(
        turnout__in=total_payed_turnouts,
        operation__credit__parent=root_70
    ).aggregate(
        amounts=Sum("operation__amount")
    ).get("amounts", 0.0) or 0.0
    total_to_pay = TurnoutOperationToPay.objects.filter(
        turnout__in=turnouts,
        turnout__is_payed=False,
        operation__credit__parent=root_70
    ).aggregate(
        amounts=Sum("operation__amount")
    ).get("amounts", 0.0) or 0.0

    total_performance = total_turnout_values.get("perfs", 0.0) or 0
    total_hours = total_turnout_values.get("total_hours", 0.0) or 0
    total_turns = total_turnout_values.get("turns", 0.0) or 0

    total_credit = credit_operations.filter(
        timepoint__date__range=(begin, end)
    ).aggregate(
        amounts=Sum('amount')
    ).get("amounts", 0.0) or 0

    total_debet = debet_operations.filter(
        timepoint__date__range=(begin, end)
    ).aggregate(
        amounts=Sum('amount')
    ).get("amounts", 0.0) or 0

    total_ordered = customer_orders.aggregate(
        workers=Sum("number_of_workers")
    ).get("workers", 0.0) or 0

    total_noderived = customer_orders.annotate(
        noderived=Greatest(
            F('number_of_workers') - Count('timesheet__worker_turnouts'),
            0
        )
    ).aggregate(
        noderived_sum=Coalesce(Sum('noderived'), 0)
    ).get('noderived_sum')

    total_locations = total_location_set.order_by("cust_location_id").distinct("cust_location_id").count()
    total_deduct = operations.filter(
        debet__in=accounts,
        credit__in=deduct_accounts,
        timepoint__date__range=(begin, end)
    ).aggregate(
        amounts=Sum("amount")
    ).get("amounts") or 0.0

    print("Finished in "+str((datetime.datetime.now()-last_time).seconds)+" sec")
    total_day_count = (end - begin).days+1
    response = render(
        request,
        "the_redhuman_is/calendar_average_content.html",
        {
            "day_performance": period_performance,
            "avg_performance": total_performance / total_day_count,
            "sum_performance": total_performance,

            "day_hours": period_hours,
            "avg_hours": total_hours / total_day_count,
            "sum_hours": total_hours,

            "day_turnouts": period_turns,
            "avg_turnouts": total_turns / total_day_count,
            "sum_turnouts": total_turns,

            "day_credit": period_credit,
            "avg_credit": total_credit / total_day_count,
            "sum_credit": total_credit,

            "day_debet": period_debet,
            "avg_debet": total_debet / total_day_count,
            "sum_debet": total_debet,

            "day_ordered": period_ordered_workers,
            "avg_ordered": total_ordered / total_day_count,
            "sum_ordered": total_ordered,

            "day_noderived": period_noderived,
            "avg_noderived": total_noderived / total_day_count,
            "sum_noderived": total_noderived,

            "day_locations": period_locations,
            "avg_locations": sum(period_locations) / len(intervals),
            "sum_locations": total_locations,

            "day_payed": period_payed,
            "avg_payed": total_payed / total_day_count,
            "sum_payed": total_payed,

            "day_to_pay": period_to_pay,
            "avg_to_pay": total_to_pay / total_day_count,
            "sum_to_pay": total_to_pay,

            "day_deduct": period_deducts,
            "avg_deduct": total_deduct / total_day_count,
            "sum_deduct": total_deduct,

            "show_average_performance": display == "performance",
            "show_sum": display in ["debet", "credit", "payed", "to_pay"],
            "days": first_row,
            "week_days": second_row
        }
    )
    return response


def calendar_detail_xls(data):
    wb = xlwt.Workbook(encoding='utf-8')
    ws = wb.add_sheet('Sheet1', cell_overwrite_ok=True)
    row_num = 0
    font_style = xlwt.XFStyle()
    font_style.font.bold = True

    col_num = 0
    ws.write(row_num, col_num, '№', font_style)
    ws.merge(row_num, row_num+1, col_num, col_num)
    col_num += 1
    ws.write(row_num, col_num, 'Рабочий', font_style)
    ws.merge(row_num, row_num+1, col_num, col_num)
    col_num += 1
    ws.write(row_num, col_num, 'Остаток', font_style)
    ws.merge(row_num, row_num+1, col_num, col_num)
    col_num += 1

    for num in range(len(data['days'])):
        ws.write(row_num, col_num, data['days'][num], font_style)
        col_num += 1
    if data['show_average_performance']:
        ws.write(row_num, col_num, 'Средняя выработка', font_style)
        ws.merge(row_num, row_num+1, col_num, col_num)
        col_num += 1
    ws.write(row_num, col_num, 'Кол-во выходов', font_style)
    ws.merge(row_num, row_num+1, col_num, col_num)
    col_num += 1
    if data['show_sum']:
        ws.write(row_num, col_num, 'Сумма', font_style)
        ws.merge(row_num, row_num+1, col_num, col_num)
        col_num += 1
    row_num += 1
    col_num = 3
    for num in range(len(data['week_days'])):
        ws.write(row_num, col_num, data['week_days'][num], font_style)
        col_num += 1

    font_style = xlwt.XFStyle()
    for index, worker, line, worked_days, average_perf, sum in data['grid']:
        row_num += 1
        col_num = 0
        ws.write(row_num, col_num, index, font_style)
        col_num += 1
        ws.write(row_num, col_num, str(worker), font_style)
        col_num += 1
        for cell in line:
            ws.write(row_num, col_num, cell, font_style)
            col_num += 1
        if data['show_average_performance']:
            ws.write(row_num, col_num, average_perf, font_style)
            col_num += 1
        ws.write(row_num, col_num, worked_days, font_style)
        col_num += 1
        if data['show_sum']:
            ws.write(row_num, col_num, sum, font_style)
            col_num += 1
    return wb


@staff_account_required
def calendar_detail_content(request):
    end = datetime.date.today()
    begin = datetime.date(end.year, end.month, 1)
    last_time = datetime.datetime.now()

    FORMAT = "%d.%m.%Y"
    day_begin = request.GET.get("begin_date")
    if day_begin:
        begin = datetime.datetime.strptime(day_begin, FORMAT).date()
    day_end = request.GET.get("end_date")
    if day_end:
        end = datetime.datetime.strptime(day_end, FORMAT).date()

    display = request.GET.get("display")
    if not display:
        display = "hours"

    report_type = request.GET.get("report_type")

    avg_or_sum = request.GET.get("avg_or_sum")

    turnouts = WorkerTurnout.objects.filter(
        timesheet__sheet_date__range=(begin, end))

    customers = models.Customer.objects.all()

    user_groups = request.user.groups.values_list('name', flat=True)
    if 'Менеджеры' in user_groups:
        customers = models.Customer.objects.filter(
            maintenancemanager__worker__workeruser__user=request.user
        )
        turnouts = turnouts.filter(
            timesheet__customer__in=customers
        )

    customer_id = request.GET.get("customer")
    if customer_id:
        turnouts = turnouts.filter(timesheet__customer__pk=customer_id)

    location_id = request.GET.get("location")
    if location_id:
        turnouts = turnouts.filter(timesheet__cust_location__pk=location_id)

    service_id = request.GET.get("service")
    if service_id:
        customer_service = models.CustomerService.objects.get(pk=service_id)
        turnouts = turnouts.filter(turnoutservice__customer_service=customer_service)

    sheet_turn = request.GET.get("sheet_turn")
    if sheet_turn:
        turnouts = turnouts.filter(timesheet__sheet_turn=sheet_turn)

    customers1 = None
    mmanager = request.GET.get("mmanager")
    if mmanager:
        manager_set = models.MaintenanceManager.objects.filter(worker=mmanager)
        customers1 = []
        for manager in manager_set:
            customers1.append(manager.customer.pk)

        turnouts = turnouts.filter(timesheet__customer__in=customers1)

    customers2 = None
    dmanager = request.GET.get("dmanager")
    if dmanager:
        manager_set = models.DevelopmentManager.objects.filter(worker=dmanager)
        customers2 = []
        for manager in manager_set:
            customers2.append(manager.customer.pk)

        turnouts = turnouts.filter(timesheet__customer__in=customers2)

    turnouts = turnouts.select_related("timesheet", "worker")

    workers = turnouts.order_by("worker_id").distinct("worker_id").values_list("worker_id")

    if display in ("credit", "debet", "deduct", "fine", "credit_minus_deduct"):
        operations = finance.models.Operation.objects.filter(
            timepoint__date__range=(begin, end)
        ).select_related("timepoint", "credit", "debet")

    print("Turnouts processed in " + str((datetime.datetime.now() - last_time).seconds) + " sec")

    last_time = datetime.datetime.now()
    grid = []
    index = 1

    root_70 = finance.model_utils.get_root_account('70.')
    first_row, second_row, intervals = get_intervals(begin, end, report_type)
    if display in ["deduct", "credit_minus_deduct"]:
        deduct_accounts = list(fine_utils.deduction_accounts(customer_id))
        deduct_operations = operations.filter(
            debet__parent=root_70,
            credit__in=deduct_accounts,
            timepoint__date__range=(begin, end)
        ).select_related("debet", "credit", "timepoint")

    worker_query = models.Worker.objects.all()
    worker_query = worker_query.filter(pk__in=workers,
                                       workerpassport__is_actual=True)
    worker_query = worker_query.annotate(
        passport=F('workerpassport__another_passport_number')
    )
    for worker in worker_query:
        line = []
        n = 0
        s = 0
        is_empty = True
        worker_account = worker.worker_account.account
        worker_debet = finance.models.Operation.objects.filter(
            debet=worker_account,
            timepoint__date__lt=begin
        ).aggregate(
            amounts=Sum("amount")
        ).get('amounts') or 0
        worker_credit = finance.models.Operation.objects.filter(
            credit=worker_account,
            timepoint__date__lt=begin
        ).aggregate(
            amounts=Sum("amount")
        ).get('amounts') or 0
        worker_saldo = worker_credit - worker_debet
        line.append(worker_saldo)
        for interval in intervals:
            period_begin = interval[0]
            period_end = interval[1]
            day_count = (period_end - period_begin).days+1 if avg_or_sum == "avg" and not report_type == 'day' else 1
            period_turnouts = turnouts.filter(timesheet__sheet_date__range=(period_begin, period_end), worker=worker.pk)
            turns = period_turnouts.count()
            if display == "performance":
                result = period_turnouts.aggregate(perfs=Sum("performance")).get("perfs", 0.0)
            elif display == "credit":
                # result = operations.filter(timepoint__date__range=(period_begin, period_end),
                #     credit=worker_account).aggregate(amounts=Sum("amount")).get("amounts", 0.0)
                result = TurnoutOperationToPay.objects.filter(
                    turnout__in=period_turnouts,
                    operation__credit__parent=root_70
                ).aggregate(
                    amounts=Sum("operation__amount")
                ).get("amounts", 0.0)
            elif display == "debet":
                result = operations.filter(
                    timepoint__date__range=(period_begin, period_end),
                    debet=worker_account
                ).aggregate(
                    amounts=Sum("amount")
                ).get("amounts", 0.0)
            elif display == "payed":
                payed_turnouts = TurnoutOperationIsPayed.objects.filter(
                    turnout__in=period_turnouts,
                    turnout__is_payed=True,
                    turnout__worker=worker.pk,
                    operation__debet__parent=root_70
                ).values_list("turnout__pk")
                result = TurnoutOperationToPay.objects.filter(
                    turnout__in=payed_turnouts,
                    turnout__worker=worker.pk,
                    operation__credit__parent=root_70
                ).aggregate(
                    amounts=Sum("operation__amount")
                ).get("amounts", 0.0)
            elif display == "to_pay":
                result = TurnoutOperationToPay.objects.filter(
                    turnout__in=period_turnouts,
                    turnout__is_payed=False,
                    operation__credit__parent=root_70
                ).aggregate(
                    amounts=Sum("operation__amount")
                ).get("amounts", 0.0)
            elif display == "fine":
                fine_operations = finance.models.Operation.objects.filter(
                    timepoint__date__range=(period_begin, period_end),
                    customerfine__isnull=False,
                    customerfine__turnout__worker=worker,
                    customerfine__turnout__timesheet__customer__in=customers
                )
                if customers1:
                    fine_operations = fine_operations.filter(
                        customerfine__turnout__timesheet__customer__in=customers1
                    )
                if customers2:
                    fine_operations = fine_operations.filter(
                        customerfine__turnout__timesheet__customer__in=customers2
                    )
                result = fine_operations.aggregate(
                    amounts=Sum('amount')
                ).get(
                    'amounts'
                ) or 0.0
            elif display == "deduct":
                result = deduct_operations.filter(
                    debet=worker_account,
                    timepoint__date__range=(period_begin, period_end)
                ).aggregate(
                    amounts=Sum("amount")
                ).get("amounts", 0.0)
            elif display == "credit_minus_deduct":
                credit = operations.filter(
                    timepoint__date__range=(period_begin, period_end),
                    credit=worker_account
                ).aggregate(
                    amounts=Sum("amount")
                ).get("amounts", 0.0) or 0.0
                deduct = deduct_operations.filter(
                    debet=worker_account,
                    timepoint__date__range=(period_begin, period_end)
                ).aggregate(
                    amounts=Sum("amount")
                ).get("amounts", 0.0) or 0.0
                result = float(credit) - float(deduct)
            else:
                result = period_turnouts.aggregate(
                    hours=Sum("hours_worked")
                ).get("hours")

            if result is not None:
                is_empty = False
            if result is None:
                if display == "debet":
                    line.append("0")
                    n = n + turns
                else:
                    line.append("-")
            else:
                s += float(result)
                n = n + turns
                result = float(result) / day_count
                line.append(result)
        if is_empty:
            continue
        average_performance = 0
        if n > 0:
            average_performance = s / n
        grid.append((index, worker, line, n, average_performance, s))
        index += 1

    print("Finished in " + str((datetime.datetime.now() - last_time).seconds) + " sec")
    if request.GET.get('output') == 'xls':
        try:
            customer = Customer.objects.get(id=customer_id)
        except Customer.DoesNotExist:
            customer = ''
        try:
            location = models.CustomerLocation.objects.get(id=location_id)
        except models.CustomerLocation.DoesNotExist:
            location = ''

        if display == 'performance':
            display_name = 'Выработка'
        elif display == 'credit':
            display_name = 'Начисления'
        elif display == 'debet':
            display_name = 'Выплаты'
        elif display == 'to_pay':
            display_name = 'Не оплаченные'
        elif display == 'payed':
            display_name = 'Оплаченные'
        elif display == 'deduct':
            display_name = 'Вычеты'
        elif display == 'credit_minus_deduct':
            display_name = 'Начисления-Вычеты'
        else:
            display_name = 'Часы'

        file_name = '{}_{}_{}_{}_с_{}_по_{}_{}.xls'.format(
            str(customer),
            str(location),
            str(customer_service) if service_id else '',
            display_name,
            begin.strftime('%d-%m'),
            end.strftime('%d-%m'),
            sheet_turn if sheet_turn else ''
        )
        response = HttpResponse(content_type='application/vnd.ms-excel')
        response['Content-Disposition'] = "attachment; filename*=UTF-8''" + \
            quote_plus(file_name)
        xls = calendar_detail_xls({
            "show_average_performance": display == "performance",
            "show_sum": display in ["debet", "credit", "payed", "to_pay", "deduct", "fine"],
            "days": first_row,
            "week_days": second_row,
            "grid": grid,
        })
        xls.save(response)
        return response
    else:
        response = render(
            request,
            "the_redhuman_is/calendar_detail_content.html",
            {
                "show_average_performance": display == "performance",
                "show_sum": display in ["debet", "credit", "payed", "to_pay", "deduct", "fine"],
                "days": first_row,
                "week_days": second_row,
                "grid": grid,
                "current_url": request.get_full_path()
            }
        )
        return response


ERRORS_CONST = {
    'lastname': 'Не указана фамилия',
    'name': 'Не указано имя',
    'birth_date': 'Не указана дата рождения',
    'mig_date': 'Не указана дата выдачи миграционной карты',
    'workerpass': 'Нет актуального паспорта',
    'pass_date_of_issue': 'Не указана дата выдачи паспорта',
    'pass_issued_by': 'Не указано кем выдан паспорт',
    'registration': 'Нет актуальной регистрации',
    'reg_date_of_issue': 'Не указа дата выдачи регистрации',
    'patent_begin_date': 'Не указана дата выдачи патента',
    'patent_end_date': 'Не указана дата завершения патента',
    'contract': 'Нет актуального договора',
    'contractor': 'Не указан подрядчик',
    'contract_begin_date': 'Не указана дата заключения контракта',
    'contract_end_date': 'Не указана дата завершения контракта',
}


def _generate_workers_error_messages(errors_list):
    data = list()
    for item in errors_list:
        try:
            worker = Worker.objects.get(pk=item['worker_id'])
        except Worker.DoesNotExist:
            pass
        else:
            errors = list()
            for error in item['errors']:
                url = ''
                if error in ['lastname', 'name', 'birth_date', 'mig_date']:
                    url = reverse(
                        'the_redhuman_is:worker_edit',
                        kwargs={'pk': worker.pk}
                    )
                elif error == 'workerpass':
                    url = reverse('the_redhuman_is:new_passport',
                                  kwargs={'pk': worker.pk})
                elif error in ['pass_date_of_issue', 'pass_issued_by']:
                    passport = worker.actual_passport
                    if passport:
                        url = reverse(
                            'the_redhuman_is:edit_passport',
                            kwargs={'pk': passport.pk}
                        )
                    else:
                        url = reverse(
                            'the_redhuman_is:new_passport',
                            kwargs={'pk': worker.pk}
                        )
                elif error == 'registration':
                    url = reverse(
                        'the_redhuman_is:new_registration',
                        kwargs={'pk': worker.pk}
                    )
                elif error == 'reg_date_of_issue':
                    registration = worker.actual_registration
                    if registration:
                        url = reverse(
                            'the_redhuman_is:edit_registration',
                            kwargs={'pk': registration.pk}
                        )
                    else:
                        url = reverse(
                            'the_redhuman_is:new_registration',
                            kwargs={'pk': worker.pk}
                        )
                elif error in ['patent_begin_date', 'patent_end_date']:
                    try:
                        patent = WorkerPatent.objects.get(workers_id=worker,
                                                          is_actual=True)
                    except WorkerPatent.DoesNotExist:
                        pass
                    else:
                        url = reverse(
                            'the_redhuman_is:edit_patent',
                            kwargs={'pk': patent.pk}
                        )
                elif error in ['contract_begin_date', 'contract_end_date', 'contractor']:
                    try:
                        contract = Contract.objects.get(c_worker=worker,
                                                        is_actual=True)
                    except Contract.DoesNotExist:
                        url = reverse(
                            'the_redhuman_is:new_contract',
                            kwargs={'pk': worker.pk}
                        )
                        error = 'contract'
                    else:
                        url = reverse(
                            'the_redhuman_is:edit_contract',
                            kwargs={'pk': contract.pk}
                        )
                if url:
                    errors.append({'name': ERRORS_CONST[error], 'url': url})
            data.append({'name': str(worker), 'errors': errors})
    return data


@staff_account_required
def notice_download_status(request):
    errors_string = request.session.get('workers_error', None)
    if errors_string:
        data = _generate_workers_error_messages(json.loads(errors_string))
    else:
        data = ''
    if data:
        head_title = 'Ошибки при заполнении данных работников'
    else:
        head_title = 'Уведомления сгенерированы без ошибок'

    return render(
        request,
        'the_redhuman_is/notice_download_status.html',
        {
            'head_title': head_title,
            'workers': data,
        }
    )


@staff_account_required
def export_workers(request):
    wb = xlwt.Workbook(encoding='utf-8')
    ws = wb.add_sheet('Список рабочих', cell_overwrite_ok=True)

    workers = Worker.objects.filter(
        tel_number__isnull=False
    ).exclude(
        tel_number=''
    ).distinct()

    ws.col(0).width = 8000
    ws.col(1).width = 3600
    ws.col(2).width = 5000
    ws.col(3).width = 12000

    def _citizenship(worker):
        if worker.citizenship:
            return worker.citizenship.name
        else:
            return worker.citizenship1

    today = datetime.date.today()

    def _worker_details(worker):
        turnouts = worker.get_turnouts()

        if not turnouts:
            return None, None, None, None

        location = turnouts.last().timesheet.cust_location
        location = '{} - {}'.format(location.customer_id, location.location_name)

        first_date = turnouts.first().timesheet.sheet_date
        last_date = turnouts.last().timesheet.sheet_date

        days = (today - last_date).days

        return location, first_date, last_date, days

    date_format = xlwt.XFStyle()
    date_format.num_format_str = 'dd.mm.yyyy'

    row = 0
    for worker in workers:
        col = 0
        ws.write(row, col, worker.last_name + ' ' + worker.name)

        col += 1
        ws.write(row, col, worker.tel_number)

        col += 1
        ws.write(row, col, _citizenship(worker))

        location, first_date, last_date, days = _worker_details(worker)

        col += 1
        ws.write(row, col, location)

        col += 1
        ws.write(row, col, first_date, date_format)

        col += 1
        ws.write(row, col, last_date, date_format)

        col += 1
        ws.write(row, col, days)

        row += 1

    response = HttpResponse(content_type='application/vnd.ms-excel')
    response['Content-Disposition'] = "attachment; filename*=UTF-8''workers.xls"
    wb.save(response)
    return response

