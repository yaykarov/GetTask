# -*- coding: utf-8 -*-
import itertools
import logging
import operator

from datetime import timedelta

from django.contrib.contenttypes.models import ContentType
from django.db.models import (
    Count,
    Q,
    Sum,
)

from django.forms import model_to_dict

from django.http import (
    HttpRequest,
    HttpResponse,
    JsonResponse,
)

from django.shortcuts import (
    get_object_or_404,
    redirect,
    render,
)
from django.utils import timezone

import finance

from the_redhuman_is.auth import staff_account_required

from the_redhuman_is.forms import (
    CustomOperationForm,
    DManagerForm,
    MManagerForm,
    WorkerSearchForm,
    WorkersDocumentsForm,
)

from the_redhuman_is.models import (
    Contract,
    Customer,
    CustomerOrder,
    DevelopmentManager,
    MaintenanceManager,
    Photo,
    RecruitmentOrder,
    TimeSheet,
    Worker,
    WorkerMedicalCard,
    WorkerPassport,
    WorkerPatent,
    WorkerRegistration,
    add_photo,
    get_photos,
)
from utils.functools import strtobool

logger = logging.getLogger(__name__)


@staff_account_required
def base(request: HttpRequest) -> HttpResponse:
    """
    Шаблон базы
    """
    return render(request, 'base.html', {})


@staff_account_required
def orders_dashboard(request):
    """
    Панель для обработки заявок
    """
    all_orders = CustomerOrder.objects.all().count()
    cust_order_qs = CustomerOrder.objects.filter(timesheet__isnull=True)
    cust_order_qs = cust_order_qs.order_by('-pk')
    unexecuted_orders = cust_order_qs.count()
    unexecuted_orders_n = cust_order_qs.annotate(Count('timesheet'))
    executed_orders = CustomerOrder.objects.filter(
        timesheet__is_executed=True
    )
    executed_orders = executed_orders.count()
    all_timesheets = TimeSheet.objects.count()
    all_timesheets_n = TimeSheet.objects.filter(is_executed=False)
    all_timesheets_n = all_timesheets_n.annotate(
        turnouts=Count('worker_turnouts'),
        hours_worked=Sum('worker_turnouts__hours_worked')
    )
    empty_timesheets = TimeSheet.objects.filter(
        is_executed=False, worker_turnouts__isnull=True
    ).count()
    unexecuted_timesheets_hours_not = TimeSheet.objects.exclude(
        worker_turnouts__isnull=True
    )
    unexecuted_timesheets_hours_not = unexecuted_timesheets_hours_not.filter(
        Q(is_executed=False, worker_turnouts__hours_worked=None) |
        Q(is_executed=False, worker_turnouts__hours_worked__lte=0)
    )
    unexecuted_timesheets_hours_not = unexecuted_timesheets_hours_not.distinct().count()
    unexecuted_timesheets = TimeSheet.objects.exclude(
        worker_turnouts__isnull=True
    )
    unexecuted_timesheets = unexecuted_timesheets.filter(
        is_executed=False,
        worker_turnouts__hours_worked__gt=0
    )
    unexecuted_timesheets = unexecuted_timesheets.distinct().count()
    return render(
        request,
        'the_redhuman_is/orders_dashboard.html',
        {
            'all_orders': all_orders,
            'unexecuted_orders': unexecuted_orders,
            'unexecuted_orders_n': unexecuted_orders_n,
            'executed_orders': executed_orders,
            'all_timesheets': all_timesheets,
            'all_timesheets_n': all_timesheets_n,
            'empty_timesheets': empty_timesheets,
            'unexecuted_timesheets': unexecuted_timesheets,
            'unexecuted_timesheets_hours_not': unexecuted_timesheets_hours_not,
        }
    )


@staff_account_required
def customer_list(request):
    user_groups = request.user.groups.values_list('name', flat=True)
    customer_qs = Customer.objects.with_new_turnouts_amount(
    ).with_all_closed_before(
    ).with_no_recons_after(
    ).with_turnouts_amount(
        'unsigned_turnouts_amount',
        Q(is_closed=False)
    ).with_turnouts_amount(
        'unpaid_signed_turnouts_amount',
        Q(is_closed=True, payment_operation__isnull=True)
    ).with_turnouts_amount(
        'paid_unsigned_turnouts_amount',
        Q(is_closed=False, payment_operation__isnull=False)
    )

    if not request.user.is_superuser and 'Менеджеры' in user_groups:
        customer_qs = customer_qs.filter(
            maintenancemanager__worker__workeruser__user=request.user
        )
    force_all = strtobool(request.GET.get('force_all'))
    if not force_all:
        customer_qs = customer_qs.filter(
            Q(new_turnouts_amount__gt=0) |
            Q(unsigned_turnouts_amount__gt=0) |
            Q(unpaid_signed_turnouts_amount__gt=0),
            is_actual=True,
        )
    customer_qs = customer_qs.order_by('cust_name')

    dmanagers = {}
    mmanagers = {}
    customer_data = []

    mmanager_form_media = False

    if customer_qs:
        dmanagers_set = DevelopmentManager.objects.filter(
            customer__in=customer_qs
        ).prefetch_related('worker')
        mmanagers_set = MaintenanceManager.objects.filter(
            customer__in=customer_qs
        ).prefetch_related('worker')

        for manager in dmanagers_set:
            dmanagers[manager.customer_id] = manager.worker

        for manager in mmanagers_set:
            mmanagers[manager.customer_id] = manager.worker

    for customer in customer_qs:
        row = model_to_dict(customer)
        row['pk'] = customer.pk
        row['new_turnouts_amount'] = customer.new_turnouts_amount
        row['unsigned_turnouts_amount'] = customer.unsigned_turnouts_amount
        row['unpaid_signed_turnouts_amount'] = customer.unpaid_signed_turnouts_amount
        row['paid_unsigned_turnouts_amount'] = customer.paid_unsigned_turnouts_amount
        row['all_closed_before'] = customer.all_closed_before
        row['no_recons_after'] = customer.no_recons_after
        customer_mmanagers = customer.maintenancemanager_set.all()
        row['mmanager_form'] = MManagerForm(
            initial={
                'worker': [m.worker.pk if m.worker else 0 for m in customer_mmanagers]
            }
        )
        if not mmanager_form_media:
            mmanager_form_media = row['mmanager_form'].media
        row['dmanager_form'] = DManagerForm(
            initial={'worker': dmanagers.get(customer.pk, None)}
        )

        customer_data.append(row)

    return render(
        request,
        'the_redhuman_is/customer_list.html',
        {
            'customers': customer_data,
            'mmanager_form_media': mmanager_form_media,
            'force_all': force_all,
        }
    )


def customer_contract_scans(request, pk):
    customer = Customer.objects.get(pk=pk)

    return render(
        request,
        'the_redhuman_is/reports/photos_list.html',
        {
            'photos': get_photos(customer)
        }
    )


def add_customer_contract_scans(request, pk):
    customer = Customer.objects.get(pk=pk)

    scans = sorted(
        request.FILES.getlist('scan'),
        key=lambda scan: str(scan),
    )

    for scan in scans:
        add_photo(customer, scan)

    return redirect('the_redhuman_is:customer_list')


@staff_account_required
def cashier_workspace(request):
    now = timezone.localtime()
    today = now.date()
    yesterday = today - timedelta(1)
    operations = finance.models.Operation.objects.filter(
        timepoint__date__gte=yesterday
    ).order_by("-timepoint")
    acc_kass = get_object_or_404(finance.models.Account, name__istartswith="Касса старая")
    acc_acc = get_object_or_404(finance.models.Account, name__istartswith="51")
    kass_saldo = acc_kass.turnover_saldo()
    acc_saldo = acc_acc.turnover_saldo()
    salary_root = get_object_or_404(finance.models.Account, name__icontains="70")
    salary_accs = salary_root.children.all()
    debet = 0
    credit = 0
    saldo = 0
    for salary_acc in salary_accs:
        debet += salary_acc.turnover_debet()
        credit += salary_acc.turnover_credit()
        saldo += salary_acc.turnover_saldo()
    form = WorkerSearchForm()
    o_form = CustomOperationForm(initial={
        'date': today,
        })
    if request.method == "POST":
        form = WorkerSearchForm(data=request.POST or None)
        o_form = CustomOperationForm(request.POST or None)
        if form.is_valid():
            worker = form.cleaned_data["worker"]
            return redirect('the_redhuman_is:to_pay_salary', pk=worker.pk)
        if o_form.is_valid():
            item = o_form.cleaned_data['choice']
            comment = o_form.cleaned_data['comment']
            amount = o_form.cleaned_data['amount']
            data = o_form.cleaned_data['date']
            # Платеж за общехозяйственные расходы
            if item == "Платеж за общехозяйственные расходы из кассы":
                debet = get_object_or_404(finance.models.Account, name__istartswith="26")
                credit = get_object_or_404(finance.models.Account, name__istartswith="Касса старая")
            # Выдача денег подотчетному лицу
            elif item == "Выдача денег подотчетному лицу":
                debet = get_object_or_404(finance.models.Account, name__istartswith="71")
                credit = get_object_or_404(finance.models.Account, name__istartswith="Касса старая")
            # Расчетный счет
            # Платеж на 302 счет
            elif item == "Платеж на 302 счет":
                debet = get_object_or_404(finance.models.Account, name__istartswith="76")
                credit = get_object_or_404(finance.models.Account, name__istartswith="51. Юнистрим")
            # Платеж за общехозяйственные расходы
            elif item == "Платеж за общехозяйственные расходы с р/с Юнистрим":
                debet = get_object_or_404(finance.models.Account, name__istartswith="26")
                credit = get_object_or_404(finance.models.Account, name__istartswith="51. Юнистрим")
            # Уплата налогов
            elif item == "Уплата налогов":
                debet = get_object_or_404(finance.models.Account, name__istartswith="26")
                credit = get_object_or_404(finance.models.Account, name__istartswith="51. Юнистрим")
                comment = "Уплата налога ___ за период с ___ по ___"
            # Поступление наличных от переводов
            elif item == "Поступление наличных от переводов на р/с":
                debet = get_object_or_404(finance.models.Account, name__istartswith="51. Юнистрим")
                credit = get_object_or_404(finance.models.Account, name__istartswith="76")
            # Поступление от клиента (редкость маловероятная)
            elif item == "Поступление от клиента":
                debet = get_object_or_404(finance.models.Account, name__istartswith="51. Юнистрим")
                credit = get_object_or_404(finance.models.Account, name__istartswith="62")
            # Поступление от клиента (редкость маловероятная)
            elif item == "Поступление от кредитора":
                debet = get_object_or_404(finance.models.Account, name__istartswith="Касса старая")
                credit = get_object_or_404(finance.models.Account, name__istartswith="67")
            operation = finance.models.Operation.objects.create(
                timepoint=now,
                comment=comment,
                author=request.user,
                debet=debet,
                credit=credit,
                amount=amount
            )
            operation.save()
            return redirect('the_redhuman_is:cashier_workspace')
    return render(
        request,
        'the_redhuman_is/cashier-workspace3.html',
        {
            'operations': operations,
            'kass_saldo': kass_saldo,
            'acc_saldo': acc_saldo,
            'acc_acc': acc_acc,
            'acc_kass': acc_kass,
            'debet': debet,
            'credit': credit,
            'saldo': saldo,
            'form': form,
            'o_form': o_form
        }
    )


# Todo: remove this
@staff_account_required
def recruitment(request):
    """
    Подбор
    """
    orders = RecruitmentOrder.objects.filter(is_actual=True).annotate(Count('workersfororder')).prefetch_related('customer_order', 'customer_order__customer', 'customer_order__cust_location')
    workers = Worker.objects.filter(
    Q(workersfororder__isnull=True)|Q(workersfororder__order__is_actual=False)
    ).exclude(worker_turnouts__timesheet__is_executed=False
    ).annotate(Count('worker_turnouts', distinct=True)).prefetch_related('metro', 'position').order_by('-worker_turnouts__count')
    return render(request, 'the_redhuman_is/recruitment.html', {'orders': orders, 'workers': workers})


def extract_photo_from_model(model):
    to_return = []
    for i in ("image", "image1", "image2", "image3"):
        if getattr(model, i, None):
            to_return.append(getattr(model, i))
    return to_return


@staff_account_required
def workers_documents(request):
    """
        Фотографии
    """

    workers = Worker.objects.order_by('pk').in_bulk()
    contracts = Contract.objects.all()
    medical_cards = WorkerMedicalCard.objects.all()
    patents = WorkerPatent.objects.all()
    registrations = WorkerRegistration.objects.all()
    passports = WorkerPassport.objects.all()

    worker_photo_qs = Photo.objects.filter(
        content_type=ContentType.objects.get_for_model(Worker)
    ).order_by(
        'object_id',
        'pk'
    ).only(
        'object_id',
        'image'
    )
    extracted_worker_photos = {
        k: [p.image for p in g]
        for k, g in itertools.groupby(worker_photo_qs, key=operator.attrgetter('object_id'))
    }
    worker_photos = {}
    for worker_pk, worker in workers.items():
        worker_photos[worker_pk] = {
            'worker': worker,
            'profile': extracted_worker_photos.get(worker_pk, False)
        }

    for contract in contracts:
        extracted_photos = extract_photo_from_model(contract)
        if extracted_photos:
            worker_photos[contract.c_worker_id].setdefault('contracts', []).append(
                (contract, extracted_photos))

    for med_card in medical_cards:
        worker_photos[med_card.worker_id].setdefault('medical_card', []).append(med_card)

    for pat in patents:
        # workers_id
        worker_photos[pat.workers_id_id].setdefault('patents', []).append(pat)

    for reg in registrations:
        worker_photos[reg.workers_id_id].setdefault('registration', []).append(reg)

    for passport in passports:
        worker_photos[passport.workers_id_id].setdefault('passport', []).append(passport)

    return render(
        request,
        'the_redhuman_is/worker_documents.html',
        {
          'workers_data': worker_photos,
          'form': WorkersDocumentsForm()
        }
    )


@staff_account_required
def worker_photos(request, pk):
    worker = get_object_or_404(Worker, pk=pk)
    return render(request, 'the_redhuman_is/photos.html', {
        'objects': [{'obj': worker, 'photos': [p.image for p in get_photos(worker)]}, ]
    })


@staff_account_required
def med_card_photos(request, pk):
    worker = get_object_or_404(Worker, pk=pk)
    med_cards = WorkerMedicalCard.objects.filter(worker=worker)

    return render(request, 'the_redhuman_is/photos.html', {
        'objects': [{'obj': med_c, 'photos': extract_photo_from_model(med_c), 'type': 'med_card'} for med_c in
                    med_cards]
    })


@staff_account_required
def contracts_photos(request, pk):
    worker = get_object_or_404(Worker, pk=pk)
    contracts = Contract.objects.filter(c_worker=worker)
    return render(request, 'the_redhuman_is/photos.html', {
        'objects': [{'obj': c, 'photos': extract_photo_from_model(c), 'type': 'contract'} for c in contracts]
    })


@staff_account_required
def ajax_worker(request):
    if request.method == 'GET':
        obj = get_object_or_404(Worker, pk=request.GET.get('q', None))
        data = model_to_dict(obj, exclude=['contract_type'])
        data['place_of_birth_name'] = obj.place_of_birth_name
        data['citizenship_name'] = obj.citizenship_name
        data['position_name'] = obj.position_name
        return JsonResponse(data, safe=False)
    return JsonResponse({})


@staff_account_required
def ajax_worker_contract(request):
    if request.method == 'GET':
        obj = get_object_or_404(Contract,
                                c_worker=request.GET.get('q', None),
                                is_actual=True)
        data = model_to_dict(obj, exclude=['image', 'image2', 'image3'])
        return JsonResponse(data, safe=False)
    return JsonResponse({})


@staff_account_required
def ajax_worker_passport(request):
    if request.method == 'GET':
        obj = get_object_or_404(WorkerPassport,
                                workers_id=request.GET.get('q', None),
                                is_actual=True)
        data = model_to_dict(obj)
        return JsonResponse(data, safe=False)
    return JsonResponse({})


@staff_account_required
def ajax_worker_patent(request):
    if request.method == 'GET':
        obj = get_object_or_404(WorkerPatent,
                                workers_id=request.GET.get('q', None),
                                is_actual=True)
        data = model_to_dict(obj)
        return JsonResponse(data, safe=False)
    return JsonResponse({})


@staff_account_required
def ajax_worker_registration(request):
    if request.method == 'GET':
        obj = get_object_or_404(WorkerRegistration,
                                workers_id=request.GET.get('q', None),
                                is_actual=True)
        data = model_to_dict(obj)
        return JsonResponse(data, safe=False)
    return JsonResponse({})


@staff_account_required
def ajax_workers_documents(request):
    if request.method == 'GET':
        filter_params = {}
        for param in ['photo', 'contract', 'med_card', 'patent', 'registration', 'passport']:
            name = f'has_{param}'
            value = strtobool(request.GET.get(param))
            if value is not None:
                filter_params[name] = value

        workers = Worker.objects.with_has_photo(
        ).with_has_contract(
        ).with_has_med_card(
        ).with_has_patent(
        ).with_has_registration(
        ).with_has_passport()

        workers = workers.filter(**filter_params)

        to_return = {}
        for w in workers:
            worker_data = {
                'name': str(w),
                'photos': w.has_photo,
                'contracts': w.has_contract,
                'med_cards': w.has_med_card,
                'patents': w.has_patent,
                'registration': w.has_registration,
                'passport': w.has_passport,
            }
            to_return[w.id] = worker_data

        return JsonResponse(to_return, safe=False)

    return JsonResponse({})
