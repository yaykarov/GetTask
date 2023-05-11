# -*- coding: utf-8 -*-

import io

from crispy_forms.helper import FormHelper
from crispy_forms.layout import (
    Field,
    Layout,
    Row,
)

from dal.autocomplete import Select2QuerySetView

from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import user_passes_test
from django.contrib.contenttypes.models import ContentType

from django.core.exceptions import (
    ObjectDoesNotExist,
    PermissionDenied,
    ValidationError,
)

from django.http import HttpResponse
from django.shortcuts import (
    redirect,
    render
)
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from django.db.models import (
    Exists,
    OuterRef,
    Q,
    Sum,
    TextField,
)

from django.db.models.functions import Cast

from doc_templates.doc_factory import delivery_worker_list_pdf

from the_redhuman_is import (
    forms,
    models
)

from the_redhuman_is.forms import ReconciliationCreateForm
from the_redhuman_is.models import (
    Photo,
    WorkerTurnout
)
from the_redhuman_is.models.paysheet_v2 import WorkerReceipt
from the_redhuman_is.models.reconciliation import ReconciliationInvoice

from the_redhuman_is.services.paysheet import paysheet_receipts

from the_redhuman_is.views.filters import ReconciliationFilter

from utils.date_time import (
    day_month_year,
    days_from_interval,
    string_from_date,
)
from utils.forms import SubmitNoValue
from utils.functools import strtobool
from utils.img_cut import hide_all_if_check

from urllib.parse import quote
from zipfile import ZipFile


class UnpaidReconciliationAutocomplete(LoginRequiredMixin, Select2QuerySetView):
    def get_queryset(self):
        reconciliations = models.Reconciliation.objects.all(
        ).with_invoice_number(
        ).with_status(
        ).filter(
            status_='in_payment'
        ).order_by('-pk')
        if self.q:
            reconciliations = reconciliations.annotate(
                pk_str=Cast('pk', TextField())
            ).filter(
                Q(pk_str__icontains=self.q) |
                Q(customer__cust_name__icontains=self.q) |
                Q(invoice_number__icontains=self.q)
            )
        return reconciliations

    def get_result_label(self, result):
        return '№{}, {}, счет "{}" на {}р. с {} по {}'.format(
            result.pk,
            result.customer.cust_name,
            result.invoice_number,
            result.sum_total,
            string_from_date(result.first_day),
            string_from_date(result.last_day)
        )


def _can_create_delete_reconciliation(user):
    return user.is_superuser or user.groups.filter(name='Касса').exists()


@require_POST
@user_passes_test(_can_create_delete_reconciliation)
def remove(request, pk):
    reconciliation = models.Reconciliation.objects.get(pk=pk)
    if not reconciliation.is_closed:
        reconciliation.delete()
    return redirect('the_redhuman_is:reconciliation_list')


def list_recons(request):
    # Todo: different view for creation!
    user_can_create_reconciliation = _can_create_delete_reconciliation(request.user)
    if request.method == 'POST':
        if not user_can_create_reconciliation:
            raise Exception('Нет прав на создание сверки.')

        form = ReconciliationCreateForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            try:
                if data['create_for_each']:
                    models.reconciliation.bulk_create_reconciliations(
                        request.user,
                        data['customer'],
                        data['last_day'],
                    )
                    return redirect(f'{reverse("the_redhuman_is:reconciliation_list")}?{request.GET.urlencode()}')
                else:
                    reconciliation = models.reconciliation.create_reconciliation(
                        request.user,
                        data['customer'],
                        data['location'],
                        None,
                        data['last_day'],
                    )
                    return redirect('the_redhuman_is:reconciliation_show', pk=reconciliation.pk)
            except ValidationError as e:
                form.add_error('last_day', e)
                creation_form = form
        else:
            creation_form = form
    else:
        try:
            for_customer = int(request.GET.get('create_for_customer'))
        except (TypeError, ValueError):
            for_customer = None
        if for_customer is not None:
            creation_form = forms.ReconciliationCreateForm(initial={'customer': for_customer})
        else:
            creation_form = forms.ReconciliationCreateForm()
    reconciliations_qs = models.Reconciliation.objects.select_related(
        'customer',
        'location',
        'invoice',
    ).with_total_sum(
    ).with_is_ready_to_close(
    ).with_deadline(
    ).with_status(
    ).with_payment_date(
    ).with_legal_entity(
    ).with_suspension_date(
    )
    f = ReconciliationFilter(request.GET, queryset=reconciliations_qs)
    helper = FormHelper()
    helper.form_method = 'GET'
    helper.disable_csrf = True
    helper.layout = Layout(
        Row(
            Field('filter_customer', css_class='form-control form-control-sm'),
            Field('date_range', css_class='form-control form-control-sm'),
            Field('is_unpaid', css_class='form-control form-control-sm'),
            Field('is_closed', css_class='form-control form-control-sm'),
            SubmitNoValue(
                'submit-search',
                'Показать',
                css_class='btn-sm btn-action btn-outline-primary'
            ),
            css_class='form-inline mb-0 form-row'
        )
    )
    f.form.helper = helper

    helper = FormHelper()
    helper.form_show_errors = False
    helper.layout = Layout(
        Row(
            Field('customer', css_class='form-control form-control-sm'),
            Field('location', css_class='form-control form-control-sm'),
            Field('last_day', css_class='form-control form-control-sm'),
            css_class='mt-0 mb-0'
        ),
        Row(
            Field('create_for_each', css_class='form-control form-control-sm'),
            css_class='mt-0 mb-0'
        ),
        Row(
            SubmitNoValue(
                'submit-create',
                'Начать сверку',
                css_class='btn-sm btn-action btn-outline-primary',
            ),
            css_class='mt-0 mb-0'
        )
    )
    helper.attrs = {'id': 'createReconciliationForm', 'target': '_blank'}
    creation_form.helper = helper
    total = f.qs.aggregate(Sum('sum_total_'))['sum_total___sum']
    return render(
        request,
        'the_redhuman_is/reconciliation/list.html',
        {
            'creation_form': creation_form,
            'filter': f,
            'reconciliations': f.qs,
            'total': total,
            'today': timezone.localdate(),
            'can_create_delete': user_can_create_reconciliation,
        }
    )


def show(request, pk):
    reconciliation = models.Reconciliation.objects.select_related(
        'invoice'
    ).get(pk=pk)
    customer = reconciliation.customer

    legal_entities = models.intersected_legal_entities(
        customer,
        reconciliation.first_day,
        reconciliation.last_day
    )

    customer_operating_accounts = models.CustomerOperatingAccounts.objects.get(
        customer=customer
    )
    accounts = [
        customer_operating_accounts.account_76_sales,
        customer_operating_accounts.account_76_debts,
        customer_operating_accounts.account_76_fines,
        customer_operating_accounts.account_62_root,
        customer_operating_accounts.account_90_2_root,
    ]
    for service_accounts in customer.customerservice_set.all():
        accounts.append(service_accounts.account_90_1)

    delivery_requests = models.DeliveryRequest.objects.with_customer_resolution(
    ).filter(
        date__range=(reconciliation.first_day, reconciliation.last_day),
        customer=customer,
    )
    if reconciliation.location_id:
        delivery_requests = delivery_requests.filter(location=reconciliation.location_id)
    suspicious_requests = delivery_requests.filter(customer_resolution='suspicious')
    normal_requests = delivery_requests.filter(customer_resolution='normal')
    try:
        invoice_initial = {
            'number': reconciliation.invoice.number,
            'date': reconciliation.invoice.date,
        }
    except ReconciliationInvoice.DoesNotExist:
        invoice_initial = {}

    invoice_form = forms.ReconciliationInvoiceForm(initial=invoice_initial)
    legal_entity = legal_entities.first().legal_entity if legal_entities.first() else None
    operations_blocked = reconciliation.customer_operations(
    ).filter(
        is_closed=True
    ).exists()
    user_can_block = (
        request.user.is_superuser or
        request.user.groups.filter(name='Касса').exists()
    )

    return render(
        request,
        'the_redhuman_is/reconciliation/show.html',
        {
            'reconciliation': reconciliation,
            'invoice_form': invoice_form,
            'suspicious_requests_count': suspicious_requests.count(),
            'normal_requests_count': normal_requests.count(),
            'legal_entity': legal_entity,
            'operations_blocked': operations_blocked,
            'user_can_block': user_can_block,
            'accounts': accounts,
            'photos': models.get_photos(reconciliation),
        }
    )


def photos(request, pk):
    reconciliation = models.Reconciliation.objects.get(pk=pk)

    return render(
        request,
        'the_redhuman_is/reports/photos_list_no_menu.html',
        {
            'amount': reconciliation.sum_total,
            'photos': models.get_photos(reconciliation)
        }
    )


@require_POST
def add_image(request, pk):
    reconciliation = models.Reconciliation.objects.get(pk=pk)

    images = sorted(
        request.FILES.getlist('image'),
        key=lambda img: str(img),
    )

    for image in images:
        models.add_photo(reconciliation, image)

    return redirect('the_redhuman_is:reconciliation_show', pk=reconciliation.pk)


@require_POST
@user_passes_test(lambda user: user.is_superuser)
def close(request, pk):
    reconciliation = models.Reconciliation.objects.get(pk=pk)

    legal_entity = models.LegalEntity.objects.get(pk=request.POST['legal_entity'])

    reconciliation.close(request.user, legal_entity)

    return redirect('the_redhuman_is:reconciliation_show', pk=reconciliation.pk)


@require_POST
@user_passes_test(lambda user: user.is_superuser or user.groups.filter(name='Касса').exists())
def block_operations(request, pk):
    reconciliation = models.Reconciliation.objects.get(pk=pk)
    if reconciliation.is_closed:
        raise PermissionDenied('Нельзя редактировать операции в закрытой сверке.')
    block = strtobool(request.POST['block'])
    reconciliation.customer_operations(
    ).update(
        is_closed=block
    )
    return redirect('the_redhuman_is:reconciliation_show', pk=reconciliation.pk)


@require_POST
def set_invoice(request, pk):
    reconciliation = models.Reconciliation.objects.get(pk=pk)
    form = forms.ReconciliationInvoiceForm(request.POST)
    if form.is_valid():
        ReconciliationInvoice.objects.update_or_create(
            reconciliation=reconciliation,
            defaults=form.cleaned_data
        )
    return redirect('the_redhuman_is:reconciliation_show', pk=reconciliation.pk)


def _worker_lists(reconciliation):
    for date in days_from_interval(reconciliation.first_day, reconciliation.last_day):
        d, m, y = day_month_year(date)
        workers = models.Worker.objects.filter(
            worker_turnouts__timesheet__in=reconciliation.timesheets().filter(sheet_date=date)
        ).distinct(
        ).with_full_name(
        ).order_by(
            'full_name'
        )

        if workers.exists():
            yield date, delivery_worker_list_pdf(d, m, y, [w.full_name for w in workers])


class ReceiptWithNoPhotoError(Exception):
    pass


def _checks(reconciliation):
    turnouts = reconciliation.turnouts()
    paysheets = models.Paysheet_v2.objects.filter(
        paysheet_entries__paysheet_entry_operations__operation__turnoutoperationtopay__turnout__in=turnouts
    ).distinct()

    for paysheet in paysheets:
        for photo in models.get_photos(paysheet):
            if not photo:
                continue

            cut_img = hide_all_if_check(photo.image.path)
            if cut_img is not None:
                yield cut_img

        turnouts_in_reconciliation_qs = WorkerTurnout.objects.filter(
            worker=OuterRef('worker'),
            timesheet__sheet_date__gte=reconciliation.first_day,
            timesheet__sheet_date__lte=reconciliation.last_day,
            timesheet__customer=reconciliation.customer_id,
        )
        if reconciliation.location_id is not None:
            turnouts_in_reconciliation_qs = turnouts_in_reconciliation_qs.filter(
                timesheet__cust_location=reconciliation.location_id,
            )
        receipt_pks = set(
            paysheet_receipts(
                paysheet
            ).annotate(
                is_in_reconciliation=Exists(
                    turnouts_in_reconciliation_qs
                )
            ).filter(
                is_in_reconciliation=True
            ).values_list('pk', flat=True)
        )
        receipt_photos = Photo.objects.filter(
            content_type=ContentType.objects.get_for_model(WorkerReceipt),
            object_id__in=receipt_pks
        )
        photo_receipt_ids = set(photo.object_id for photo in receipt_photos)
        if receipt_pks != photo_receipt_ids:
            raise ReceiptWithNoPhotoError(f'Нет фото у чеков {receipt_pks - photo_receipt_ids}.')
        for photo in receipt_photos:
            cut_img = hide_all_if_check(photo.image.path)
            if cut_img is None:
                raise ReceiptWithNoPhotoError(f'Битое фото у чека {photo.object_id}.')
            yield cut_img


# Todo: need some refactoring vvv

# Todo: notification?
def _contracts(reconciliation):
    turnouts = reconciliation.turnouts()
    workers = models.Worker.objects.filter(
        worker_turnouts__in=turnouts
    ).with_full_name(
    ).annotate(
        has_actual_wse=Exists(
            models.WorkerSelfEmploymentData.objects.filter(
                deletion_ts__isnull=True,
                worker=OuterRef('pk')
            )
        )
    ).filter(
        has_actual_wse=False
    ).distinct()

    for worker in workers:
        last_turnout = turnouts.filter(
            worker=worker
        ).select_related(
            'timesheet'
        ).order_by(
            'timesheet__sheet_date'
        ).last()

        contract = worker.contract.filter(
            Q(begin_date__isnull=True) | Q(end_date__gt=last_turnout.timesheet.sheet_date),
        ).order_by(
            '-is_actual',
            'end_date'
        ).first()

        if contract is None:
            yield f'!Нет договора {worker.full_name}', ['']
            continue

        paths = [p.image.path for p in models.get_photos(contract)]
        for img in [contract.image, contract.image2, contract.image3]:
            if img:
                paths.append(img.path)

        try:
            notification = models.NoticeOfContract.objects.get(contract=contract)
            paths += [p.image.path for p in models.get_photos(notification)]

        except ObjectDoesNotExist:
            yield f'!Нет уведомления {worker.full_name}', ['']

        images = []
        for path in paths:
            with open(path, 'rb') as image_content:
                images.append(image_content.read())

        if len(images) == 0:
            yield f'!Нет сканов договора {worker.full_name}', ['']
            continue

        yield worker.full_name, images


def _passports(reconciliation):
    workers = models.Worker.objects.filter(
        worker_turnouts__in=reconciliation.turnouts()
    ).with_full_name(
    ).distinct(
    )

    for worker in workers:
        passport = worker.actual_passport
        if passport is None:
            yield f'!Нет паспорта {worker.full_name}', ['']
            continue

        paths = [p.image.path for p in models.get_photos(passport)]
        images = []
        for path in paths:
            with open(path, 'rb') as image_content:
                images.append(image_content.read())

        if len(images) == 0:
            yield f'!Нет сканов паспорта {worker.full_name}', ['']
            continue

        yield worker.full_name, images


def _migration_cards(reconciliation):
    workers = models.Worker.objects.filter(
        worker_turnouts__in=reconciliation.turnouts()
    ).with_full_name(
    ).distinct(
    )

    for worker in workers:
        if worker.citizenship_name in ['РФ']:
            continue

        try:
            migration_card = models.WorkerMigrationCard.objects.get(worker=worker)
            paths = [p.image.path for p in models.get_photos(migration_card)]

            images = []
            for path in paths:
                with open(path, 'rb') as image_content:
                    images.append(image_content.read())

            if len(images) == 0:
                yield f'!Нет сканов миграционки {worker.full_name}', ['']
                continue

        except ObjectDoesNotExist:
            yield f'!Нет миграционки {worker.full_name}', ['']

        yield worker.full_name, images


def extra_documents(request, pk):
    reconciliation = models.Reconciliation.objects.get(pk=pk)

    # Todo: move to some utils?
    proxy_file = io.BytesIO()
    with ZipFile(proxy_file, 'w') as zip_file:

        def _add_images(prefix, items):
            for name, images in items:
                for i, image in enumerate(images):
                    suffix = f' {i + 1}' if len(images) > 1 else ''
                    if len(image) > 0:
                        real_prefix = f'{prefix} '
                    else:
                        real_prefix = ''
                    zip_file.writestr(
                        f'{real_prefix}{name}{suffix}.jpg',
                        image
                    )

        for date, worker_list in _worker_lists(reconciliation):
            zip_file.writestr(
                f'работники, выходившие {string_from_date(date)}.pdf',
                worker_list
            )

        for i, check in enumerate(_checks(reconciliation)):
            zip_file.writestr(
                f'чек {i + 1}.jpg',
                check
            )

        _add_images('Договор', _contracts(reconciliation))
        _add_images('Паспорт', _passports(reconciliation))
        _add_images('Миграционная карта', _migration_cards(reconciliation))

    response = HttpResponse(content_type='application/zip')
    response[
        'Content-Disposition'
    ] = "attachment; filename*=UTF-8''{}".format(
        '{}.zip'.format(quote(str(reconciliation)))
    )
    response.write(proxy_file.getvalue())

    return response
