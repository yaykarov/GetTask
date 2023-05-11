from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import (
    OuterRef,
    Q,
)
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from django.views.generic import TemplateView
from sql_util.aggregates import Exists

from the_redhuman_is.models import (
    Worker,
    WorkerSelfEmploymentData,
)
from the_redhuman_is.services import update_not_paid_turnout_payments

worker_fields = (
    'pk',
    'full_name',
    'citizenship__name',
    'input_date',
)
wse_fields = (
    'pk',
    'worker_id',
    'cardholder_name',
    'tax_number',
    'bank_account',
    'bank_name',
    'bank_identification_code',
    'correspondent_account',
    'deletion_ts',
)


@login_required
@require_http_methods(['GET', 'HEAD'])
def selfemployment_json_data(request):
    wse_qs = WorkerSelfEmploymentData.objects.annotate(
        e1=Exists(
            WorkerSelfEmploymentData.objects.filter(
                Q(deletion_ts__gt=OuterRef('deletion_ts')) |
                Q(deletion_ts=OuterRef('deletion_ts'), pk__gt=OuterRef('pk')),
                worker_id=OuterRef('worker_id')
            )
        ),
        e2=Exists(
            WorkerSelfEmploymentData.objects.filter(
                worker_id=OuterRef('worker_id'),
                deletion_ts__isnull=True
            )
        )
    ).filter(Q(deletion_ts__isnull=True) | Q(e1=False, e2=False)).values_list(*wse_fields)

    worker_qs = Worker.objects.all(
    ).with_full_name(
    ).annotate(
        has_selfemployment=Exists(
            WorkerSelfEmploymentData.objects.filter(
                worker=OuterRef('pk')
            )
        )
    ).filter(
        has_selfemployment=True
    ).select_related(
        'citizenship',
    ).values_list(*worker_fields)

    count = worker_qs.count()
    start, length = int(request.GET['start']), int(request.GET['length'])
    search_term = request.GET['search[value]']
    if search_term != '':
        worker_qs = worker_qs.filter_by_text(search_term)
    order = int(request.GET['order[0][column]'])
    desc = request.GET['order[0][dir]'] == 'desc'
    if order in range(3, 9):
        wse_data = list(wse_qs.order_by('-' * desc + wse_fields[order - 1])[start:start+length])
        worker_ids = [e[1] for e in wse_data]
        worker_extra = {e[0]: e for e in worker_qs.filter(pk__in=worker_ids)}
        worker_data = [worker_extra[ix] for ix in worker_ids]
    else:
        if order in range(0, 3):
            worker_qs = worker_qs.order_by('-' * desc + worker_fields[order + 1])
        worker_data = list(worker_qs[start:start+length])
        worker_ids = [e[0] for e in worker_data]
        wse_extra = {e[1]: e for e in wse_qs.filter(worker__in=worker_ids)}
        wse_data = [wse_extra[ix] for ix in worker_ids]
    data = [(u[1], u[2], u[3].strftime('%d.%m.%Y')) + v[2:] + (u[0], v[0]) for u, v in zip(worker_data, wse_data)]

    return JsonResponse({
        'draw': request.GET['draw'],
        'recordsTotal': count,
        'recordsFiltered': count,
        'data': data,
    })


@login_required
@require_http_methods(['POST'])
def selfemployment_json_toggle(request):
    try:
        pk = int(request.POST['pk'])
        wse = WorkerSelfEmploymentData.objects.get(pk=pk)
        if wse.deletion_ts is None:
            wse.deletion_ts = timezone.now()
        else:
            wse.deletion_ts = None
        wse.save()
        update_not_paid_turnout_payments(wse.worker, request.user)
    except (KeyError, ValueError, WorkerSelfEmploymentData.DoesNotExist):
        return JsonResponse({}, status=400)
    return JsonResponse({'is_actual': wse.is_actual}, status=200)


class SelfEmploymentView(LoginRequiredMixin, TemplateView):
    model = Worker
    template_name = 'the_redhuman_is/worker/self_employment.html'
