# -*- coding: utf-8 -*-

import datetime
import re
import xlrd

from django.forms import ModelChoiceField
from django.forms import Select

from django.db import transaction

from django.shortcuts import redirect
from django.shortcuts import render

from django.views.decorators.http import require_POST

from the_redhuman_is.auth import staff_account_required

from the_redhuman_is import forms
from the_redhuman_is import models

from utils.date_time import date_from_string


class FinesForm(forms.CustomerSelectionForm):
    material_type = ModelChoiceField(
        queryset=models.MaterialType.objects.all(),
        label='Тип штрафа/вычета - дисциплинарный. Остальные варианты вычетов пока внести нельзя, ждите обновлений.',
        widget=Select(
            attrs={'class': 'form-control hidden', 'hidden': True}
        ),
        required=False,
    )


def _find_worker(customer_pk, full_name):
    full_name = re.sub(r'\s+', ' ', full_name.lower().strip())
    name_components = re.split('[\.\s]+', full_name)
    last_name = name_components[0]

    workers = models.Worker.objects.filter(
        last_name__icontains=last_name
    )
    if customer_pk:
        workers = workers.filter(
            worker_turnouts__timesheet__customer__pk=customer_pk
        ).distinct()

    worker = None

    for w in workers:
        if str(w).lower() == full_name:
            worker = w
            break

    if not worker:
        similar = []
        if len(name_components) >= 3:
            name = name_components[1]
            patronymic = name_components[2]
            for w in workers:
                if w.name and w.patronymic:
                    if w.name.lower()[0] != name[0]:
                        continue
                    if w.patronymic.lower()[0] != patronymic[0]:
                        continue
                    similar.append(w)
        if len(similar) == 1:
            worker = similar[0]

    return worker, workers


def _parse_fines_file(customer_pk, sheet):
    normal = []
    problem = {}
    format_errors = []
    for row in range(1, sheet.nrows):
        name = sheet.cell_value(row, 0).strip()
        worker, workers = _find_worker(customer_pk, name)

        col_date = 1
        col_fine = col_date + 1
        col_deduction = col_fine + 1
        col_comment = col_deduction + 1

        try:
            if sheet.cell_type(row, col_date) == xlrd.XL_CELL_DATE:
                date = datetime.datetime(
                    *xlrd.xldate_as_tuple(
                        sheet.cell_value(row, col_date),
                        sheet.book.datemode
                    )
                ).date()
            else:
                date = date_from_string(sheet.cell_value(row, col_date))
        except Exception as e:
            format_errors.append(
                'Строка {}: что-то не так с датой ({}).'.format(row, e)
            )
            continue

        fine = sheet.cell_value(row, col_fine)
        if fine != '' and fine is not None:
            fine = abs(fine)
        deduction = sheet.cell_value(row, col_deduction)
        if deduction != '' and deduction is not None:
            deduction = abs(deduction)

        comment = sheet.cell_value(row, col_comment)

        if worker:
            data = {
                'worker': worker,
                'date': date,
                'comment': comment
            }
            if fine:
                data['fine'] = fine
                data['turnout'] = models.WorkerTurnout.objects.filter(
                    worker=worker,
                    timesheet__sheet_date__lte=date,
                    turnoutservice__isnull=False,
                ).order_by('timesheet__sheet_date').last()
            if deduction:
                data['deduction'] = deduction
            normal.append(data)
        else:
            problem[name] = workers

    return normal, problem, format_errors


def _problem_workers(customer_pk, sheet):
    result = []
    for row in range(1, sheet.nrows):
        name = sheet.cell_value(row, 0)
        worker, workers = _find_worker(customer_pk, name)

        if not worker and name not in result:
            result.append((name, [str(w) for w in workers]))

    return result


@staff_account_required
def import_fines(request):
    return render(
        request,
        'the_redhuman_is/fine_utils/import_fines.html',
        {
            'fines_form': FinesForm()
        }
    )


@require_POST
@staff_account_required
@transaction.atomic
def do_import_fines(request):
    ff = request.FILES['fines']
    customer_pk = request.POST['customer']
    material_type_pk = request.POST.get('material_type')

    book = xlrd.open_workbook(
        file_contents=ff.read()
    )
    sheet = book.sheet_by_index(0)

    normal, problem, format_errors = _parse_fines_file(customer_pk, sheet)
    if problem or format_errors:
        return render(
            request,
            'the_redhuman_is/fine_utils/import_fines_errors.html',
            {
                'customer_name': models.Customer.objects.get(pk=customer_pk).cust_name,
                'problem_workers': problem,
                'format_errors': format_errors
            }
        )

    operations_pack = models.fine_utils.create_fines(
        request.user,
        customer_pk,
        material_type_pk,
        normal,
        'Импорт штрафов из файла. {}/{}'.format(
            models.Customer.objects.get(pk=customer_pk).cust_name,
            models.MaterialType.objects.get(pk=material_type_pk).name if material_type_pk else 'штрафы или дисциплинарные вычеты'
        )
    )

    ff.seek(0)
    deductions_file = models.fine_utils.create_deductions_file(
        request.user,
        ff,
        customer_pk,
    )
    deductions_file.on_import_complete(operations_pack)

    return redirect('the_redhuman_is:fine_utils_operations_pack_list')


@staff_account_required
def operations_pack_list(request):
    return render(
        request,
        'the_redhuman_is/fine_utils/operations_pack_list.html',
        {
            'packs': models.fine_utils.OperationsPack.objects.all(
            ).prefetch_related(
                'deductions_file'
            ).order_by(
                '-timestamp'
            )
        }
    )


@require_POST
@staff_account_required
def rollback_operations_pack(request, pk):
    pack = models.fine_utils.OperationsPack.objects.get(pk=pk)
    models.fine_utils.rollback_operations_pack(
        pack,
        remove_from_paysheet=(request.POST.get('remove_from_paysheet') == 'on')
    )

    return redirect('the_redhuman_is:fine_utils_operations_pack_list')
