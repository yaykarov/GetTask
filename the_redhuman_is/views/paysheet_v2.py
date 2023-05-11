# -*- coding: utf-8 -*-

import datetime
import decimal
import io
import json
import math
import os
import re
import xlwt

from dal import autocomplete
from django.contrib.auth.models import Group
from django.core.exceptions import (
    ObjectDoesNotExist,
    PermissionDenied,
)

from django.db import transaction

from django.db.models import (
    DecimalField,
    Exists,
    ExpressionWrapper,
    F,
    OuterRef,
    PositiveIntegerField,
    Q,
    Subquery,
    Sum,
    Value,
)
from django.db.models.functions import (
    Coalesce,
    Greatest,
    Upper,
)


from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.contenttypes.models import ContentType
from django.forms import ModelChoiceField
from django.http import (
    HttpResponse,
    JsonResponse,
)
from django.shortcuts import (
    redirect,
    render,
)
from django.utils import timezone
from django.views.decorators.http import require_POST

from urllib.parse import quote

from zipfile import ZipFile

import finance
from doc_templates import odt
from doc_templates.http_responses import xlsx_content_response

from the_redhuman_is import (
    forms,
    models,
    services,
)
from the_redhuman_is.models import WorkerTurnout

from the_redhuman_is.models.paysheet_v2 import (
    Paysheet_v2,
    Paysheet_v2Entry,
)
from the_redhuman_is.models.paysheet import (
    PaysheetTalkBankPaymentStatus,
    Prepayment,
)

from the_redhuman_is.auth import staff_account_required
from the_redhuman_is.tasks import (
    send_email,
    make_paysheet_payments_with_talk_bank,
)

from utils.date_time import (
    as_default_timezone,
    date_from_string,
    days_from_interval,
    string_from_date,
)
from utils.numbers import get_decimal

from the_redhuman_is.views.utils import (
    _get_value,
    get_first_last_day,
)
from the_redhuman_is.services.paysheet import (
    add_registry as do_add_registry,
    get_service_name,
    paysheet_photos,
    paysheet_receipt_photos,
)
from the_redhuman_is.services.paysheet.talk_bank import get_paysheet_payment_report


def close_paysheet_permission_required(function):
    def _proxy(request, *args, **kwargs):
        if not request.user.is_superuser:
            user_groups = request.user.groups.values_list(
                'name',
                flat=True
            )
            if 'Закрытие ведомостей' not in user_groups:
                raise PermissionDenied()

        return function(request, *args, **kwargs)

    return _proxy


def _get_paysheet_params(request):
    worker_pk = request.POST.get('worker')
    if worker_pk == 0:
        worker_pk = None

    customer = None
    customer_pk = request.POST.get('customer')
    if customer_pk:
        customer = models.Customer.objects.get(
            pk=customer_pk
        )

    location = None
    location_pk = request.POST.get('location')
    if location_pk:
        location = models.CustomerLocation.objects.get(
            pk=location_pk
        )

    accountable_person = None
    accountable_person_pk = request.POST.get('accountable_person')
    if accountable_person_pk:
        accountable_person = models.AccountablePerson.objects.get(
            pk=accountable_person_pk
        )
    first_day, last_day = get_first_last_day(request)

    return (
        customer,
        location,
        accountable_person,
        worker_pk,
        first_day,
        last_day
    )


def _try_set_accountable_person(paysheet, POST):
    if not paysheet.is_closed:
        if not models.AccountableDocumentOperation.objects.filter(
            document__content_type=ContentType.objects.get_for_model(type(paysheet)),
            document__object_id=paysheet.pk
        ).exists():
            accountable_person = models.AccountablePerson.objects.get(
                pk=POST['person']
            )
            models.set_accountable_person(paysheet, accountable_person)


class WorkerAutocomplete(LoginRequiredMixin, autocomplete.Select2QuerySetView):
    def get_queryset(self):
        location_pk = self.forwarded.get('location')
        if location_pk:
            workers = models.Worker.objects.annotate(
                has_location=Exists(
                    WorkerTurnout.objects.filter(
                        worker=OuterRef('pk'),
                        timesheet_cust_location=location_pk
                    )
                )
            ).filter(
                has_location=True
            )
            if self.q:
                workers = workers.filter_by_text(self.q)
            return workers
        return models.Worker.objects.none()


# Для страницы учета расходов, в разделе "выдача подотчетному лицу"
# Todo: search by string?
@staff_account_required
def paysheet_autocomplete(request):
    person_pk = json.loads(request.GET['forward'])['person']
    q = request.GET.get('q')
    prepayments = models.Prepayment.objects.exclude(
        workers__operation__isnull=False
    )
    if q:
        paysheets = models.Paysheet_v2.objects.filter(
            Q(customer__cust_name__icontains=q) |
            Q(location__location_name__icontains=q),
            is_closed=False,
        )
        prepayments = prepayments.filter(
            Q(location__customer_id__cust_name__icontains=q) |
            Q(location__location_name__icontains=q),
        )
    else:
        paysheets = models.Paysheet_v2.objects.filter(
            is_closed=False
        )
    paysheets = paysheets.annotate(
        person_pk=Subquery(
            models.DocumentWithAccountablePerson.objects.filter(
                accountabledocumentoperation__isnull=True,
                content_type=ContentType.objects.get_for_model(
                    models.Paysheet_v2
                ),
                object_id=OuterRef('pk')
            ).values('accountable_person'),
            output_field=PositiveIntegerField()
        )
    ).filter(
        person_pk=person_pk
    )

    prepayments = prepayments.annotate(
        person_pk=Subquery(
            models.DocumentWithAccountablePerson.objects.filter(
                accountabledocumentoperation__isnull=True,
                content_type=ContentType.objects.get_for_model(
                    models.Prepayment
                ),
                object_id=OuterRef('pk')
            ).values('accountable_person'),
            output_field=PositiveIntegerField()
        )
    ).filter(
        person_pk=person_pk
    )

    results = []
    for paysheet in paysheets:
        results.append(
            {
                'id': 'paysheet_{}'.format(paysheet.pk),
                'text': str(paysheet)
            }
        )
    for prepayment in prepayments:
        results.append(
            {
                'id': 'prepayment_{}'.format(prepayment.pk),
                'text': str(prepayment)
            }
        )

    return JsonResponse({'results': results}, safe=False)


class PaysheetCreationForm(forms.CustomerAndLocationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['location'].required = False
        self.fields['customer'].required = False

    worker = ModelChoiceField(
        queryset=models.Worker.objects.all(),
        label='',
        widget=autocomplete.ListSelect2(
            attrs={'class': 'form-control'},
            url='the_redhuman_is:paysheet_v2_worker_autocomplete',
            forward=['location']
        ),
        required=False
    )
    accountable_person = ModelChoiceField(
        label='Подотчетное лицо',
        queryset=models.AccountablePerson.objects.all(),
        widget=autocomplete.ModelSelect2(
            attrs={'class': 'form-control'},
            url='the_redhuman_is:accountable-person-autocomplete'
        ),
    )


@staff_account_required
def list_paysheets(request):
    readonly = not request.user.is_superuser
    user_groups = request.user.groups.values_list('name', flat=True)
    deadline = timezone.now() - datetime.timedelta(hours=24)

    paysheets = Paysheet_v2.objects.with_short_description(
    ).with_total_amount(
    ).with_issued_amount(
    ).with_data(deadline=deadline)

    prepayments = Prepayment.objects.with_short_description(
    ).with_is_closed(
    ).with_total_amount(
    ).with_issued_amount(
    ).with_data(deadline=deadline)

    if not (request.user.is_superuser or 'Касса' in user_groups):
        paysheets = paysheets.filter(
            is_closed=False
        )
        prepayments = prepayments.filter(
            closed=False
        )
        if 'Менеджеры' in user_groups:
            paysheets = paysheets.filter_by_accountable_user(request.user.pk)
            prepayments = prepayments.filter_by_accountable_user(request.user.pk)

    return render(
        request,
        'the_redhuman_is/paysheet_v2/list.html',
        {
            'readonly': readonly,
            'creation_form': PaysheetCreationForm(),
            # Todo: some initial values?
            'interval_form': forms.DaysPickerIntervalForm(),
            'paysheets': paysheets,
            'prepayments': prepayments,
        }
    )


@require_POST
@user_passes_test(lambda user: user.is_superuser)
@staff_account_required
def do_create(request):
    (
        customer,
        location,
        accountable_person,
        worker_pk,
        first_day,
        last_day
    ) = _get_paysheet_params(request)

    workers = None
    if worker_pk:
        workers = models.Worker.objects.filter(pk=worker_pk)

    paysheet = models.paysheet_v2.create_paysheet(
        request.user,
        accountable_person,
        first_day,
        last_day,
        customer,
        location,
        workers
    )

    return redirect('the_redhuman_is:paysheet_v2_show', pk=paysheet.pk)


@require_POST
@user_passes_test(lambda user: user.is_superuser)
@staff_account_required
def remove(request, pk):
    paysheet = Paysheet_v2.objects.get(pk=pk)
    if not paysheet.is_closed:
        paysheet.delete()
    return redirect('the_redhuman_is:paysheet_v2_list')


@require_POST
@user_passes_test(lambda user: user.is_superuser)
@staff_account_required
def toggle_lock(request, pk):
    paysheet = Paysheet_v2.objects.get(pk=pk)
    if not paysheet.is_closed:
        paysheet.toggle_lock()
    return redirect('the_redhuman_is:paysheet_v2_show', pk=pk)


@require_POST
@close_paysheet_permission_required
@transaction.atomic
def remove_workers(request, pk):
    paysheet = Paysheet_v2.objects.get(pk=pk)
    if not paysheet.is_closed:
        workers_pks = request.POST.getlist('worker_pk')
        for worker_pk in workers_pks:
            paysheet.remove_worker(worker_pk)

    return redirect('the_redhuman_is:paysheet_v2_show', pk=pk)


@require_POST
@user_passes_test(lambda user: user.is_superuser)
@staff_account_required
def reset_workers(request, pk):
    paysheet = Paysheet_v2.objects.get(pk=pk)
    if not paysheet.is_closed:
        filter_payments_by_customer = request.POST.get(
            'filter_payments_by_customer',
            'true'
        ) == 'true'
        workers_pks = request.POST.getlist('worker_pk')
        paysheet.reset_workers(workers_pks, filter_payments_by_customer)

    return redirect('the_redhuman_is:paysheet_v2_show', pk=pk)


@require_POST
@user_passes_test(lambda user: user.is_superuser)
@staff_account_required
def add_remainders(request, pk):
    paysheet = Paysheet_v2.objects.get(pk=pk)
    if not paysheet.is_closed:
        workers_pks = request.POST.getlist('worker_pk')
        workers = models.Worker.objects.filter(
            pk__in=workers_pks
        ).annotate(
            to_pay = Subquery(
                models.Paysheet_v2Entry.objects.filter(
                    worker__pk=OuterRef('pk'),
                    paysheet=paysheet
                ).values('amount')
            ),
        )
        for worker in workers:
            entry = paysheet.paysheet_entries.get(
                worker=worker
            )
            value = worker.to_pay + get_decimal(
                request.POST['remainder_{}'.format(worker.pk)]
            )
            amount = max(value, 0)
            if worker.selfemployment_data.filter(deletion_ts__isnull=True).first() is None:
                amount = math.floor(amount / decimal.Decimal(100.0)) * 100
            entry.update_amount(amount)

    return redirect('the_redhuman_is:paysheet_v2_show', pk=pk)


@require_POST
@close_paysheet_permission_required
def save_receipts(request, pk):
    paysheet = Paysheet_v2.objects.get(pk=pk)
    if not paysheet.is_closed:
        workers_pks = request.POST.getlist('worker_pk')
        workers = models.Worker.objects.filter(
            pk__in=workers_pks
        )
        for worker in workers:
            receipt_url = request.POST['receipt_{}'.format(worker.pk)]

            entry = paysheet.paysheet_entries.get(worker=worker)

            try:
                receipt_entry = models.WorkerReceiptPaysheetEntry.objects.get(
                    paysheet_entry=entry
                )
                receipt = receipt_entry.worker_receipt
                receipt.timestamp = timezone.localtime()
                receipt.author = request.user
                receipt.url = receipt_url
                receipt.save()

            except ObjectDoesNotExist:
                receipt = models.WorkerReceipt.objects.create(
                    author=request.user,
                    worker=worker,
                    url=receipt_url,
                    date=timezone.localdate(paysheet.timestamp)
                )
                models.WorkerReceiptPaysheetEntry.objects.create(
                    worker_receipt=receipt,
                    paysheet_entry=entry,
                )

    return redirect('the_redhuman_is:paysheet_v2_show', pk=pk)


@require_POST
@user_passes_test(lambda user: user.is_superuser)
@staff_account_required
@transaction.atomic
def recreate(request, pk):
    paysheet = Paysheet_v2.objects.get(pk=pk)
    if not paysheet.is_closed:
        paysheet.recreate()

    return redirect('the_redhuman_is:paysheet_v2_show', pk=pk)


@require_POST
@user_passes_test(lambda user: user.is_superuser)
@staff_account_required
def remove_operation(request, paysheet_pk, operation_pk):
    paysheet = Paysheet_v2.objects.get(pk=paysheet_pk)
    if not paysheet.is_closed:
        paysheet.remove_operation(operation_pk)

    return redirect('the_redhuman_is:paysheet_v2_show', pk=paysheet_pk)


@require_POST
@user_passes_test(lambda user: user.is_superuser)
@staff_account_required
@transaction.atomic
def set_accountable_person(request, pk):
    paysheet = Paysheet_v2.objects.get(pk=pk)
    _try_set_accountable_person(paysheet, request.POST)
    return redirect('the_redhuman_is:paysheet_v2_show', pk=pk)


# Todo: what timezone to use?
def _date(operation):
    return as_default_timezone(operation.timepoint).date()


def _add_operations(calendar, operations, keyword):
    for operation in operations:
        day = _date(operation)
        if day not in calendar:
            calendar[day] = {}
        calendar[day][keyword] = calendar[day].get(keyword, 0) + operation.amount


# Todo: get rid of this
def _worker_row_for_paysheet(paysheet, worker):
    calendar = {}

    account = worker.worker_account.account
    debet_operations, credit_operations = paysheet.account_operations(
        account.pk
    )
    _add_operations(calendar, debet_operations, 'debet')
    _add_operations(calendar, credit_operations, 'credit')

    return calendar


# Todo: move to finance module?
def _account_saldo(account_ref, operations=None, deadline=None):
    if operations is None:
        operations = finance.models.Operation.objects.all()

    debit_subquery = Subquery(
        operations.filter(
            debet=OuterRef(account_ref)
        ).values(
            'debet'
        ).annotate(
            Sum('amount'),
        ).values('amount__sum')
    )

    if deadline:
        operations = operations.filter(
            timepoint__date__lte=deadline
        )
    credit_subquery = Subquery(
        operations.filter(
            credit=OuterRef(account_ref)
        ).values(
            'credit'
        ).annotate(
            Sum('amount'),
        ).values('amount__sum')
    )

    return ExpressionWrapper(
        Coalesce(credit_subquery, 0) - Coalesce(debit_subquery, 0),
        output_field=DecimalField()
    )


def _get_paysheet_content(paysheet):
    workers = paysheet.workers(
    ).select_related(
        'citizenship',
        'banned',
    ).with_is_selfemployed(
    ).with_paysheet_amount_to_pay(
        paysheet
    ).with_has_registry_receipt(
        paysheet
    ).with_paysheet_receipt_url(
        paysheet.pk
    ).annotate(
        deposit_saldo=_account_saldo('deposit__account__pk'),
        turnover_saldo=_account_saldo('worker_account__account__pk'),
        payday_saldo=_account_saldo(
            'worker_account__account__pk',
            deadline=paysheet.last_day
        ),
        interval_saldo=_account_saldo(
            'worker_account__account__pk',
            operations=finance.models.Operation.objects.filter(
                paysheet_entry_operation__entry__worker__pk=OuterRef('pk'),
                paysheet_entry_operation__entry__paysheet=paysheet
            ),
        ),
        remainder=Greatest(
            Greatest(F('payday_saldo'), 0, output_field=DecimalField()) -
                Greatest(F('paysheet_amount_to_pay'), 0, output_field=DecimalField()),
            0,
            output_field=DecimalField()
        ),
        account=Subquery(
            finance.models.Account.objects.filter(
                pk=OuterRef('worker_account__account__pk')
            ).values(
                'id'
            )
        ),
        location=Coalesce(
            Subquery(
                models.ZoneGroup.objects.filter(
                    workerzone__worker__pk=OuterRef('pk')
                ).values(
                    'name'
                )
            ),
            Value('-')
        )
    )

    days = days_from_interval(paysheet.first_day, paysheet.last_day)

    grid = []
    index = 1
    total_values = {
        'deposit': 0,
        'total': 0,
        'payday_saldo': 0,
        'interval_saldo': 0,
        'paysheet_amount_to_pay': 0,
        'remainder': 0,
    }
    for worker in workers:
        calendar = {}

        debet_operations, credit_operations = paysheet.account_operations(
            worker.account
        )
        _add_operations(calendar, debet_operations, 'debet')
        _add_operations(calendar, credit_operations, 'credit')

        pending_turnouts = worker.worker_turnouts.filter(
            turnoutoperationtopay__isnull=True
        ).prefetch_related(
            'timesheet'
        )
        for turnout in pending_turnouts:
            day = turnout.timesheet.sheet_date
            if day in calendar:
                calendar[day]['warning'] = True
            else:
                calendar[day] = {'warning': True}

        expanded_calendar = [calendar.get(d) for d in days]

        grid.append(
            (
                index,
                worker,
                expanded_calendar
            )
        )

        index += 1

        total_values['deposit'] += worker.deposit_saldo
        total_values['total'] += worker.turnover_saldo
        total_values['payday_saldo'] += worker.payday_saldo
        total_values['interval_saldo'] += worker.interval_saldo
        total_values['paysheet_amount_to_pay'] += worker.paysheet_amount_to_pay
        total_values['remainder'] += worker.remainder

    return days, grid, total_values


def _check_paysheet_permissions(paysheet, user):
    if not (
            models.Customer.objects.filter(
                maintenancemanager__worker__workeruser__user=user,
                id=paysheet.customer_id
            ).exists()
            or
            models.DocumentWithAccountablePerson.objects.filter(
                accountable_person__worker__workeruser__user=user,
                object_id=paysheet.pk,
                content_type=ContentType.objects.get_for_model(Paysheet_v2)
            ).exists()
    ):
        raise PermissionDenied()


@staff_account_required
def show(request, pk):
    paysheet = Paysheet_v2.objects.all(
    ).with_talk_bank_payment_status(
    ).get(pk=pk)
    user_groups = request.user.groups.values_list('name', flat=True)
    if 'Менеджеры' in user_groups:
        _check_paysheet_permissions(paysheet, request.user)

    days, grid, total_values = _get_paysheet_content(paysheet)

    accountable_person_form = None
    accountable_person = models.get_accountable_person(paysheet)
    if accountable_person:
        if not models.AccountableDocumentOperation.objects.filter(
            document__content_type=ContentType.objects.get_for_model(Paysheet_v2),
            document__object_id=paysheet.pk
        ).exists():
            accountable_person_form = forms.AccountablePersonForm(
                initial={'person': accountable_person}
            )

    mode = 'readonly'

    if paysheet.talk_bank_payment_status == PaysheetTalkBankPaymentStatus.ERROR:
        if request.user.is_superuser:
            mode = 'close_allowed'

    if paysheet.talk_bank_payment_status == None:
        if request.user.is_superuser:
            mode = 'superuser'
        elif 'Закрытие ведомостей' in user_groups:
            mode = 'close_allowed'

    status_text = PaysheetTalkBankPaymentStatus.STATUS_DICT.get(paysheet.talk_bank_payment_status)

    data = {
        'mode': mode,
        'paysheet': paysheet,
        'talk_bank_payment_status_text': status_text,
        'accountable_person': accountable_person,
        'photos': paysheet_photos(paysheet),
        'days': days,
        'grid': grid,
        'accountable_person_form': accountable_person_form,
        'total_values': total_values,
    }

    return render(request, 'the_redhuman_is/paysheet_v2/show.html', data)


@staff_account_required
def download_paysheet(request, pk):
    paysheet = Paysheet_v2.objects.get(pk=pk)
    if request.user.groups.filter(name='Менеджеры').exists():
        _check_paysheet_permissions(paysheet, request.user)

    workers_type = _get_value(request, 'workers')
    output = _get_value(request, 'output')

    if workers_type == 'normal':
        wb, _ = paysheet_xls_normal(paysheet)
    elif workers_type == 'self_employed_normal':
        csv, _, registry_num = paysheet_csv_self_employed_normal(paysheet)
        if output != 'csv':
            raise NotImplementedError
    elif workers_type == 'self_employed_another_account':
        wb, _ = paysheet_xls_self_employed_another_account(paysheet)
    else:
        raise NotImplementedError

    if output == 'xls':
        response = HttpResponse(content_type='application/vnd.ms-excel')
        response['Content-Disposition'] = f"attachment; filename*=UTF-8''{quote(str(paysheet))}.xls"
        wb.save(response)
    elif output == 'csv':
        response = HttpResponse(content_type='text/csv')
        filename = f'Реестр {registry_num} (ведомость {paysheet.pk})'
        response['Content-Disposition'] = f"attachment; filename*=UTF-8''{quote(filename)}.csv"
        response.write(csv)
    elif output == 'pdf':
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f"attachment; filename*=UTF-8''{quote(str(paysheet))}.pdf"
        xls = io.BytesIO()
        wb.save(xls)
        pdf_object = odt.convert_to_pdf(xls.getvalue(), suffix='.xls')
        response.write(pdf_object)
    else:
        raise NotImplementedError

    return response


def do_email_paysheet(paysheet):
    cashier_emails = list(
        Group.objects.get(
            name='Касса'
        ).user_set.values_list(
            'email',
            flat=True
        ).distinct()
    )

    text_body = [f'Ведомости приложены.\n']

    attachments = []
    try:
        wb_normal, normal_total = paysheet_xls_normal(
            paysheet,
            workers_presence_required=True
        )
    except NoDataError:
        pass
    else:
        xls_normal = io.BytesIO()
        wb_normal.save(xls_normal)
        pdf_object = odt.convert_to_pdf(xls_normal.getvalue(), suffix='.xls')
        text_body.append(f'Обычные: {normal_total} руб.')
        attachments.append(
            {
                'filename': f'{paysheet} (без СЗ).pdf',
                'body': pdf_object,
                'mime_type': ('application', 'pdf')
            },
        )

    try:
        registry, registry_se_total, registry_num = paysheet_csv_self_employed_normal(
            paysheet,
            workers_presence_required=True
        )
    except NoDataError:
        pass
    else:
        text_body.append(f'Самозанятые МТС: {registry_se_total} руб.')
        attachments.append(
            {
                'filename': f'Реестр {registry_num} (ведомость {paysheet.pk}).csv',
                'body': registry,
                'mime_type': ('text', 'csv')
            },
        )

    try:
        wb_selfemployed, no_registry_se_total = paysheet_xls_self_employed_another_account(
            paysheet,
            workers_presence_required=True
        )
    except NoDataError:
        pass
    else:
        xls_selfemployed = io.BytesIO()
        wb_selfemployed.save(xls_selfemployed)
        text_body.append(f'Самозанятые Точка: {no_registry_se_total} руб.')
        attachments.append(
            {
                'filename': f'{paysheet} (только СЗ).xls',
                'body': xls_selfemployed.getvalue(),
                'mime_type': ('application', 'vnd.ms-excel')
            },
        )
    if not attachments:
        raise NoDataError

    send_email(
        cashier_emails,
        f'{paysheet}',
        '\n'.join(text_body),
        attachment=attachments
    )


@require_POST
@staff_account_required
def email_paysheet(request, pk):
    paysheet = Paysheet_v2.objects.get(pk=pk)
    try:
        do_email_paysheet(paysheet)
    except Group.DoesNotExist:
        return JsonResponse({}, status=400)
    except NoDataError:
        return JsonResponse({}, status=400)
    return JsonResponse({})


@require_POST
@user_passes_test(lambda user: user.is_superuser)
def make_payments_with_talk_bank(request, pk):
    make_paysheet_payments_with_talk_bank(request.user.pk, pk)
    return HttpResponse()


@require_POST
@user_passes_test(lambda user: user.is_superuser)
def create_paysheets_for_outstanding_requests(request):
    form = forms.AccountablePersonForm(data=request.POST, field_name='accountable_person')
    if form.is_valid():
        accountable_person = form.cleaned_data['accountable_person']
        created_paysheets = services.paysheet.create_paysheets_for_outstanding_requests(
            author=request.user,
            accountable_person=accountable_person,
        )
        for paysheet in created_paysheets:
            do_email_paysheet(paysheet)
    # todo visible effect
    return redirect('the_redhuman_is:paysheet_v2_list')


@require_POST
@user_passes_test(lambda user: user.is_superuser)
def bulk_create_paysheets(request):
    form = forms.AccountablePersonForm(data=request.POST, field_name='accountable_person')
    if form.is_valid():
        accountable_person = form.cleaned_data['accountable_person']
        created_paysheets = services.paysheet.bulk_create_paysheets(
            author=request.user,
            accountable_person=accountable_person,
        )

        # Auto sending emails is disabled now
        # Todo: enable someday
#        for paysheet in created_paysheets:
#            do_email_paysheet(paysheet)

    # Todo: visible effect
    return redirect('the_redhuman_is:paysheet_v2_list')


def _title(operation, worker_account):
    TITLES = [
        (models.CustomerFine, 'Штраф'),
        (models.RkoOperation, 'РКО'),
        (models.TurnoutBonus, 'Бонус (с выходом)'),
        (models.TurnoutDeduction, 'Вычет (с выходом)'),
        (models.TurnoutOperationIsPayed, 'Выплата за выходы'),
        (models.TurnoutOperationToPay, 'Начисление за выход'),
        (models.WorkerBonus, 'Бонус'),
        (models.WorkerDeduction, 'Вычет'),
        (models.WorkerPrepayment, 'Аванс'),
    ]

    for model, title in TITLES:
        if model.objects.filter(operation=operation).exists():
            return title

    if operation.debet == worker_account:
        return 'Счет клиента - дебет'

    if operation.credit == worker_account:
        return 'Счет клиента - кредит'

    return 'Непонятная операция, сообщите Алексею'


def _annotate_operations(operations, worker_account):
    return [{'title': _title(o, worker_account), 'operation': o} for o in operations]


@staff_account_required
def day_details(request, paysheet_pk, worker_pk, date):
    paysheet = Paysheet_v2.objects.get(pk=paysheet_pk)
    worker = models.Worker.objects.get(pk=worker_pk)
    date = date_from_string(date)

    account = worker.worker_account.account

    # Todo: wtf?
    debet_operations, credit_operations = paysheet.account_operations(
        account.pk,
        date
    )
    operations = debet_operations.union(
        credit_operations
    )

    return render(
        request,
        'the_redhuman_is/paysheet_v2/day_details.html',
        {
            'readonly': not request.user.is_superuser,
            'worker': worker,
            'date': date,
            'show_edit_block': False,
            'paysheet': paysheet,
            'operations': _annotate_operations(operations, account),
        }
    )


@require_POST
@staff_account_required
@close_paysheet_permission_required
def add_image(request, pk):
    paysheet = Paysheet_v2.objects.get(pk=pk)

    images = sorted(
        request.FILES.getlist('image'),
        key=lambda img: str(img),
    )

    for image in images:
        models.add_photo(paysheet, image)

    return redirect('the_redhuman_is:paysheet_v2_show', pk=pk)


@require_POST
@close_paysheet_permission_required
def add_registry(request, pk):
    paysheet = Paysheet_v2.objects.get(pk=pk)

    do_add_registry(paysheet, request.FILES.get('registry'), request.user)

    return redirect('the_redhuman_is:paysheet_v2_show', pk=pk)


@require_POST
@staff_account_required
@close_paysheet_permission_required
@transaction.atomic
def update_amounts(request, pk):
    paysheet = Paysheet_v2.objects.get(pk=pk)
    if not paysheet.is_closed:
        amount_rx = re.compile('^amount_(\d+)$')
        for key, value in request.POST.items():
            m = amount_rx.match(key)
            if m:
                entry = paysheet.paysheet_entries.get(
                    worker__pk=m.group(1)
                )
                entry.update_amount(get_decimal(value))

    return redirect('the_redhuman_is:paysheet_v2_show', pk=pk)


@require_POST
@staff_account_required
@close_paysheet_permission_required
def close(request, pk):
    paysheet = Paysheet_v2.objects.get(pk=pk)
    if not paysheet.ready_to_close():
        # Todo: some message or redirection.
        raise Exception(
            'Нельзя закрыть ведомость, пока в ней есть работники, '
            'у которых сальдо на интервале ведомости отрицательно, '
            'либо больше, чем остаток на счете. И пока нет фоток.'
        )

    paysheet.close_with_default_payment_account(request.user)

    return redirect('the_redhuman_is:paysheet_v2_list')


def _style():
    style = xlwt.XFStyle()
    style.borders = xlwt.Borders()
    border = 7 # 'hair' style
    style.borders.left = border
    style.borders.right = border
    style.borders.top = border
    style.borders.bottom = border
    return style


def _bold_style():
    style = _style()
    style.font.bold = True
    style.font.height = 220
    style.alignment.wrap = xlwt.Formatting.Alignment.WRAP_AT_RIGHT
    style.alignment.vert = xlwt.Formatting.Alignment.VERT_CENTER
    return style


def _write_paysheet_header(worksheet, paysheet, col_num):
    title_font = _bold_style()

    worksheet.row(0).height_mismatch = True
    worksheet.row(0).height = 540
    worksheet.merge(0, 0, 0, col_num)
    worksheet.merge(1, 1, 0, 1)
    worksheet.merge(1, 1, 2, col_num)
    for i in range(col_num):
        worksheet.write(0, i + 1, None, title_font)
        worksheet.write(1, i + 1, None, title_font)

    worksheet.write(0, 0, str(paysheet), title_font)

    worksheet.row(1).height_mismatch = True
    worksheet.row(1).height = 300
    worksheet.write(1, 0, 'Подотчетное лицо:', title_font)
    accountable_person = models.get_accountable_person(paysheet) or ''
    worksheet.write(1, 2, str(accountable_person), title_font)


def _write_workers_header(worksheet, paysheet, merge=False, numbers=True):
    bold_font = _bold_style()
    row_num = 2
    col_num = 0

    worksheet.row(row_num).height_mismatch = True
    worksheet.row(row_num).height = 300

    if merge:
        worksheet.merge(row_num, row_num + 1, col_num, col_num)
    if numbers:
        worksheet.write(row_num, col_num, '№', bold_font)
        worksheet.col(col_num).width = 800
        col_num += 1

    worksheet.write(row_num, col_num, 'Рабочий', bold_font)
    worksheet.col(col_num).width = 9100
    if merge:
        worksheet.merge(row_num, row_num + 1, col_num, col_num)
    col_num += 1

    return row_num, col_num


def _add_total_sheet(workbook, title, paysheet, first_index, workers):
    ws = workbook.add_sheet(title, cell_overwrite_ok=True)
    ws.set_header_str(''.encode('utf-8'))
    ws.set_footer_str(''.encode('utf-8'))

    row_num, col_num = _write_workers_header(ws, paysheet)

    bold_font = _style()
    bold_font.font.bold = True
    bold_font.font.height = 220
    bold_font.alignment.horz = xlwt.Formatting.Alignment.HORZ_CENTER
    bold_font.alignment.vert = xlwt.Formatting.Alignment.VERT_CENTER

#    ws.write(row_num, col_num, 'Залог', bold_font)
    ws.col(col_num).width = 2900
    col_num += 1

    ws.write(row_num, col_num, '', bold_font)
#    ws.write(row_num, col_num, 'Остаток', bold_font)
    ws.col(col_num).width = 2900
    col_num += 1

    ws.write(row_num, col_num, 'Выплатить', bold_font)
    ws.col(col_num).width = 3200
    col_num += 1

    ws.write(row_num, col_num, '', bold_font)
    ws.col(col_num).width = 1000
    col_num += 1

    ws.write(row_num, col_num, 'Подпись', bold_font)
    ws.col(col_num).width = 5000

    _write_paysheet_header(ws, paysheet, col_num)

    regular_font = _style()
    regular_font.alignment.vert = xlwt.Formatting.Alignment.VERT_CENTER

    currency_style = _bold_style()
    currency_style.font.height = 320

    for i in range(len(workers)):
        row_num += 1
        col_num = 0

        ws.row(row_num).height_mismatch = True
        ws.row(row_num).height = 450

        worker = workers[i]

        ws.write(row_num, col_num, first_index + i + 1, regular_font)
        col_num += 1

        ws.write(row_num, col_num, str(worker), regular_font)
        col_num += 1

        # Todo: remove this line, uncomment next block.
        ws.write(row_num, col_num, '', currency_style)
#        deposit_amount = models.deposit.get_deposit_amount(worker)
#        ws.write(row_num, col_num, deposit_amount, currency_style)
        col_num += 1

        # Todo: remove this line, uncomment next block.
        ws.write(row_num, col_num, '', currency_style)
#        saldo = -1 * worker.worker_account.account.turnover_saldo()
#        ws.write(row_num, col_num, saldo, currency_style)
        col_num += 1

        amount = paysheet.amount(worker)
        ws.write(row_num, col_num, amount, currency_style)
        col_num += 1

        ws.write(row_num, col_num, '', regular_font)
        col_num += 1

        ws.write(row_num, col_num, '', regular_font)

    return ws, row_num


def _add_details_sheets(workbook, title_prefix, paysheet, first_index, workers):
    MAX_DAYS_IN_PAYSHEET = 9
    first_day = paysheet.first_day
    last_day = paysheet.last_day
    days = days_from_interval(first_day, last_day)
    sheet_count = math.ceil(len(days) / MAX_DAYS_IN_PAYSHEET)
    sheets = []
    font_style = _style()
    for sheet_index in range(sheet_count):
        begin = sheet_index * MAX_DAYS_IN_PAYSHEET
        end = min(begin + MAX_DAYS_IN_PAYSHEET, len(days))
        ws = workbook.add_sheet(
            '{}, {}-{}'.format(
                title_prefix,
                days[begin].strftime('%d.%m'),
                days[end-1].strftime('%d.%m')
            ),
            cell_overwrite_ok=True
        )
        row_num, col_num =_write_workers_header(ws, paysheet, merge=True)
        weekdays = ['пн', 'вт', 'ср', 'чт', 'пт', 'сб', 'вс']
        for day in days[begin:end]:
            ws.write(row_num, col_num, day.strftime('%d.%m'), font_style)
            ws.write(row_num + 1, col_num, weekdays[day.weekday()], font_style)
            col_num += 1

        _write_paysheet_header(ws, paysheet, col_num - 1)

        sheets.append(ws)

    font_style.font.bold = False
    row_num = 4
    for i in range(len(workers)):
        worker = workers[i]
        calendar = _worker_row_for_paysheet(paysheet, worker)
        expanded_calendar = [calendar.get(d) for d in days]
        for sheet_index in range(sheet_count):
            col_num = 0
            ws = sheets[sheet_index]

            ws.set_portrait(False)
            ws.set_header_str(''.encode('utf-8'))
            ws.set_footer_str(''.encode('utf-8'))

            ws.write(row_num, col_num, first_index + i + 1, font_style)
            col_num += 1

            ws.write(row_num, col_num, str(worker), font_style)
            col_num += 1

            begin = sheet_index * MAX_DAYS_IN_PAYSHEET
            end = min(begin + MAX_DAYS_IN_PAYSHEET, len(days))

            first_col = col_num

            for cell in expanded_calendar[begin:end]:
                value = ''
                if ws.col(col_num).width != 2750:
                    ws.col(col_num).width = 1400
                if cell:
                    debet = cell.get('debet', 0)
                    credit = cell.get('credit', 0)
                    if debet > 0 and credit > 0:
                        value = '{}/{}'.format(int(credit), int(debet))
                        ws.col(col_num).width = 2750
                    else:
                        value = credit - debet
                ws.write(row_num, col_num, value, font_style)
                col_num += 1

            # Увеличиваем первую колонку с детализацией,
            # чтобы в ячеку с подотчетным лицом влезло имя
            cols = end - begin
            if cols < 8:
                ws.col(first_col).width = 1400 * (9 - cols)

        row_num += 1

    return sheets


def _add_operations_sheet(workbook, title, paysheet, first_index, operations):
    worksheet = workbook.add_sheet(title, cell_overwrite_ok=True)
    worksheet.set_header_str(''.encode('utf-8'))
    worksheet.set_footer_str(''.encode('utf-8'))

    title_style = _bold_style()
    title_style.alignment.horz = xlwt.Formatting.Alignment.HORZ_CENTER
    row_num, col_num = _write_workers_header(worksheet, paysheet, numbers=False)
    worksheet.col(0).width = 6500

    worksheet.write(row_num, col_num, 'Дата', title_style)
    worksheet.col(col_num).width = 2000
    col_num += 1
    worksheet.write(row_num, col_num, 'Вычет', title_style)
    worksheet.col(col_num).width = 2500
    col_num += 1
    worksheet.write(row_num, col_num, 'Комментарий', title_style)
    worksheet.col(col_num).width = 14000
    _write_paysheet_header(worksheet, paysheet, col_num)

    row_num += 1
    font_style = _style()
    font_style.alignment.wrap = xlwt.Formatting.Alignment.WRAP_AT_RIGHT
    font_style.alignment.vert = xlwt.Formatting.Alignment.VERT_CENTER

    comment_style = _style()
    comment_style.alignment.wrap = xlwt.Formatting.Alignment.WRAP_AT_RIGHT
    comment_style.alignment.vert = xlwt.Formatting.Alignment.VERT_CENTER
    comment_style.font.height = 150

    currency_style = _bold_style()
    currency_style.font.height = 320
    for operation in operations:
        col_num = 0

        worksheet.row(row_num).height_mismatch = True
        worksheet.row(row_num).height = 550

        value = str(operation.debet.worker_account.worker)
        worksheet.write(row_num, col_num, value, font_style)
        col_num += 1

        worksheet.write(row_num, col_num, operation.timepoint.strftime('%d.%m.%y'), font_style)
        col_num += 1

        worksheet.write(row_num, col_num, operation.amount, currency_style)
        col_num += 1

        worksheet.write(row_num, col_num, operation.comment, comment_style)
        col_num += 1

        row_num += 1


# Todo: use _get_paysheet_content() or it's basics
def paysheet_xls_normal(paysheet, workers_presence_required=False):
    workers = paysheet.workers(
    ).with_is_selfemployed(
    ).filter(
        is_selfemployed=False
    )

    if workers_presence_required and not workers.exists():
        raise NoDataError

    wb = xlwt.Workbook(encoding='utf-8')
    MAX_WORKERS_IN_SHEET_PORTRAIT = 30

    row_num = 0
    portrait_count = (math.ceil(len(workers) / MAX_WORKERS_IN_SHEET_PORTRAIT)) or 1
    for sheet_index in range(portrait_count):
        begin = sheet_index * MAX_WORKERS_IN_SHEET_PORTRAIT
        end = min(begin + MAX_WORKERS_IN_SHEET_PORTRAIT, len(workers))
        ws, row_num = _add_total_sheet(
            wb,
            'Итого с {} по {}'.format(begin + 1, end),
            paysheet,
            begin,
            workers[begin:end],
        )

    font_style = _style()
    font_style.font.bold = True
    font_style.font.height = 320
    row_num += 1
    ws.merge(row_num, row_num, 0, 3)
    font_style.alignment.horz = xlwt.Formatting.Alignment.HORZ_RIGHT
    ws.write(row_num, 0, 'Итого', font_style)
    ws.write(row_num, 1, '', font_style)
    ws.row(row_num).height_mismatch = True
    ws.row(row_num).height = 450
    ws.write(row_num, 4, paysheet.normal_workers_total_amount, font_style)

    MAX_WORKERS_IN_SHEET_ALBUM = 34
    album_count = math.ceil(len(workers) / MAX_WORKERS_IN_SHEET_ALBUM)
    for sheet_index in range(album_count):
        begin = sheet_index * MAX_WORKERS_IN_SHEET_ALBUM
        end = min(begin + MAX_WORKERS_IN_SHEET_ALBUM, len(workers))
        _add_details_sheets(
            wb,
            '{}-{}'.format(begin + 1, end),
            paysheet,
            begin,
            workers[begin:end],
        )

    MAX_OPERATIONS_IN_SHEET_PORTRAIT = 25
    operations = finance.models.Operation.objects.filter(
        debet__worker_account__worker__in=workers,
        timepoint__date__gte=paysheet.first_day
    ).select_related(
        'debet'
    ).order_by(
        'debet__worker_account__worker',
        'timepoint'
    )
    operation_sheet_count = math.ceil(len(operations) / MAX_OPERATIONS_IN_SHEET_PORTRAIT)
    for sheet_index in range(operation_sheet_count):
        begin = sheet_index * MAX_OPERATIONS_IN_SHEET_PORTRAIT
        end = min(begin + MAX_OPERATIONS_IN_SHEET_PORTRAIT, len(operations))
        title = 'Списания-{}'.format(sheet_index + 1)
        _add_operations_sheet(
            wb,
            title,
            paysheet,
            begin,
            operations[begin:end]
        )

    return wb, paysheet.normal_workers_total_amount


class NoDataError(Exception):
    pass


def paysheet_xls_self_employed_another_account(paysheet, workers_presence_required=False):
    workers = paysheet.workers(
    ).with_is_selfemployed(
    ).with_full_name(
    ).with_cardholder_name(
    ).filter(
        is_selfemployed=True,
    # Если ФИО держателя карты отличается от ФИО работника - счет не его,
    # и он попадает в отдельный файл на ручную обработку
    ).annotate(
        uppercase_cardholder=Upper('cardholder_name')
    ).exclude(
        uppercase_cardholder=Upper('full_name')
    ).with_selfemployment_data(
        more=True
    ).order_by(
        'full_name',
    )

    if workers_presence_required and not workers.exists():
        raise NoDataError

    wb = xlwt.Workbook(encoding='utf-8')
    ws = wb.add_sheet('самозанятым в оплату', cell_overwrite_ok=True)
    title_font = _bold_style()
    titles = [
        ('ФИО', 9000),
        ('ФИО держателя карты', 9000),
        ('ИНН', 3500),
        ('Р/С', 5500),
        ('Банк', 9000),
        ('Бик', 3000),
        ('К/С', 5500),
        ('Сумма', 2000),
    ]
    for i, (title, width) in enumerate(titles):
        ws.write(0, i, title, title_font)
        ws.col(i).width = width

    total_sum = decimal.Decimal(0)
    for i, worker in enumerate(workers):
        row = i + 1
        data = worker.wse
        worker_amount = paysheet.amount(worker)
        total_sum += worker_amount
        for col, value in enumerate([
            str(worker),
            data['cardholder_name'],
            data['tax_number'],
            data['bank_account'],
            data['bank_name'],
            data['bank_identification_code'],
            data['correspondent_account'],
            worker_amount,
        ]):
            ws.write(row, col, value)
    return wb, total_sum


def get_csv_registry(workers, payment_date):
    header = (
        'Фамилия;'
        'Имя;'
        'Отчество;'
        'ИНН;'
        'Дата учета дохода;'
        'Сумма дохода;'
        'Номер лицевого счета самозанятого;'
        'БИК Банка;'
        'Наименование услуги;'
        'ИНН Заказчика;'
        'Полное наименование заказчика;'
    )

    org_name = 'ООО "ГЕТТАСК"'
    org_tax_code = '5029258192'
    income_date = string_from_date(payment_date)

    rows = []
    total_sum = decimal.Decimal(0)

    for worker in workers:
        total_sum += worker.amount
        row = [
            worker.last_name,
            worker.name,
            worker.patronymic or '',
            worker.wse['tax_number'],
            income_date,
            str(worker.amount),
            worker.wse['bank_account'],
            worker.wse['bank_identification_code'],
            get_service_name(
                worker.paysheet_workdays['start'],
                worker.paysheet_workdays['end']
            ),
            org_tax_code,
            org_name
        ]
        rows.append(';'.join(row) + ';')

    return '\n'.join([header] + rows).encode('cp1251'), total_sum


def paysheet_csv_self_employed_normal(paysheet, workers_presence_required=False):
    workers = paysheet.workers(
    ).with_is_selfemployed(
    ).with_selfemployment_data(
    ).with_has_registry_receipt(
        paysheet
    ).with_full_name(
        upper=True
    ).with_cardholder_name(
        upper=True
    ).filter(
        has_registry_receipt=False,
        is_selfemployed=True,
        # Если ФИО держателя карты совпадает с ФИО работника -
        # можно пробовать платить/собирать чеки в автоматическом режиме
        cardholder_name=F('full_name')
    ).with_paysheet_workdays(
        paysheet.pk,
    ).annotate(
        amount=Subquery(
            Paysheet_v2Entry.objects.filter(
                paysheet=paysheet,
                worker=OuterRef('pk')
            ).values(
                'amount'
            ),
            output_field=DecimalField()
        )
    ).order_by(
        'full_name',
    )

    if workers_presence_required and not workers.exists():
        raise NoDataError

    registry_num = models.PaysheetRegistry.objects.filter(
        paysheet=paysheet
    ).order_by(
        'registry_num_id'
    ).last(
    ).registry_num_id

    csv_registry, total_sum = get_csv_registry(
        workers,
        timezone.localdate(paysheet.timestamp),
    )
    return csv_registry, total_sum, registry_num


def paysheet_receipts(request, pk):
    paysheet = Paysheet_v2.objects.get(pk=pk)
    receipt_photos = paysheet_receipt_photos(paysheet)

    proxy_file = io.BytesIO()
    with ZipFile(proxy_file, 'w') as zip_file:
        for photo in receipt_photos:
            path = photo.image.path
            with open(path, 'rb') as image_content:
                zip_file.writestr(
                    os.path.basename(path),
                    image_content.read()
                )

    response = HttpResponse(content_type='application/zip')
    response[
        'Content-Disposition'
    ] = "attachment; filename*=UTF-8''{}".format(
        '{}.zip'.format(quote(f'Чеки из ведомости №{paysheet.pk}'))
    )
    response.write(proxy_file.getvalue())

    return response

def talk_bank_payment_report(request, pk):
    report = get_paysheet_payment_report(pk)
    return xlsx_content_response(report, f'{pk}_report.xlsx')
