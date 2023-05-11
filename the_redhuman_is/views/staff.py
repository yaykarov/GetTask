# -*- coding: utf-8 -*-

from django.contrib.auth.mixins import LoginRequiredMixin

from django.core.exceptions import ObjectDoesNotExist

from django.db import transaction

from django.db.models import Count
from django.db.models import OuterRef
from django.db.models import Q
from django.db.models import Subquery

from django.http import JsonResponse

from django.shortcuts import render

from django.views.decorators.http import require_POST

from dal.autocomplete import Select2QuerySetView

from the_redhuman_is import models

from utils.date_time import (
    date_from_string,
    string_from_date,
)

from the_redhuman_is.views import datatables

from the_redhuman_is.views.contracts import (
    _end_date_suggest,
    _notification_list,
    _selected_contracts,
    filtered_contracts,
)

from the_redhuman_is._2_0_staff_views import _generate_workers_error_messages

from the_redhuman_is.views.utils import (
    _get_value,
    exception_to_json_error,
    get_first_last_day,
)


def passports_qs(view):
    worker_pk = view.forwarded.get('worker')
    return models.WorkerPassport.objects.filter(workers_id__pk=worker_pk)


def passport_label(passport):
    return '{} {} с {} по {}'.format(
        passport.passport_series,
        passport.another_passport_number,
        string_from_date(passport.date_of_issue) if passport.date_of_issue else '-',
        string_from_date(passport.date_of_exp) if passport.date_of_exp else '-',
    )


class PassportAutocomplete(LoginRequiredMixin, Select2QuerySetView):
    def get_queryset(self):
        return passports_qs(self)

    def get_result_label(self, result):
        return passport_label(result)


def workers_list(request):
    first_day, last_day = get_first_last_day(request)

    return render(
        request,
        'workers_list.html',
        {
            'first_day': string_from_date(first_day),
            'last_day': string_from_date(last_day)
        }
    )


# @see datatables.net
def workers_list_details(request):
    columns = datatables.selected_columns(request.GET)

    user_groups = request.user.groups.values_list('name', flat=True)
    if request.user.is_superuser or 'Менеджеры' not in user_groups:
        workers = models.Worker.objects.all()
    else:
        customers = models.Customer.objects.filter(
            maintenancemanager__worker__workeruser__user=request.user
        )
        workers = models.Worker.objects.filter(
            Q(timesheet__customer__in=customers) |
            Q(worker_turnouts__timesheet__customer__in=customers)
        ).distinct()

    search_text = request.GET.get('search[value]')
    if search_text:
        workers = workers.filter_by_text(search_text)

    annotations = {}
    if 'turnouts_count' in columns:
        annotations['turnouts_count'] = Count('worker_turnouts', distinct=True)

    if 'contracts_count' in columns:
        annotations['contracts_count'] = Count('contract', distinct=True)

    if 'last_turnout_date' in columns:
        annotations['last_turnout_date'] = Subquery(
            models.TimeSheet.objects.filter(
                worker_turnouts__worker__pk=OuterRef('pk')
            ).order_by(
                '-sheet_date'
            ).values('sheet_date')[:1]
        )

    if 'last_turnout_customer' in columns:
        annotations['last_turnout_customer'] = Subquery(
            models.TimeSheet.objects.filter(
                worker_turnouts__worker__pk=OuterRef('pk')
            ).order_by(
                '-sheet_date'
            ).values('customer__cust_name')[:1]
        )

    if len(annotations) > 0:
        workers = workers.annotate(**annotations)

    for field in ['position', 'citizenship']:
        if field in columns:
            workers = workers.select_related(field)

    order_column, order_dir = datatables.order(request.GET)
    order_field = columns[order_column]

    if order_field in ['citizenship', 'position']:
        order_field += '__name'

    if order_field == 'worker':
        order_fields = ['last_name', 'name', 'patronymic']
    else:
        order_fields = [order_field]

    workers = workers.order_by(*[order_dir + f for f in order_fields])

    def _serialize(worker):
        result = {}
        for field in columns:
            if field == 'worker':
                result['worker_data'] = {
                    'pk': worker.pk,
                    'full_name': str(worker)
                }
            elif field in ['input_date', 'm_date_of_exp', 'last_turnout_date']:
                result[field] = string_from_date(getattr(worker, field))
            elif field in ['citizenship', 'position']:
                result[field] = getattr(worker, field).name
            else:
                result[field] = getattr(worker, field)

        return result

    records_total, workers = datatables.filter_range(workers, request.GET)

    data = []
    for worker in workers:
        data.append(_serialize(worker))

    return JsonResponse(
        {
            'draw': request.GET['draw'],
            'recordsTotal': records_total,
            'recordsFiltered': records_total, # Todo?
            'data': data
        }
    )


def contracts_list(request):
    return render(
        request,
        'contracts_list.html',
        {
        }
    )


# @see datatables.net
def contracts_list_details(request):
    columns = datatables.selected_columns(request.GET)

    contracts = filtered_contracts(request.GET.get('filter'))

    search_text = request.GET.get('search[value]')
    if search_text:
        contracts = contracts.filter(
            Q(c_worker__name__icontains=search_text) |
            Q(c_worker__last_name__icontains=search_text) |
            Q(c_worker__patronymic__icontains=search_text) |
            Q(cont_type__icontains=search_text)
        )

    contracts = contracts.select_related('c_worker')

    if 'contractor' in columns:
        contracts = contracts.select_related('contractor')

    order_column, order_dir = datatables.order(request.GET)
    order_field = columns[order_column]

    if order_field == 'worker':
        order_fields = ['c_worker__last_name', 'c_worker__name', 'c_worker__patronymic']
    elif order_field == 'contractor':
        order_fields = ['contractor__full_name']
    elif order_field == 'checkbox':
        order_fields = []
    else:
        order_fields = [order_field]

    contracts = contracts.order_by(*[order_dir + f for f in order_fields])

    def _serialize(contract):
        result = { 'pk': contract.pk }
        for field in columns:
            if field == 'worker':
                result['worker_data'] = {
                    'pk': contract.c_worker.pk,
                    'full_name': str(contract.c_worker)
                }
            elif field == 'checkbox':
                continue
            elif field == 'contractor':
                result['contractor'] = (
                    contract.contractor.full_name if contract.contractor else None
                )
            elif field in ['begin_date', 'end_date']:
                result[field] = string_from_date(getattr(contract, field))
            else:
                result[field] = getattr(contract, field)

        return result

    records_total, contracts = datatables.filter_range(contracts, request.GET)

    data = []
    for contract in contracts:
        data.append(_serialize(contract))

    return JsonResponse(
        {
            'draw': request.GET['draw'],
            'recordsTotal': records_total,
            'recordsFiltered': records_total, # Todo?
            'data': data
        }
    )


@require_POST
@exception_to_json_error()
def change_contracts(request):
    action = _get_value(request, 'action')
    contracts = _selected_contracts(request)
    if action == 'set_contractor':
        contractor_pk = _get_value(request, 'contractor')
        contractor = models.Contractor.objects.get(pk=contractor_pk)

        with transaction.atomic():
            for contract in contracts:
                contract.contractor = contractor
                contract.save()

    elif action == 'set_begin_date':
        begin_date = date_from_string(_get_value(request, 'date'))

        with transaction.atomic():
            for contract in contracts:
                contract.begin_date = begin_date
                contract.end_date = _end_date_suggest(contract)
                contract.save()
                notification, created = models.NoticeOfContract.objects.get_or_create(
                    contract=contract
                )
                notification.date = begin_date
                notification.save()

    # fire
    elif action == 'set_end_date':
        termination_date = date_from_string(_get_value(request, 'date'))

        with transaction.atomic():
            for contract in contracts:
                contract.is_actual = False
                contract.end_date = termination_date
                contract.save()
                notification, created = models.NoticeOfTermination.objects.get_or_create(
                    contract=contract
                )
                notification.date = termination_date
                notification.save()

    else:
        raise Exception('Unknown action value: {}'.format(action))

    return JsonResponse({'status': 'ok'})


@exception_to_json_error()
def download_notifications(request):
    action = _get_value(request, 'action')
    contracts = _selected_contracts(request)

    if action in ['download_conclude_notifications', 'download_termination_notifications']:
        proxy = models.ContractorProxy.objects.get(pk=_get_value(request, 'proxy'))
        notification_type = 'contract'
        if action == 'download_termination_notifications':
            notification_type = 'termination'

        errors, response = _notification_list(
            contracts,
            proxy,
            notification_type
        )

        if errors:
            return JsonResponse(
                {
                    'status': 'error',
                    'errors': _generate_workers_error_messages(errors)
                }
            )
        else:
            return response
    else:
        raise Exception('Unknown action value: {}'.format(action))


def worker_document_photos(request, worker_pk):
    return render(
        request,
        'worker_documents.html',
        {
            'worker_pk': worker_pk
        }
    )


def _worker_photos(request, worker):
    photos = []

    def _add_photo(photo_type, photo, target):
        photos.append(
            {
                'type': photo_type,
                'target': target.pk,
                'pk': photo.pk,
                'url': request.build_absolute_uri(photo.image.url),
            }
        )

    for photo in models.get_photos(worker):
        _add_photo('general', photo, worker)

    try:
        migration_card = models.WorkerMigrationCard.objects.get(worker=worker)
        for photo in models.get_photos(migration_card):
            _add_photo('migration_card', photo, migration_card)

    except ObjectDoesNotExist:
        pass

    try:
        passports = models.WorkerPassport.objects.filter(workers_id=worker)
        for passport in passports:
            for photo in models.get_photos(passport):
                _add_photo('passport', photo, passport)

    except ObjectDoesNotExist:
        pass

    return photos


def worker_documents_photos_data(request):
    worker_pk = _get_value(request, 'worker')

    worker = models.Worker.objects.get(pk=worker_pk)

    return JsonResponse(
        {
            'status': 'ok',
            'photos': _worker_photos(request, worker)
        }
    )


@exception_to_json_error()
def update_worker_document_photo(request):
    worker_pk = _get_value(request, 'worker')
    photo_pk = _get_value(request, 'pk')
    target_type = _get_value(request, 'type')
    target_pk = _get_value(request, 'target')

    worker = models.Worker.objects.get(pk=worker_pk)
    photo = models.Photo.objects.get(pk=photo_pk)

    if photo.pk not in [e['pk'] for e in _worker_photos(request, worker)]:
        raise Exception('The worker owning the photo can not be changed')

    if target_type == 'general':
        photo.change_target(worker)
    elif target_type == 'migration_card':
        migration_card, _ = models.WorkerMigrationCard.objects.get_or_create(
            worker=worker
        )
        photo.change_target(migration_card)
    elif target_type == 'passport':
        passport = models.WorkerPassport.objects.get(
            workers_id=worker,
            is_actual=True
        )
        # Todo
#        passport = models.WorkerPassport.objects.get(
#            workers_id=worker,
#            pk=target_pk
#        )
        photo.change_target(passport)
    else:
        raise Exception(f'Unknown target type {target_type}')

    return JsonResponse(
        {
            'status': 'ok',
            'photo': {'type': target_type, 'target': target_pk, 'pk': photo_pk}
        }
    )
