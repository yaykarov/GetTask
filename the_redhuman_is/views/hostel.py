# -*- coding: utf-8 -*-

import datetime
import xlwt

from django.db import transaction
from django.db.models import CharField
from django.db.models import F
from django.db.models import OuterRef
from django.db.models import Q
from django.db.models import Subquery
from django.db.models import Value
from django.db.models.functions import Concat

from django.contrib.auth.decorators import user_passes_test

from django.http import HttpResponse
from django.shortcuts import redirect
from django.shortcuts import render
from django.views.decorators.http import require_POST

from django.utils import timezone

import finance

from the_redhuman_is.auth import staff_account_required

from the_redhuman_is import models
from the_redhuman_is.forms import CustomerSelectionForm
from the_redhuman_is.forms import DaysIntervalForm
from the_redhuman_is.forms import SingleDateForm
from the_redhuman_is.forms import WorkerSearchForm

from utils.date_time import date_from_string
from utils.date_time import days_from_interval
from utils.date_time import string_from_date
from the_redhuman_is.views.utils import get_first_last_day
from the_redhuman_is.views.xls_utils import fill_days


@staff_account_required
def list(request):
    deadline = timezone.now().date() - datetime.timedelta(days=7)
    bonuses = models.HostelBonus.objects.filter(
        Q(last_day__isnull=True) | Q(last_day__gte=deadline)
    ).select_related(
        'worker'
    ).annotate(
        full_name=Concat(
            'worker__last_name',
            Value(' '),
            'worker__name',
            Value(' '),
            'worker__patronymic',
            output_field=CharField()
        ),
        last_turnout_customer=Subquery(
            models.WorkerTurnout.objects.filter(
                worker__pk=OuterRef('worker__pk')
            ).order_by(
                'timesheet__sheet_date'
            ).values('timesheet__customer__cust_name')[:1]
        ),
        last_turnout_location=Subquery(
            models.WorkerTurnout.objects.filter(
                worker__pk=OuterRef('worker__pk')
            ).order_by(
                'timesheet__sheet_date'
            ).values('timesheet__cust_location__location_name')[:1]
        )
    ).order_by(
        'full_name'
    )

    return render(
        request,
        'the_redhuman_is/hostel/list.html',
        {
            'worker_form': WorkerSearchForm(),
            'checkin_date_form': SingleDateForm(),
            'checkout_date_form': SingleDateForm(),
            'bonuses': bonuses
        }
    )


@require_POST
@staff_account_required
@transaction.atomic
def set_bonus(request):
    worker_pk = request.POST['worker']
    first_day = date_from_string(request.POST['date'])
    amount = int(request.POST['amount'])

    worker = models.Worker.objects.get(pk=worker_pk)

    open_bonuses = models.HostelBonus.objects.filter(
        Q(last_day__isnull=True) | Q(last_day__gte=first_day),
        worker=worker,
        first_day__lte=first_day,
    )

    if open_bonuses.exists():
        raise Exception(
            '{} уже имеет надбавку на интервале, в который попадает {}'.format(
                worker,
                string_from_date(first_day)
            )
        )

    bonus = models.HostelBonus.objects.create(
        author=request.user,
        worker=worker,
        amount=amount,
        first_day=first_day
    )

    return redirect('the_redhuman_is:hostel_list')


@require_POST
@staff_account_required
@transaction.atomic
def set_bonus_last_day(request):
    bonus_pks = request.POST.getlist('bonus_pk')
    last_day = date_from_string(request.POST['date'])

    bonuses = models.HostelBonus.objects.filter(
        pk__in=bonus_pks
    )
    for bonus in bonuses:
        if bonus.first_day > last_day:
            raise Exception(
                '{}: дата начала действия бонуса ({}) меньше, чем дата окончания ({})'.format(
                    worker,
                    string_from_date(bonus.first_day),
                    string_from_date(last_day)
                )
            )
        bonus.last_day = last_day
        bonus.save()

    return redirect('the_redhuman_is:hostel_list')


@require_POST
@user_passes_test(lambda user: user.is_superuser)
@staff_account_required
@transaction.atomic
def update_all_hostel_bonuses(request):
    workers = models.Worker.objects.filter(
        hostelbonus__isnull=False
    )
    worker_pk = request.POST.get('worker_pk')
    if worker_pk:
        workers = workers.filter(pk=worker_pk)

    for worker in workers:
        for turnout in worker.worker_turnouts.all():
            models.update_hostel_bonus(turnout, request.user)

    return redirect('the_redhuman_is:hostel_list')


def _expenses_report_xls(days, grid, days_sums, total_sum):
    wb = xlwt.Workbook(encoding='utf-8')
    ws = wb.add_sheet('Компенсация проживания', cell_overwrite_ok=True)

    ws.col(0).width = 9100

    font_style = xlwt.XFStyle()
    row = 0
    col = 1
    row, col = fill_days(ws, font_style, row, col, days)

    ws.col(col).width = 2000
    ws.write(row, col, 'Итого', font_style)
    ws.merge(row, row + 1, col, col)

    row = 2

    for worker, operations, row_sum in grid:
        col = 0
        ws.write(row, col, str(worker), font_style)
        col += 1
        for operation in operations:
            if operation:
                ws.write(row, col, operation.amount, font_style)
            col += 1
        ws.write(row, col, row_sum, font_style)

        row += 1

    col = 0
    ws.write(row, col, 'Итого', font_style)
    col += 1
    for day_sum in days_sums:
        ws.write(row, col, day_sum, font_style)
        col += 1

    ws.write(row, col, total_sum, font_style)

    return wb


@staff_account_required
def expenses_report(request):
    first_day, last_day = get_first_last_day(request)
    customer = None
    customer_pk = request.GET.get('customer')
    if customer_pk:
        customer = models.Customer.objects.get(pk=customer_pk)

    turnouts = models.WorkerTurnout.objects.filter(
        hostelbonusoperation__isnull=False,
        timesheet__sheet_date__range=(first_day, last_day)
    )

    if customer:
        turnouts = turnouts.filter(
            timesheet__customer=customer
        )

    workers = models.Worker.objects.filter(
        worker_turnouts__in=turnouts
    ).distinct(
    ).annotate(
        full_name=Concat(
            'last_name',
            Value(' '),
            'name',
            Value(' '),
            'patronymic',
            output_field=CharField()
        ),
    ).order_by(
        'full_name'
    )

    calendar = []

    for worker in workers:
        operations = finance.models.Operation.objects.filter(
            hostelbonusoperation__isnull=False,
            hostelbonusoperation__turnout__worker=worker,
            hostelbonusoperation__turnout__timesheet__sheet_date__range=(
                first_day,
                last_day
            )
        ).annotate(
            sheet_date=F(
                'hostelbonusoperation__turnout__timesheet__sheet_date',
            ),
        )
        operations_dict = {}
        for operation in operations:
            date = operation.sheet_date
            if date in operations_dict:
                raise Exception(
                    'Несколько компенсаций у {} за {}'.format(
                        worker,
                        string_from_date(date)
                    )
                )
            operations_dict[date] = operation

        calendar.append((worker, operations_dict))

    days = days_from_interval(first_day, last_day)
    grid = []
    days_sums = [0 for day in days]
    for worker, operations in calendar:
        row = []
        row_sum = 0
        for i in range(len(days)):
            day = days[i]
            operation = operations.get(day)
            if operation:
                row_sum += operation.amount
                days_sums[i] += operation.amount

            row.append(operation)
        grid.append((worker, row, row_sum))

    total_sum = sum(days_sums)

    if request.GET.get('format') == 'xls':
        response = HttpResponse(content_type='application/vnd.ms-excel')
        response[
            'Content-Disposition'
        ] = "attachment; filename*=UTF-8''hostel_expenses_report.xls"
        xls = _expenses_report_xls(days, grid, days_sums, total_sum)
        xls.save(response)
        return response

    else:
        customer_form = CustomerSelectionForm(
            initial={
                'customer': customer
            }
        )
        customer_form.fields['customer'].required = False

        return render(
            request,
            'the_redhuman_is/hostel/expenses_report.html',
            {
                'first_day': first_day,
                'last_day': last_day,
                'customer': customer_form,
                'customer_form': customer_form,
                'interval_form': DaysIntervalForm(
                    initial={
                        'first_day': first_day,
                        'last_day': last_day
                    }
                ),
                'days': days,
                'grid': grid,
                'days_sums': days_sums,
                'total_sum': total_sum
            }
        )
