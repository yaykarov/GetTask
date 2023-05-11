# -*- coding: utf-8 -*-

import datetime

import xlwt

from django.urls import reverse
from django.db.models import OuterRef
from django.db.models import Subquery
from django.db.models import Sum
from django.http import HttpResponse
from django.shortcuts import render

import finance

from the_redhuman_is import forms
from the_redhuman_is import models

from the_redhuman_is.models.fine_utils import deduction_accounts

from utils.date_time import date_time_from_string
from utils.date_time import string_from_date

from the_redhuman_is.views.utils import get_first_last_day
from the_redhuman_is.views.xls_utils import fill_days


CITIZENSHIP_TYPES = [
    ('russian',     'РФ'),
    ('not_russian', 'Не РФ'),
    ('all',         'Любое'),
]

_CITIZENSHIP_TYPES_DICT = dict(CITIZENSHIP_TYPES)


LAYOUT_TYPES = [
    ('service',           'Разбивка по услугам'),
    ('shift',             'Разбивка по сменам'),
    ('shift_and_service', 'Разбивка и по услугам, и по сменам'),
    ('no_breakdown',      'Без разбивки'),
]

CUSTOMER_FETCH_TYPES = [
    ('include', 'Показать выбранных клиентов'),
    ('exclude', 'Исключить выбранных клиентов'),
]

_LAYOUT_TYPES_DICT = dict(LAYOUT_TYPES)


def _hours(turnout):
    if turnout.hours_worked:
        return float(turnout.hours_worked)
    return 0.0


def _fm_hours(turnout):
    if turnout.hours_worked and turnout.performance:
        return float(turnout.hours_worked * turnout.performance / 100)
    return 0.0


def _turnouts(turnout):
    return 1.0


def _money(turnout, model):
    operations = model.objects.filter(
        turnout=turnout
    )
    if operations.exists():
        return float(
            operations.aggregate(
                amount_sum=Sum('operation__amount')
            )['amount_sum'] or 0
        )

    return 0.0


def _customer_money(turnout):
    return _money(turnout, models.TurnoutCustomerOperation)


def _customer_debt_money(turnout):
    customer = turnout.timesheet.customer
    recs = models.Reconciliation.objects.filter(
        customer=customer,
        is_closed=True
    ).order_by(
        '-last_day'
    )
    if not recs.exists() or turnout.timesheet.sheet_date > recs.first().last_day:
        return _customer_money(turnout)
    return 0


def _customer_fines(turnout):
    return _money(turnout, models.CustomerFine)


def _customer_money_fines(turnout):
    return _customer_money(turnout) - _customer_fines(turnout)


def _worker_money(turnout):
    return _money(turnout, models.TurnoutOperationToPay)


def _worker_deductions(turnout):
    worker = turnout.worker
    timesheet = turnout.timesheet
    worker_deductions = models.WorkerDeduction.objects.filter(
        operation__credit__in=deduction_accounts(timesheet.customer.pk),
        operation__timepoint__date=timesheet.sheet_date,
        operation__debet__worker_account__worker=worker,
    )

    worker_deductions_sum = 0
    if worker_deductions.exists():
        worker_deductions_sum = float(
            worker_deductions.aggregate(
                amount_sum=Sum('operation__amount')
            )['amount_sum'] or 0
        )

    return worker_deductions_sum + _money(turnout, models.TurnoutDeduction)


def _worker_money_fines(turnout):
    return _worker_money(turnout) - _worker_deductions(turnout)


def _margin(turnout):
    return _customer_money(turnout) - _worker_money(turnout)


def _margin_percentage(turnout):
    return _worker_money(turnout), _customer_money(turnout)


def _has_applicant(turnout):
    return hasattr(turnout.worker, 'applicant_link')


def _is_turnout_new_natural(turnout):
    return turnout.is_first() and not _has_applicant(turnout)


def _is_turnout_new_applicant(turnout):
    return turnout.is_first() and _has_applicant(turnout)


def _new_turnouts(turnout):
    if turnout.is_first():
        return 1.0

    return 0.0


def _new_turnouts_natural(turnout):
    if _is_turnout_new_natural(turnout):
        return 1.0

    return 0.0


def _new_applicants(turnout):
    if _is_turnout_new_applicant(turnout):
        return 1.0

    return 0.0


_REPORT_TYPES = [
    ('hours',                'Часы по табелю',         _hours),
    ('fm_hours',             'Часы * пр-ность',        _fm_hours),
    ('turnouts',             'Выходы по табелю',       _turnouts),
    ('turnouts_ordered',     'Выходы по заявке',       None),
    ('noderived',            'Недопоставка',           _turnouts),
    ('unclosed_orders',      'Незакрытые заявки',      None),
    ('customer_money',       'Стоимость услуг',        _customer_money),
    ('customer_debt_money',  'Услуги без актов',       _customer_debt_money),
    ('customer_fines',       'Штрафы',                 _customer_fines),
    ('customer_money_fines', 'Услуги минус штрафы',    _customer_money_fines),
    ('worker_money',         'Затраты на рабочих',     _worker_money),
    ('unpayed_worker_money', 'Долг рабочим',           None),
    ('worker_deductions',    'Вычеты рабочим',         _worker_deductions),
    ('worker_money_fines',   'Рабочие минус вычеты',   _worker_money_fines),
    ('margin',               'Наценка',                _margin),
    ('margin_percentage',    'Наценка в %',            _margin_percentage),
    ('new_turnouts',         'Новые выходы',           _new_turnouts),
    ('new_turnouts_natural', 'Новые без подбора',      _new_turnouts_natural),
    ('new_applicants',       'Новые от подбора',       _new_applicants),
]

SUPERUSERS_ONLY = {
    'customer_debt_money',
    'customer_fines',
    'customer_money',
    'customer_money_fines',
    'margin',
    'margin_percentage',
    'worker_deductions',
}


def _report_types(request):
    types = []
    for item in _REPORT_TYPES:
        type_id, type_name, func = item
        if request.user.is_superuser or type_id not in SUPERUSERS_ONLY:
            types.append(item)
    return types


def _report_type_choices(request):
    return [(type_id, name) for type_id, name, func in _report_types(request)]


_INFO_GETTERS = { type_id: func for type_id, type_name, func in _REPORT_TYPES }


# Todo: share this with other similar forms?
def _get_form_params(request):
    customer_fetch_type = request.GET.get('customer_fetch_type', 'include')

    customers = None
    param_customer_pks = request.GET.getlist('customers')
    if param_customer_pks:
        customers = models.Customer.objects.filter(
            pk__in=param_customer_pks
        )

    manager = None
    param_manager_pk = request.GET.get('manager')
    if param_manager_pk:
        manager = models.Worker.objects.get(pk=int(param_manager_pk))

    first_day, last_day = get_first_last_day(request)

    param_layout_type = request.GET.get('layout_type')
    if param_layout_type not in _LAYOUT_TYPES_DICT.keys():
        param_layout_type = 'no_breakdown'

    param_report_type = request.GET.get('report_type')
    report_types = _report_types(request)
    supported_types = [type_id for type_id, type_name, func in report_types]
    if param_report_type not in supported_types:
        param_report_type = supported_types[0]

    param_citizenship = request.GET.get('citizenship')
    if param_citizenship not in _CITIZENSHIP_TYPES_DICT.keys():
        param_citizenship = 'all'

    return (
        customer_fetch_type,
        customers,
        manager,
        first_day,
        last_day,
        param_layout_type,
        param_report_type,
        param_citizenship
    )


def _make_xls_response(days, column_sums, data, sum_average, sum_overall):
    wb = xlwt.Workbook(encoding='utf-8')
    ws = wb.add_sheet('Сводка по клиентам', cell_overwrite_ok=True)

    font_style = xlwt.XFStyle()
    font_style.font.bold = True

    row_num = 0
    col_num = 0

    ws.col(col_num).width = 15000
    ws.write(row_num, col_num, 'Клиент', font_style)
    ws.merge(row_num, row_num + 1, col_num, col_num)
    col_num += 1

    row_num, col_num = fill_days(ws, font_style, row_num, col_num, days)

    ws.write(row_num, col_num, 'Среднее', font_style)
    ws.merge(row_num, row_num + 1, col_num, col_num)
    col_num += 1

    ws.write(row_num, col_num, 'Итого', font_style)
    ws.merge(row_num, row_num + 1, col_num, col_num)

    row_num += 2

    for location, row_name, row, row_average, row_sum in data:
        col_num = 0
        ws.write(row_num, col_num, row_name, font_style)
        col_num += 1
        for value, url in row:
            ws.write(row_num, col_num, value, font_style)
            col_num += 1
        ws.write(row_num, col_num, row_average, font_style)
        col_num += 1
        ws.write(row_num, col_num, row_sum, font_style)
        row_num += 1

    col_num = 0
    ws.write(row_num, col_num, 'Итого', font_style)
    col_num += 1
    for value in column_sums:
        ws.write(row_num, col_num, value, font_style)
        col_num += 1
    ws.write(row_num, col_num, sum_average, font_style)
    col_num += 1
    ws.write(row_num, col_num, sum_overall, font_style)

    response = HttpResponse(
        content_type='application/vnd.ms-excel'
    )
    response[
        'Content-Disposition'
    ] = "attachment; filename*=UTF-8''summary.xls"
    wb.save(response)
    return response


def report(request):
    from the_redhuman_is.models.paysheet_v2 import _saldo

    (
        customer_fetch_type,
        customers,
        manager,
        first_day,
        last_day,
        layout_type,
        report_type,
        citizenship
    ) = _get_form_params(request)

    if report_type == 'unpayed_worker_money':
        layout_type = 'no_breakdown'

    orders = models.CustomerOrder.objects.filter(
        on_date__gte=first_day,
        on_date__lte=last_day,
    ).distinct()

    user_groups = request.user.groups.values_list('name', flat=True)
    if 'Менеджеры' in user_groups:
        orders = orders.filter(
            customer__maintenancemanager__worker__workeruser__user=request.user
        )

    if customers:
        if customer_fetch_type == 'include':
            orders = orders.filter(
                customer__in=customers
            )
        elif customer_fetch_type == 'exclude':
            orders = orders.exclude(
                customer__in=customers
            )

    if manager:
        orders = orders.filter(
            customer__maintenancemanager__worker=manager
        )

    locations_dict = orders.values('cust_location').distinct()
    locations = models.CustomerLocation.objects.filter(
        pk__in=[l['cust_location'] for l in locations_dict]
    )

    workers = models.Worker.objects.filter(
        worker_turnouts__timesheet__customerorder__in=orders
    ).distinct(
    ).annotate(
        last_location=Subquery(
            models.TimeSheet.objects.filter(
                worker_turnouts__worker__pk=OuterRef('pk')
            ).order_by(
                '-sheet_date'
            ).values('cust_location')[:1]
        ),
    )
    workers_locations = {}

    def _fill_workers_locations():
        for worker in workers:
            location = worker.last_location
            if location not in workers_locations:
                workers_locations[location] = []
            workers_locations[location].append(worker)

    days = [
        first_day + datetime.timedelta(days=d) for d in range(0, (last_day-first_day).days + 1)
    ]

    def _filter_turnouts(order):
        try:
            timesheet = models.TimeSheet.objects.get(customerorder=order)
        except models.TimeSheet.DoesNotExist:
            turnouts = models.WorkerTurnout.objects.none()
        else:
            turnouts = timesheet.worker_turnouts.all()
            if report_type in ['new_turnouts', 'new_turnouts_natural', 'new_applicants']:
                if citizenship == 'russian':
                    turnouts = turnouts.filter(
                        worker__citizenship__name='РФ',
                    )
                elif citizenship == 'not_russian':
                    turnouts = turnouts.exclude(
                        worker__citizenship__name='РФ',
                    )
        return turnouts.select_related('timesheet')

    if report_type == 'margin_percentage':
        column_sums = [(0.0, 0.0) for day in days]
    else:
        column_sums = [0.0 for day in days]
    data = []

    def _url(location, day, shift, service):
        uri = request.build_absolute_uri(
            reverse(
                'the_redhuman_is:report_customer_summary_details',
                kwargs={
                    'location_pk': location.pk,
                    'date': string_from_date(day),
                    'shift': shift or '-',
                    'report_type': report_type
                }
            )
        )
        if service:
            uri += '?service={}'.format(service.service.pk)
        return uri

    def _add(t1, t2):
        if isinstance(t1, tuple):
            return tuple([sum(x) for x in zip(t1, t2)])
        else:
            return t1 + t2

    turnout_value_getter = _INFO_GETTERS[report_type]

    def _day_value(day, location, shift, service):
        if report_type == 'margin_percentage':
            day_value = (0.0, 0.0)
        else:
            day_value = 0.0
        day_orders = orders.filter(
            on_date=day,
            cust_location=location,
        )
        if shift:
            day_orders = day_orders.filter(
                bid_turn=shift
            )
        for order in day_orders:
            if report_type == 'turnouts_ordered':
                day_value += order.number_of_workers
            elif report_type == 'unclosed_orders':
                if not models.TimeSheet.objects.filter(customerorder=order).exists():
                    day_value += order.number_of_workers
            elif report_type == 'unpayed_worker_money':
                if not workers_locations:
                    _fill_workers_locations()
                ws = workers_locations.get(location.pk, [])
                debit_operations = finance.models.Operation.objects.filter(
                    paysheet_entry_operation__isnull=True,
                    paysheet_v2_operation__isnull=True,
                    timepoint__date=day,
                    debet__worker_account__worker__in=ws,
                )
                credit_operations = finance.models.Operation.objects.filter(
                    paysheet_entry_operation__isnull=True,
                    paysheet_v2_operation__isnull=True,
                    timepoint__date=day,
                    credit__worker_account__worker__in=ws,
                )
                return float(_saldo(debit_operations, credit_operations))
            else:
                turnouts = _filter_turnouts(order)
                if service:
                    turnouts = turnouts.filter(
                        turnoutservice__customer_service=service
                    ).distinct()
                for turnout in turnouts:
                    day_value = _add(day_value, turnout_value_getter(turnout))
            if report_type == 'noderived':
                day_value -= order.number_of_workers
        if report_type == 'noderived':
            day_value = max(0, -day_value)

        return day_value

    def _do_fill_data(items):
        for location, shift, service in items:
            row_name = '{} {}'.format(
                location.customer_id,
                location.location_name,
            )
            if service:
                row_name += ' - {}'.format(service.service.name)
            if shift:
                row_name += ' - {}'.format(shift)

            if report_type == 'margin_percentage':
                row_sum = (0.0, 0.0)
            else:
                row_sum = 0.0
            row = []
            for i in range(len(days)):
                day = days[i]
                day_value = _day_value(
                    day,
                    location,
                    shift,
                    service
                )

                row_sum = _add(row_sum, day_value)
                column_sums[i] = _add(column_sums[i], day_value)
                if day_value == 0:
                    day_value = ''
                row.append(
                    (day_value, _url(location, day, shift, service))
                )

            if report_type == 'margin_percentage':
                data.append((location, row_name, row, row_sum))
            else:
                data.append((location, row_name, row, row_sum / len(days), row_sum))

    def _fill_data(shift, service):
        def _items(shift, service):
            if shift:
                shifts = ['День', 'Ночь']
            else:
                shifts = [None]
            for location in locations:
                if service:
                    services = list(
                        models.CustomerService.objects.filter(
                            customer=location.customer_id
                        )
                    )
                else:
                    services = [None]
                for service in services:
                    for shift in shifts:
                        yield location, shift, service

        _do_fill_data(_items(shift, service))

    _filling_params = {
        'no_breakdown':      (False, False),
        'shift':             (True, False),
        'service':           (False, True),
        'shift_and_service': (True, True)
    }

    shift, service = _filling_params[layout_type]
    _fill_data(shift, service)

    def _percentage(value):
        worker, customer = value
        if customer > 0:
            return 100.0 * (customer - worker) / customer
        else:
            return 0.0

    if report_type == 'margin_percentage':
        sum_overall = (0.0, 0.0)
        for value in column_sums:
            sum_overall = _add(sum_overall, value)

        # postprocessing
        sum_overall = _percentage(sum_overall)

        column_sums = [_percentage(x) for x in column_sums]

        def _postprocess(item):
            location, name, row, row_sum = item
            row_sum = _percentage(row_sum)
            row = [(_percentage(value), url) for value, url in row]
            return location, name, row, row_sum, row_sum

        data = [_postprocess(item) for item in data]

        sum_average = sum_overall

    else:
        sum_overall = sum(column_sums)
        sum_average = sum_overall / len(days)

    if request.GET.get('format') == 'xls':
        return _make_xls_response(days, column_sums, data, sum_average, sum_overall)
    else:
        return render(
            request,
            'the_redhuman_is/reports/customer_summary.html',
            {
                'report_type': report_type,
                'filter_form': forms.CustomerSummaryReportFilter(
                    _report_type_choices(request),
                    initial={
                        'customer_fetch_type': customer_fetch_type,
                        'customers': [c.pk for c in customers] if customers else [],
                        'manager': manager,
                        'first_day': first_day,
                        'last_day': last_day,
                        'layout_type': layout_type,
                        'report_type': report_type,
                        'citizenship': citizenship,
                    }
                ),
                'days': days,
                'column_sums': column_sums,
                'data': data,
                'sum_average': sum_average,
                'sum_overall': sum_overall
            }
        )


def details(request, location_pk, date, shift, report_type):
    location_pk = int(location_pk)

    day = date_time_from_string(date)
    orders = models.CustomerOrder.objects.filter(
        on_date=day,
    )

    location = None
    if location_pk != 0:
        location = models.CustomerLocation.objects.get(pk=location_pk)
        orders = orders.filter(
            cust_location=location,
        )

    service_pk = request.GET.get('service')
    if shift != '-':
        orders = orders.filter(
            bid_turn=shift
        )

    citizenship = request.GET.get('citizenship')

    result = []

    for order in orders:
        timesheets = models.TimeSheet.objects.filter(customerorder=order)
        if timesheets:
            timesheet = timesheets.get()
            turnouts = timesheet.worker_turnouts.all()
            if service_pk:
                turnouts = turnouts.filter(
                    turnoutservice__customer_service__service__pk=service_pk
                )
            if citizenship == 'russian':
                turnouts = turnouts.filter(
                    worker__citizenship__name='РФ'
                )
            if citizenship == 'not_russian':
                turnouts = turnouts.exclude(
                    worker__citizenship__name='РФ'
                )

            for turnout in turnouts:
                if report_type == 'new_turnouts':
                    if turnout.is_first():
                        result.append(turnout)
                elif report_type == 'new_turnouts_natural':
                    if _is_turnout_new_natural(turnout):
                        result.append(turnout)
                elif report_type == 'new_applicants':
                    if _is_turnout_new_applicant(turnout):
                        source_pk = request.GET.get('source')
                        if source_pk:
                            source_pk = int(source_pk)
                        manager_pk = request.GET.get('manager')
                        if manager_pk:
                            manager_pk = int(manager_pk)
                        applicant = turnout.worker.applicant_link.applicant
                        if ((not source_pk or source_pk == applicant.source.pk) and
                                (not manager_pk or manager_pk == applicant.author.pk)):
                            result.append(turnout)
                elif report_type == 'worker_deductions':
                    if _worker_deductions(turnout) > 0:
                        result.append(turnout)
                elif report_type == 'customer_fines':
                    if _customer_fines(turnout) > 0:
                        result.append(turnout)
                else:
                    result.append(turnout)

    return render(
        request,
        'the_redhuman_is/reports/turnouts_list.html',
        {
            'location': location,
            'day': day,
            'turnouts': result,
        }
    )
