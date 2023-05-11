# -*- coding: utf-8 -*-

import datetime
import decimal
import re
import xlrd
import xlwt

from django.forms import CharField
from django.forms import widgets

from django.db import transaction

from django.db.models import OuterRef
from django.db.models import Q
from django.db.models import Subquery
from django.db.models import Sum

from django.shortcuts import redirect
from django.shortcuts import render

from django.http import HttpResponse
from django.http import JsonResponse

from django.views.decorators.http import require_POST

from django.utils import timezone

import finance

from the_redhuman_is.auth import staff_account_required

from the_redhuman_is import forms
from the_redhuman_is import models

from the_redhuman_is.views.utils import get_first_last_day
from utils.date_time import days_from_interval
from utils.date_time import string_from_date


YEAR = timezone.now().date().year
VKUSVILL_PK = 16
VKUSVILL_SERVICE_PK = 8

WAREHOUSES = {
    'ТИЛСИ': 'Молоко',
    'Кавказский': 'Молоко',
    'Склад_Сухой': 'Молоко',
    'Склад долгосрочной продукции': 'Долгосрок',
    'Склад_Хлеба': 'Хлеб',
    'Склад_Овощи_Фрукты': 'Овощи',
    'Склад_Охл_Мясо': 'Мясо',
    'Зона отгрузки заморозки': 'Заморозка'
}


@staff_account_required
def management_page(request):
    return render(
        request,
        'the_redhuman_is/vkusvill/management_page.html',
        {
            'filter_form': forms.DaysIntervalForm()
        }
    )


def _parse_performance_sheet(sheet):
    name = sheet.name
    day = int(name[:2])
    month = int(name[3:5])
    day = datetime.date(
        day=day,
        month=month,
        year=YEAR
    )

    A_RX = re.compile('^([AА]\d+.*)$')

    state = 'initial'
    level = None
    terminal = None

    result = {}
    errors = []

    for row in range(0, sheet.nrows):
        value = sheet.cell_value(row, 0)
        m = A_RX.match(value)
        if m:
            state = 'new_terminal'
            terminal = m.group(1)
        elif value in ['С пересчетом', 'Без пересчета']:
            if terminal:
                state = 'new_warehouse'
                level = sheet.rowinfo_map[row + 1].outline_level
            else:
                errors.append(
                    'Лист {}, строка {}: значение <{}> до того, как был указан терминал'.format(
                        string_from_date(day),
                        row,
                        value
                    )
                )
        elif state == 'new_warehouse':
            if sheet.rowinfo_map[row].outline_level == level:
                errors_more = int(sheet.cell_value(row, 1) or 0)
                errors_less = int(sheet.cell_value(row, 2) or 0)
                performance = int(sheet.cell_value(row, 3) or 0)
                if terminal not in result:
                    result[terminal] = {}
                terminal_data = result[terminal]
                box_type = WAREHOUSES[sheet.cell_value(row, 0)] # warehouse
                if box_type in terminal_data:
                    (
                        prev_errors_more,
                        prev_errors_less,
                        prev_performance
                    ) = terminal_data[box_type]
                    terminal_data[box_type] = (
                        errors_more + prev_errors_more,
                        errors_less + prev_errors_less,
                        performance + prev_performance
                    )
                else:
                    terminal_data[box_type] = (
                        errors_more,
                        errors_less,
                        performance
                    )
            elif sheet.rowinfo_map[row].outline_level < level:
                state = 'initial'

    return day, result, errors


def _parse_performance_book(book):
    result = {}
    errors = {}
    for sheet in book.sheets():
        day, data, sheet_errors = _parse_performance_sheet(sheet)
        if day in result:
            raise Exception(
                'Неподдерживаемый формат: в файле несколько листов с датой {}.'.format(
                    string_from_date(day)
                )
            )
        result[day] = data
        if sheet_errors:
            errors[string_from_date(day)] = sheet_errors

    return result, errors


# Todo: deprecated? remove?
def _get_output_difference(data):
    grid = {}

    output_indices = {}

    for day, info in data.items():
        turnouts = models.WorkerTurnout.objects.filter(
            timesheet__customer__pk=VKUSVILL_PK,
            timesheet__sheet_date=day,
            turnoutservice__customer_service__service__pk=VKUSVILL_SERVICE_PK
        ).select_related(
            'timesheet'
        )

        for turnout in turnouts:
            current_output = {}
            for item in models.TurnoutOutput.objects.filter(turnout=turnout):
                name = item.box_type.name
                if name in current_output:
                    raise Exception('Multiple outputs with the same name are unsupported')
                current_output[name] = item.amount

            day_data = data[turnout.timesheet.sheet_date]
            code_name = turnout.worker_code_name
            xls_output = day_data.get(code_name, {})

            output_difference = {}

            for box_type_name, values in xls_output.items():
                (errors_more, errors_less, performance) = values
                output_difference[
                    box_type_name
                ] = performance - current_output.get(box_type_name, 0)

            for name, amount in current_output.items():
                if name not in output_difference:
                    output_difference[name] = -amount

            for k, v in output_difference.items():
                if k not in output_indices:
                    output_indices[k] = len(output_indices) + 1

                if v != 0:
                    worker_name = str(turnout.worker)
                    if worker_name not in grid:
                        grid[worker_name] = {}

                    if turnout.timesheet.sheet_date in grid[worker_name]:
                        raise Exception('Multiple turnouts at same day and same worker')

                    grid[worker_name][
                        turnout.timesheet.sheet_date
                    ] = output_difference
                    break

    wb = xlwt.Workbook(encoding='utf-8')
    style = xlwt.XFStyle()

    for day, info in data.items():
        ws = wb.add_sheet(string_from_date(day), cell_overwrite_ok=True)
        for output_name, index in output_indices.items():
            ws.write(0, index, output_name, style)
        row_num = 1
        for worker_name, data in grid.items():
            if day in data:
                ws.write(row_num, 0, worker_name, style)
                for output_name, amount in data[day].items():
                    ws.write(row_num, output_indices[output_name], amount, style)
                row_num += 1

    response = HttpResponse(content_type='application/vnd.ms-excel')
    response[
        'Content-Disposition'
    ] = "attachment; filename*=UTF-8''" + 'output_difference.xls'
    wb.save(response)

    return response


@staff_account_required
def performance_file_report(request, pk):
    performance_file = models.PerformanceFile.objects.get(pk=pk)

    book = xlrd.open_workbook(
        file_contents=performance_file.data_file.read(),
        formatting_info=True
    )

    data, errors = _parse_performance_book(book)

    not_in_xls = []
    not_in_turnouts = []

    for day, info in data.items():
        turnouts = models.WorkerTurnout.objects.filter(
            timesheet__customer__pk=VKUSVILL_PK,
            timesheet__sheet_date=day,
            turnoutservice__customer_service__service__pk=VKUSVILL_SERVICE_PK
        ).select_related(
            'timesheet'
        )

        turnout_codes = []

        for turnout in turnouts:
            code_name = turnout.worker_code_name
            turnout_codes.append(code_name)

            if code_name not in info.keys():
                timesheets = models.TimeSheet.objects.filter(
                    customer__pk=VKUSVILL_PK,
                    worker_turnouts__worker_code_name=code_name,
                    sheet_date=day
                ).select_related(
                    'customer',
                    'cust_location'
                ).distinct()
                not_in_xls.append((code_name, timesheets))

        for code_name in info.keys():
            if code_name not in turnout_codes:
                not_in_turnouts.append((day, code_name))

    return render(
        request,
        'the_redhuman_is/vkusvill/performance_file_check_result.html',
        {
            'performance_file_pk': performance_file.pk,
            'format_errors': errors,
            'not_in_xls': not_in_xls,
            'not_in_turnouts': not_in_turnouts
        }
    )


@require_POST
@staff_account_required
def save_and_check_performance_file(request):
    pf = request.FILES['performance']
    performance_file = models.vkusvill.create_performance_file(
        request.user,
        pf
    )

    return redirect('the_redhuman_is:vkusvill_performance_file_report', pk=performance_file.pk)


@require_POST
@staff_account_required
@transaction.atomic
def import_performance_file(request, pk):
    performance_file = models.PerformanceFile.objects.get(pk=pk)

    book = xlrd.open_workbook(
        file_contents=performance_file.data_file.read(),
        formatting_info=True
    )

    data, errors = _parse_performance_book(book)

    turnouts = models.WorkerTurnout.objects.filter(
        timesheet__customer__pk=VKUSVILL_PK,
        timesheet__sheet_date__in=data.keys(),
        turnoutservice__customer_service__service__pk=VKUSVILL_SERVICE_PK
    ).select_related(
        'timesheet'
    )

    for turnout in turnouts:
        code_name = turnout.worker_code_name
        day_data = data[turnout.timesheet.sheet_date]
        output = day_data.get(code_name, {})
        # Не хочется обнулять сразу всю выработку, на случай, если есть
        # внесенные вручную данные, которых почему-то нет в xls
        if output:
            current_output = models.TurnoutOutput.objects.filter(
                turnout=turnout
            )
            current_output.update(amount=0)

        for box_type_name, values in output.items():
            (errors_more, errors_less, performance) = values

            box_type = models.BoxType.objects.get(
                name=box_type_name,
                customer__pk=VKUSVILL_PK
            )
            models.set_turnout_output(
                turnout,
                box_type,
                performance,
                errors_more + errors_less
            )

    performance_file.on_import_complete()

    return redirect('the_redhuman_is:vkusvill_management_page')


# returns dict with (performance, total_revenue, fine_percentage)
def _parse_errors(sheet):
    A_RX = re.compile('^([AА]\d+.*)$')

    result = {}

    for row in range(0, sheet.nrows):
        value = sheet.cell_value(row, 0)
        m = A_RX.match(value)
        if m:
            result[value] = (
                sheet.cell_value(row, 4) or 0,
                sheet.cell_value(row, 6) or 0,
                sheet.cell_value(row, 1) or 0
            )

    return result


@staff_account_required
def errors_file_report(request, pk):
    errors_file = models.ErrorsFile.objects.get(pk=pk)

    errors_book = xlrd.open_workbook(
        file_contents=errors_file.data_file.read(),
    )

    errors_info = _parse_errors(errors_book.sheet_by_index(0))

    amounts = {}

    for code, value in errors_info.items():
        total_output, xls_amount, fine_percentage = value

        turnouts = models.WorkerTurnout.objects.filter(
            timesheet__customer__pk=VKUSVILL_PK,
            timesheet__sheet_date__gte=errors_file.first_day,
            timesheet__sheet_date__lte=errors_file.last_day,
            turnoutservice__customer_service__service__pk=VKUSVILL_SERVICE_PK,
            worker_code_name=code
        )

        real_amount = turnouts.aggregate(
            amount=Sum('turnoutcustomeroperation__operation__amount')
        ).get('amount') or 0

        real_fine = real_amount * decimal.Decimal(fine_percentage) / decimal.Decimal(100)

        amounts[code] = (
            # Выручка по нашим данным
            real_amount,
            # Ставка штрафа в файле
            fine_percentage,
            # Сумма штрафа
            real_fine,
            # Выручка с учетом штрафа
            real_amount - real_fine,
            # Выручка в файле
            xls_amount,
            # Выручка в файле - по нашим данным
            decimal.Decimal(xls_amount) - real_amount + real_fine
        )

    return render(
        request,
        'the_redhuman_is/vkusvill/errors_file_report.html',
        {
            'errors_file': errors_file,
            'data': amounts
        }
    )


@staff_account_required
def errors_files_list(request):
    return render(
        request,
        'the_redhuman_is/vkusvill/errors_files_list.html',
        {
            'files': models.ErrorsFile.objects.all().order_by('-timestamp')
        }
    )


@staff_account_required
def save_and_check_errors_file(request):
    first_day, last_day = get_first_last_day(request)
    ef = request.FILES['errors']
    errors_file = models.vkusvill.create_errors_file(
        request.user,
        ef,
        first_day,
        last_day
    )

    return redirect(
        'the_redhuman_is:vkusvill_errors_file_report',
        pk=errors_file.pk
    )


@require_POST
@staff_account_required
@transaction.atomic
def import_errors_file(request, pk):
    errors_file = models.vkusvill.ErrorsFile.objects.get(pk=pk)

    customer_account = models.CustomerOperatingAccounts.objects.get(
        customer__pk=VKUSVILL_PK
    )

    errors_book = xlrd.open_workbook(
        file_contents=errors_file.data_file.read(),
    )

    errors_info = _parse_errors(errors_book.sheet_by_index(0))

    fines = []

    for code, value in errors_info.items():
        total_output, xls_amount, fine_percentage = value

        turnouts = models.WorkerTurnout.objects.filter(
            timesheet__customer__pk=VKUSVILL_PK,
            timesheet__sheet_date__gte=errors_file.first_day,
            timesheet__sheet_date__lte=errors_file.last_day,
            turnoutservice__customer_service__service__pk=VKUSVILL_SERVICE_PK,
            worker_code_name=code
        ).select_related(
            'timesheet'
        ).annotate(
            revenue=Subquery(
                finance.models.Operation.objects.filter(
                    turnoutcustomeroperation__turnout__pk=OuterRef('pk')
                ).values('amount')
            )
        )

        for turnout in turnouts:
            fine_amount = (
                turnout.revenue *
                decimal.Decimal(fine_percentage) /
                decimal.Decimal(100)
            )
            fine = {
                'worker': turnout.worker,
                'turnout': turnout,
                'date': turnout.timesheet.sheet_date,
                'fine': fine_amount,
                'deduction': fine_amount / decimal.Decimal(1.2),
                'comment': 'Пересорт, терминал {}, {}'.format(
                    code,
                    string_from_date(turnout.timesheet.sheet_date)
                )
            }
            fines.append(fine)

    models.fine_utils.create_fines(
        request.user,
        VKUSVILL_PK,
        None,
        fines,
        'Вкусвилл - пересорт c {} по {}'.format(
            string_from_date(errors_file.first_day),
            string_from_date(errors_file.last_day)
        )
    )

    errors_file.on_import_complete()

    return redirect(
        'the_redhuman_is:vkusvill_errors_file_report',
        pk=errors_file.pk
    )


def _code_name(turnout):
    return turnout.worker_code_name


def _errors(turnout):
    return turnout.errors


_REPORT_TYPES = [
    ('terminals', 'Терминалы', _code_name),
    ('performance', 'Выработка', None),
    ('errors', 'Пересорт', _errors),
]


def _report_choices():
    return [(type_id, name) for type_id, name, func in _REPORT_TYPES]


_INFO_GETTERS = { type_id: func for type_id, name, func in _REPORT_TYPES }


class PerformanceReportFilter(forms.DaysIntervalForm):
    report_type = CharField(
        label='Вариант отчета',
        widget=widgets.Select(
            choices=_report_choices(),
            attrs={
                'class': 'form-control form-control-sm',
                'style': 'max-width: 140px;'
            }
        )
    )


def _xls_performance_report(days, grid):
    output_indices = {}

    for worker, data in grid.items():
        for output_name, cells in data.items():
            if output_name not in output_indices:
                output_indices[output_name] = len(output_indices)

    wb = xlwt.Workbook(encoding='utf-8')
    style = xlwt.XFStyle()

    weekdays = ['пн', 'вт', 'ср', 'чт', 'пт', 'сб', 'вс']

    sheets = []
    for k, v in output_indices.items():
        if k is None:
            name = 'Sheet'
        else:
            name = k
        ws = wb.add_sheet(name, cell_overwrite_ok=True)
        ws.col(0).width = 10000
        col_num = 1
        for day in days:
            ws.write(0, col_num, day.strftime('%d.%m'), style)
            ws.write(1, col_num, weekdays[day.weekday()], style)
            col_num += 1
        sheets.append(ws)

    row_nums = [2 for i in range(len(sheets))]

    for worker, data in grid.items():
        for output_name, cells in data.items():
            sheet_index = output_indices[output_name]
            sheet = sheets[sheet_index]
            col_num = 0
            sheet.write(row_nums[sheet_index], col_num, str(worker), style)
            col_num += 1
            for cell in cells:
                if cell is not None:
                    sheet.write(row_nums[sheet_index], col_num, cell, style)
                col_num += 1
            row_nums[sheet_index] += 1

    response = HttpResponse(content_type='application/vnd.ms-excel')
    response[
        'Content-Disposition'
    ] = "attachment; filename*=UTF-8''" + 'vkusvill_info.xls'
    wb.save(response)

    return response


@staff_account_required
def performance_report(request):
    first_day, last_day = get_first_last_day(request)
    days = days_from_interval(first_day, last_day)
    report_type = request.GET.get('report_type', 'terminals')

    grid = {}

    turnouts = models.WorkerTurnout.objects.filter(
        timesheet__customer__pk=VKUSVILL_PK,
        timesheet__sheet_date__gte=first_day,
        timesheet__sheet_date__lte=last_day,
        turnoutservice__customer_service__service__pk=VKUSVILL_SERVICE_PK,
    ).select_related(
        'worker',
        'timesheet'
    ).prefetch_related(
        'output',
        'output__box_type',
    ).annotate(
        errors=Subquery(
            finance.models.Operation.objects.filter(
                turnoutdeduction__turnout=OuterRef('pk'),
                comment__icontains='Пересорт'
            ).values(
                'amount'
            )
        )
    ).order_by(
        'worker'
    )

    func = _INFO_GETTERS[report_type]

    def _add(worker, output_name, day, value):
        if worker not in grid:
            grid[worker] = {}

        worker_data = grid[worker]
        if output_name not in worker_data:
            worker_data[output_name] = [None for i in range(len(days))]

        day_index = (day - first_day).days
        row = worker_data[output_name]
        if row[day_index]:
            row[day_index] = '{}/{}'.format(row[day_index], value)
        else:
            row[day_index] = value

    for turnout in turnouts:
        worker = turnout.worker
        day = turnout.timesheet.sheet_date

        if report_type == 'performance':
            for output in turnout.output.all():
                if output.amount != 0:
                    _add(worker, output.box_type.name, day, output.amount)
        else:
            _add(worker, None, day, func(turnout))

    if request.GET.get('format') == 'xls':
        return _xls_performance_report(days, grid)

    return render(
        request,
        'the_redhuman_is/vkusvill/performance_report.html',
        {
            'filter_form': PerformanceReportFilter(
                initial={
                    'first_day': first_day,
                    'last_day': last_day,
                    'report_type': report_type,
                }
            ),
            'days': days,
            'grid': grid
        }
    )


_NEW_CODES = {
    'Усон Уулу Кутманбек': 'А1(Овощи)',
    'Кенеш Уулу Талгатбек': 'А2(Овощи)',
    'Жанышбек Уулу Нурсултан': 'А3(Овощи)',
    'Даткабек Уулу Талгат': 'А4(Овощи)',
    'Каграманян Эрик Аратович': 'А5(Овощи)',
    'Батырбеков Калыбек Батырбекович': 'А6(Овощи)',
    'Карыев Адилет Жыргалбекович': 'А7(Овощи)',
    # 'Жунушбаев Нурбек Турарбекович': 'А8(Овощи)',
    'Жамалидин Уулу Арген': 'А9(Овощи)',
    'Дуйшенбай Уулу Элдар': 'А10(Овощи)',
    'Рахатбек Уулу Манас': 'А11(Овощи)',
    'Кенжеев Улукбек Муртазакулович': 'А12(Овощи)',
    'Нурдин Уулу Эдилбек': 'А13(Овощи)',
    'Турдукулов Орозали': 'А14(Овощи)',
    'Темир Уулу Толонбай': 'А15(Овощи)',
    'Молдобеков Азамат Тойболотович': 'А16(Овощи)',
    'Сейдакматов Арген Рахатбекович': 'А17(Овощи)',
    'Кудайбердиев Бекмырза Анарбаевич': 'А18(Овощи)',
    'Касымжан Уулу Сталбек': 'А19(Овощи)',
    'Шамшыдинов Талыпжан': 'А20(Овощи)',
    'Маматкадыров Талгат Кубанычбекович': 'А1(МО;Х;ДП;М)',
    'Каныев Дастан Русланович': 'А2(МО;Х;ДП;М)',
    'Байгазиев Маратбек Элчибекович': 'А3(МО;Х;ДП;М)',
    'Сокучу Уулу Улукбек': 'А4(МО;Х;ДП;М)',
    'Мамытбек Уулу Темирлан': 'А5(МО;Х;ДП;М)',
    'Сыныбек Уулу Тынчтыкбек': 'А10(МО;Х;ДП;М)',
    'Токтомушов Таирбек Жоомартович': 'А11(МО;Х;ДП;М)',
    'Абдрашитов Алтын': 'А12(МО;Х;ДП;М)',
    'Абдиллаев Мухаммедали Абдыгапарович': 'А13(МО;Х;ДП;М)',
    'Мелисбек Уулу Арген': 'А14(МО;Х;ДП;М)',
    'Шадыканов Болсунбек Анарбекович': 'А15(МО;Х;ДП;М)',
    'Таирбек Уулу Иса': 'А16(МО;Х;ДП;М)',
    'Маликов Талант Маликович': 'А17(МО;Х;ДП;М)',
    'Инамжан Уулу Максат': 'А18(МО;Х;ДП;М)',
    'Гулжигит Уулу Эрлан': 'А1(Х;ДП;М;МО)',
    'Исабек Уулу Артур': 'А2(Х;ДП;М;МО)',
    'Жуманазаров Нурбек': 'А3(Х;ДП;М;МО)',
    'Абдикаримов Нурмухамед Асхатович': 'А4(Х;ДП;М;МО)',
    'Арзибек Уулу Самат': 'А5(Х;ДП;М;МО)',
    'Савралимов Болотбек': 'А6(Х;ДП;М;МО)',
    'Рысбаев Акжол': 'А7(Х;ДП;М;МО)',
    'Алмазбек Уулу Элмурат': 'А8(Х;ДП;М;МО)',
    'Каныбек Уулу Азамат': 'А9(Х;ДП;М;МО)',
    'Кылычов Шайлообек': 'А10(Х;ДП;М;МО)',
    'Жунушбаев Нурбек Турарбекович': 'А11(Х;ДП;М;МО)',
    'Кабылов Дастан': 'А12(Х;ДП;М;МО)',
    'Руслан Уулу Актан': 'А13(Х;ДП;М;МО)',
    'Манасов Муслимбек': 'А1(М;Х;ДП;МО)',
    'Нусуп Уулу Омурбек': 'А2(М;Х;ДП;МО)',
    'Сакиев Тилек': 'А3(М;Х;ДП;МО)',
    'Кантемир Уулу Жумадил': 'А4(М;Х;ДП;МО)',
    'Эркиналы Уулу Рысбек': 'А5(М;Х;ДП;МО)',
    'Бакиров Уланбек': 'А6(М;Х;ДП;МО)',
    'Нурланбек Уулу Бакыт 254': 'А7(М;Х;ДП;МО)',
    'Бегали Уулу Канатбек': 'А8(М;Х;ДП;МО)',
    'Джуманов Жаныбек Болотбекович': 'А9(М;Х;ДП;МО)',
    'Азинбай Уулу Асылбек': 'А10(М;Х;ДП;МО)',
    # 'Жуманазаров Нурбек ': 'А15(М;Х;ДП;МО)',
}

_KNOWN_CODES = {
    'А1': 'А1(МО;Х;ДП;М)',
    'А10': 'А10(МО;Х;ДП;М)',
    'А11': 'А11(МО;Х;ДП;М)',
    'А12': 'А12(МО;Х;ДП;М)',
    'А14': 'А14(МО;Х;ДП;М)',
    'А15': 'А15(МО;Х;ДП;М)',
    'А16': 'А16(МО;Х;ДП;М)',
    'А17': 'А17(МО;Х;ДП;М)',
    'А18': 'А18(МО;Х;ДП;М)',
    'А19': 'А19(МО;Х;ДП;М)',
    'А2': 'А2(МО;Х;ДП;М)',
    'А20': 'А20(МО;Х;ДП;М)',
    'А21': 'А21(МО;Х;ДП;М)',
    'А22': 'А22(МО;Х;ДП;М)',
    'А24': 'А24(МО;Х;ДП;М)',
    'А25': 'А25(МО;Х;ДП;М)',
    'А26': 'А26(МО;Х;ДП;М)',
    'А27': 'А27(МО;Х;ДП;М)',
    'А29': 'А29(МО;Х;ДП;М)',
    'А30': 'А30(МО;Х;ДП;М)',
    'А31': 'А31(МО;Х;ДП;М)',
    'А34': 'А34(МО;Х;ДП;М)',
    'А35': 'А35(МО;Х;ДП;М)',
    'А36': 'А36(МО;Х;ДП;М)',
    'А39': 'А39(МО;Х;ДП;М)',
    # 'А4': 'А4(МО;Х;ДП;М)',
    'А40': 'А40(МО;Х;ДП;М)',
    'А41': 'А41(МО;Х;ДП;М)',
    'А42': 'А42(МО;Х;ДП;М)',
    'А45': 'А45(МО;Х;ДП;М)',
    'А47': 'А47(МО;Х;ДП;М)',
    # 'А49': 'А45(МО;Х;ДП;М)',
    'А5': 'А5(МО;Х;ДП;М)',
    'А51': 'А1(Х;ДП;М;МО)',
    'А53': 'А3(Х;ДП;М;МО)',
    'А54': 'А4(Х;ДП;М;МО)',
    'А56': 'А6(Х;ДП;М;МО)',
    'А59': 'А9(Х;ДП;М;МО)',
    'А6': 'А6',
    'А61': 'А11(Х;ДП;М;МО)',
    'А65': 'А15(Х;ДП;М;МО)',
    'А7': 'А7',
    'А23': 'А23(МО;Х;ДП;М)',
    'А3': 'А3(МО;Х;ДП;М)',
    'А33': 'А33(МО;Х;ДП;М)',
    'А37': 'А37(МО;Х;ДП;М)',
    'А43': 'А43(МО;Х;ДП;М)',
    'А44': 'А44(МО;Х;ДП;М)',
    'А48': 'А48(МО;Х;ДП;М)',
    'А55': 'А5(Х;ДП;М;МО)',
    'А58': 'А8(Х;ДП;М;МО)',
    'А60': 'А10(Х;ДП;М;МО)',
    'А64': 'А14(Х;ДП;М;МО)',
    'А66': 'А16(Х;ДП;М;МО)',
    'А9': 'А9',
    'А32': 'А32(МО;Х;ДП;М)',
    'А50': 'А50(МО;Х;ДП;М)',
    'А52': 'А2(Х;ДП;М;МО)',
    'А8': 'А8',
    'А46': 'А46(МО;Х;ДП;М)',
    'А28': 'А28(МО;Х;ДП;М)',
    'А57': 'А7(Х;ДП;М;МО)',
    'А62': 'А12(Х;ДП;М;МО)',
}


@staff_account_required
def test_report_1(request):
    first_day = datetime.date(year=2019, month=4, day=22)
    last_day = datetime.date(year=2019, month=4, day=30)
    days = days_from_interval(first_day, last_day)

    result = []
    for day in days:
        timesheet = models.TimeSheet.objects.filter(
            customer__pk=VKUSVILL_PK,
            sheet_date=day
        ).prefetch_related(
            'worker_turnouts'
        ).get()

        for t in timesheet.worker_turnouts.all():
            code_name = t.worker_code_name
            full_name = str(t.worker)

            if full_name in _NEW_CODES and code_name in _KNOWN_CODES:
                code_by_name = _NEW_CODES[full_name]
                code_by_code = _KNOWN_CODES[code_name]

                if code_by_name != code_by_code:
                    message = 'WTF {} ({}) {}, {}/{}'.format(
                        full_name,
                        code_name,
                        t.worker.id,
                        code_by_name,
                        code_by_code
                    )

#            if full_name not in _NEW_CODES and code_name not in _KNOWN_CODES:
#                message = 'FC {} ({}) {}'.format(
#                    full_name,
#                    t.worker_code_name,
#                    t.worker.id
#                )
#                if message not in result:
#                    result.append(message)

#            if full_name not in _NEW_CODES:
#                message = 'F {} ({}) {}'.format(
#                    full_name,
#                    t.worker_code_name,
#                    t.worker.id
#                )
#                if message not in result:
#                    result.append(message)
#            if code_name not in _KNOWN_CODES:
#                message = 'C {} ({}) {}'.format(
#                    full_name,
#                    t.worker_code_name,
#                    t.worker.id
#                )
#                if message not in result:
#                    result.append(message)

        result = sorted(result)

    return JsonResponse(result, safe=False)


@staff_account_required
def rename_vegetables(request):
    turnouts = models.WorkerTurnout.objects.filter(
        worker_code_name__contains='ОВОЩИ'
    )

    rx = re.compile('^(.+)\(ОВОЩИ\)$')
    for turnout in turnouts:
        m = rx.match(turnout.worker_code_name)
        turnout.worker_code_name = m.group(1) + '(Овощи)'
        turnout.save()

    return JsonResponse([str(t) for t in turnouts], safe=False)


# Todo: remove
@staff_account_required
def rename_codes(request):
    first_day = datetime.date(year=2019, month=4, day=22)
    last_day = datetime.date(year=2019, month=4, day=30)

    problems = []

    turnouts = models.WorkerTurnout.objects.filter(
        timesheet__customer__pk=VKUSVILL_PK,
        timesheet__sheet_date__range=(first_day, last_day)
    ).select_related(
        'timesheet'
    )

    for turnout in turnouts:
        code_name = turnout.worker_code_name
        full_name = str(turnout.worker)

        if code_name in _KNOWN_CODES:
            turnout.worker_code_name = _KNOWN_CODES[code_name]
            turnout.save()
            continue

        if full_name in _NEW_CODES:
            turnout.worker_code_name = _NEW_CODES[full_name]
            turnout.save()
            continue

        message = '{}: {} ({}) {}'.format(
            string_from_date(turnout.timesheet.sheet_date),
            full_name,
            code_name,
            turnout.worker.id
        )
        problems.append(message)

    return JsonResponse(problems, safe=False)


@staff_account_required
def make_ugai_transform(request):
    from ..fine_utils import _find_worker

    ef = request.FILES['errors']
    book = xlrd.open_workbook(file_contents=ef.read())
    sheet = book.sheets()[0]

    workers = []
    for row in range(0, sheet.nrows):
        name = sheet.cell_value(row, 0)
        worker, _ = _find_worker(
            VKUSVILL_PK,
            name
        )
        if not worker:
            raise Exception('Not found {}!'.format(name))
        workers.append((worker, sheet.cell_value(row, 1)))

    first_day, last_day = get_first_last_day(request)

    for worker, amount in workers:
        if amount == 0:
            continue

        turnouts = worker.worker_turnouts.filter(
            timesheet__sheet_date__range=(first_day, last_day)
        )
        operations = finance.models.Operation.objects.filter(
            turnoutdeduction__turnout__in=turnouts,
            comment__icontains='Пересорт'
        )

        # На случай "нулевого пересорта"
        for operation in operations:
            if operation.amount < 1:
                operation.amount = 1
                operation.save()

        current_amount = operations.aggregate(
            Sum('amount')
        ).get('amount__sum') or 0

        coeff = decimal.Decimal(amount) / current_amount

        for operation in operations:
            operation.amount = operation.amount * coeff
            operation.save()

    return redirect('the_redhuman_is:vkusvill_management_page')


@staff_account_required
def temporary_fines(request):
    first_day = datetime.date(day=1, month=7, year=2019)
    workers = models.Worker.objects.filter(
        worker_turnouts__timesheet__customer__pk=VKUSVILL_PK,
        worker_turnouts__timesheet__sheet_date__gte=first_day
    ).distinct()

    debtors = []
    for w in workers:
        account = w.worker_account.account
        saldo = account.turnover_saldo()
        if saldo <= 0:
            continue

        fines = finance.models.Operation.objects.filter(
            timepoint__date__gte=first_day,
            customerfine__turnout__worker=w
        ).aggregate(
            Sum('amount')
        )['amount__sum'] or 0
        deductions = finance.models.Operation.objects.filter(
            Q(turnoutdeduction__turnout__worker=w) |
            Q(workerdeduction__isnull=False),
            timepoint__date__gte=first_day,
            debet=account,
        ).aggregate(
            Sum('amount')
        )['amount__sum'] or 0

        debtors.append((w, saldo, fines, deductions, deductions-saldo))

    return render(
        request,
        'the_redhuman_is/customer_specific/vkusvill/temporary_fines.html',
        {
            'debtors': debtors
        }
    )
