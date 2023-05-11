# -*- coding: utf-8 -*-

import decimal

from django.contrib.auth.mixins import LoginRequiredMixin

from django.http import JsonResponse

from django.shortcuts import render

from dal import autocomplete

from the_redhuman_is import models

from the_redhuman_is.views.utils import _get_value
from the_redhuman_is.views.utils import exception_to_json_error
from the_redhuman_is.views.utils import get_first_last_day

from utils.date_time import date_from_string
from utils.date_time import string_from_date


# Todo: to manager
def worker_turnouts(view):
    customer_pk = view.forwarded.get('customer')
    worker_pk = view.forwarded.get('worker')

    turnouts = models.WorkerTurnout.objects.all(
    ).select_related(
        'timesheet'
    ).order_by(
        '-timesheet__sheet_date'
    )

    if customer_pk:
        turnouts = turnouts.filter(timesheet__customer__pk=customer_pk)

    if worker_pk:
        turnouts = turnouts.filter(worker__pk=worker_pk)

    return turnouts


class WorkerTurnoutAutocomplete(LoginRequiredMixin, autocomplete.Select2QuerySetView):
    def get_queryset(self):
        return worker_turnouts(self)

    def get_result_label(self, result):
        return '{}, {}'.format(
            string_from_date(result.timesheet.sheet_date),
            result.timesheet.sheet_turn
        )


@exception_to_json_error()
def create(request):

    def _decimal(key):
        value = _get_value(request, key)
        if value is not None:
            return decimal.Decimal(value)
        return None

    claim_type = _get_value(request, 'claim_type')
    comment = _get_value(request, 'comment')
    fine_amount = _decimal('fine_amount')
    fine_date = date_from_string(_get_value(request, 'fine_date'))
    customer_pk = _get_value(request, 'customer')
    fine_type = _get_value(request, 'fine_type')
    provider_pk = _get_value(request, 'provider')
    worker_pk = _get_value(request, 'worker')
    deduction_date_type = _get_value(request, 'deduction_date_type')
    deduction_date = date_from_string(_get_value(request, 'deduction_date'))
    turnout_pk = _get_value(request, 'turnout')
    deduction_amount_type = _get_value(request, 'deduction_amount_type')
    deduction_amount = _decimal('deduction_amount')
    deduction_type = _get_value(request, 'deduction_type')
    expense_pk = _get_value(request, 'expense')
    industrial_cost_type_pk = _get_value(request, 'industrial_cost_type')

    models.fine_utils.create_claim(
        request.user,
        claim_type,
        comment,
        fine_amount,
        fine_date,
        customer_pk,
        fine_type,
        provider_pk,
        worker_pk,
        deduction_date_type,
        deduction_date,
        turnout_pk,
        deduction_amount_type,
        deduction_amount,
        deduction_type,
        expense_pk,
        industrial_cost_type_pk,
        request.FILES.getlist('files'),
    )

    return JsonResponse({'status': 'ok'})


@exception_to_json_error()
def claim_list(request):
    first_day, last_day = get_first_last_day(request)

    deductions = models.fine_utils.claims_list(first_day, last_day)

    _copy_fields = [
        'claim_type',
        'deduction_type',
        'first_photo',
        'customer_name',
        'claim_by',
        'fine_amount',
        'fine_id',
        'worker_id',
        'worker_full_name',
        'amount',
        'id',
        'comment',
        'timestamp',
    ]
    def _serialize(item):
        return { f: getattr(item, f) for f in _copy_fields }

    data = [_serialize(o) for o in deductions]

    return JsonResponse({'status': 'ok', 'data': data})


def photos(request, pk):
    return render(
        request,
        'the_redhuman_is/reports/photos_list.html',
        {
            'photos': models.fine_utils.claims_photos(pk)
        }
    )
    
