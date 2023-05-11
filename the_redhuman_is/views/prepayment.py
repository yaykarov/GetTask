# -*- coding: utf-8 -*-

import xlwt

from urllib.parse import quote

from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from the_redhuman_is.auth import staff_account_required

from the_redhuman_is.forms import (
    AccountablePersonForm,
    StatementWorkersForm
)

from the_redhuman_is import models

from the_redhuman_is.models import (
    Prepayment,
    WorkerPrepayment,
)

from the_redhuman_is.views.paysheet_v2 import (
    _get_paysheet_params,
    _style,
    _try_set_accountable_person,
    close_paysheet_permission_required,
)


@require_POST
@user_passes_test(lambda user: user.is_superuser)
@staff_account_required
@transaction.atomic
def create(request):
    (
        customer,
        location,
        accountable_person,
        worker_pk,
        first_day,
        last_day
    ) = _get_paysheet_params(request)

    if customer is None:
        return HttpResponse(
            content='Для аванса поле "Клиент" является обязательным',
            status=403
        )

    workers = None
    if worker_pk:
        workers = models.Worker.objects.filter(pk=worker_pk)

    prepayment = models.paysheet.create_prepayment(
        request.user,
        accountable_person,
        first_day,
        last_day,
        customer,
        location,
        workers
    )

    return redirect('the_redhuman_is:prepayment_show', pk=prepayment.pk)


@require_POST
@user_passes_test(lambda user: user.is_superuser)
@staff_account_required
def add_workers(request, pk):
    prepayment = get_object_or_404(Prepayment, pk=pk)
    workers_ids = request.POST.getlist('worker')
    for worker in workers_ids:
        saldo = worker.worker_account.account.turnover_saldo()
        if -saldo:
            WorkerPrepayment.objects.create(
                worker_id=worker,
                amount=0,
                prepayment=prepayment
            ).save()

    return redirect('the_redhuman_is:prepayment_show', pk=prepayment.pk)


# Todo: !!!
#@require_POST
@staff_account_required
@close_paysheet_permission_required
def delete_worker(request, prepayment, worker):
    WorkerPrepayment.objects.filter(
        prepayment=prepayment,
        worker=worker
    ).delete()

    if request.is_ajax():
        return HttpResponse('ok')
    else:
        return redirect('the_redhuman_is:prepayment_show', pk=prepayment.pk)


@require_POST
@user_passes_test(lambda user: user.is_superuser)
@staff_account_required
@transaction.atomic
def set_accountable_person(request, pk):
    prepayment = Prepayment.objects.get(pk=pk)
    _try_set_accountable_person(prepayment, request.POST)
    return redirect('the_redhuman_is:prepayment_show', pk=prepayment.pk)


@require_POST
@staff_account_required
@close_paysheet_permission_required
def add_image(request, pk):
    prepayment = Prepayment.objects.get(pk=pk)

    for image in request.FILES.getlist('image'):
        models.add_photo(prepayment, image)

    return redirect('the_redhuman_is:prepayment_show', pk=prepayment.pk)


@require_POST
@staff_account_required
@close_paysheet_permission_required
@transaction.atomic
def close(request, pk):
    prepayment = get_object_or_404(Prepayment, pk=pk)

    if not models.get_photos(prepayment).exists():
        messages.error(request, 'К авансовой ведомости не прикреплено фото')
        return redirect(reverse('the_redhuman_is:prepayment_show', args=[pk]))

    if not prepayment.is_closed:
        accountable_person = models.get_accountable_person(prepayment)
        account = accountable_person.account_71
        prepayment.close(request.user, account)

    return redirect(
        reverse('the_redhuman_is:prepayment_show', args=[prepayment.pk])
    )


# Todo: !!!
#@require_POST
@user_passes_test(lambda user: user.is_superuser)
@staff_account_required
def save(request, pk):
    if request.POST:
        amount_for_all = request.POST.get('amount_for_all')
        if not amount_for_all:
            amount_for_all = 0
        amount_for_all = float(amount_for_all)

        if amount_for_all:
            request.session.pop('unchanged_worker_prepayment', None)
            unchanged = []
            for item in Prepayment.objects.get(pk=pk).workers.all():
                saldo = -item.worker.worker_account.account.turnover_saldo()
                if saldo > amount_for_all:
                    item.amount = amount_for_all
                    item.save()
                else:
                    unchanged.append(item.worker_id)
            if unchanged:
                request.session['unchanged_worker_prepayment'] = unchanged
        else:
            for key in request.POST:
                if key.startswith('wp-'):
                    id = key.split('-')[-1]
                    wp = WorkerPrepayment.objects.get(pk=id)
                    wp.amount = request.POST[key]
                    wp.save()
    if request.is_ajax():
        return HttpResponse('ok')
    else:
        return redirect(reverse('the_redhuman_is:prepayment_show', args=[pk]))


@staff_account_required
def show(request, pk):
    prepayment = get_object_or_404(Prepayment, pk=pk)

    user_groups = request.user.groups.values_list('name', flat=True)
    if 'Менеджеры' in user_groups:
        customers = models.Customer.objects.filter(
            maintenancemanager__worker__workeruser__user=request.user
        )
        if not models.DocumentWithAccountablePerson.objects.filter(
            accountable_person__worker__workeruser__user=request.user,
            object_id=pk,
            content_type=ContentType.objects.get_for_model(Prepayment)
        ).exists() and prepayment.customer not in customers:
            raise PermissionDenied()

    workers_prepayments = list()
    for item in prepayment.workers.all():
        saldo = item.worker.worker_account.account.turnover_saldo()
        workers_prepayments.append({
            'id': item.pk,
            'worker': item.worker,
            'saldo': -saldo,
            'amount': item.real_amount(),
        })

    workers_prepayments.sort(key=lambda w: str(w['worker']))

    accountable_person_form = None
    accountable_person = models.get_accountable_person(prepayment)
    if accountable_person:
        if not models.AccountableDocumentOperation.objects.filter(
            document__content_type=ContentType.objects.get_for_model(Prepayment),
            document__object_id=prepayment.pk
        ).exists():
            accountable_person_form = AccountablePersonForm(
                initial={ 'person': accountable_person }
            )

    mode = 'readonly'
    if request.user.is_superuser:
        mode = 'superuser'
    elif 'Закрытие ведомостей' in user_groups:
        mode = 'close_allowed'

    data = {
        'mode': mode,
        'prepayment': prepayment,
        'accountable_person': accountable_person,
        'photos': models.get_photos(prepayment),
        'workers_prepayments': workers_prepayments,
        'form': StatementWorkersForm(),
        'accountable_person_form': accountable_person_form,
        'unchanged': request.session.pop('unchanged_worker_prepayment', None),
    }
    if request.GET.get('output') == 'xls':
        xls = prepayment_xls(prepayment, workers_prepayments)

        response = HttpResponse(content_type='application/vnd.ms-excel')
        response[
            'Content-Disposition'
        ] = "attachment; filename*=UTF-8''" + quote(str(prepayment) + '.xls')
        xls.save(response)
        return response
    else:
        return render(
            request,
            'the_redhuman_is/paysheet_v2/prepayment.html',
            data
        )


def prepayment_xls(prepayment, data):
    title = 'Аванс №{}'.format(prepayment.pk)
    wb = xlwt.Workbook(encoding='utf-8')
    ws = wb.add_sheet(title, cell_overwrite_ok=True)
    ws.set_header_str(''.encode('utf-8'))
    ws.set_footer_str(''.encode('utf-8'))

    row_num = 0

    title_font = _style()
    title_font.font.bold = True
    title_font.font.height = 220
    title_font.alignment.wrap = xlwt.Formatting.Alignment.WRAP_AT_RIGHT
    title_font.alignment.vert = xlwt.Formatting.Alignment.VERT_CENTER

    ws.row(0).height_mismatch = True
    ws.row(0).height = 540
    ws.merge(0, 0, 0, 3)
    ws.merge(1, 1, 0, 1)
    ws.merge(1, 1, 2, 3)
    # Хак для правильной рамки у объединенной ячейки
    for i in range(3):
        ws.write(0, i + 1, None, title_font)
        ws.write(1, i + 1, None, title_font)

    col_num = 0
    ws.write(row_num, col_num, str(prepayment), title_font)
    row_num += 1

    ws.write(row_num, 0, 'Подотчетное лицо:', title_font)
    accountable_person = models.get_accountable_person(prepayment) or ''
    ws.write(row_num, 2, str(accountable_person), title_font)
    row_num += 1

    ws.write(row_num, col_num, '№', title_font)
    ws.col(col_num).width = 800
    col_num += 1

    ws.write(row_num, col_num, 'Рабочий', title_font)
    ws.col(col_num).width = 9000
    col_num += 1

    ws.write(row_num, col_num, 'Выплатить', title_font)
    ws.col(col_num).width = 4000
    col_num += 1

    ws.write(row_num, col_num, 'Подпись', title_font)
    ws.col(col_num).width = 7500

    font_style = _style()
    i = 1
    for item in data:
        row_num += 1
        col_num = 0

        ws.row(row_num).height_mismatch = True
        ws.row(row_num).height = 400

        ws.write(row_num, col_num, i, font_style)
        col_num += 1
        ws.write(row_num, col_num, str(item['worker']), font_style)
        col_num += 1
        ws.write(row_num, col_num, item['amount'], font_style)
        col_num += 1
        ws.write(row_num, col_num, '', font_style)
        col_num += 1
        i += 1
    col_num = 0
    row_num += 1
    ws.write(row_num, col_num, 'Итого', font_style)
    ws.merge(row_num, row_num, col_num, col_num + 1)
    col_num = 2
    ws.write(row_num, col_num, prepayment.total_amount, font_style)
    col_num += 1

    return wb


@require_POST
@user_passes_test(lambda user: user.is_superuser)
@staff_account_required
def remove(request, pk):
    prepayment = get_object_or_404(Prepayment, pk=pk)
    prepayment.workers.filter(operation__isnull=True).delete()
    prepayment.delete()
    return redirect('the_redhuman_is:paysheet_v2_list')

