# -*- coding: utf-8 -*-

import datetime

from dal import autocomplete
from django.contrib.auth.models import Group

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Sum
from django.http import HttpResponse
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_POST

from django import forms

from sql_util.utils import SubquerySum, SubqueryCount

from the_redhuman_is import models

from the_redhuman_is.models import Customer
from the_redhuman_is.models import CustomerLocation
from the_redhuman_is.models import CustomerRepr
from the_redhuman_is.models import DevelopmentManager
from the_redhuman_is.models import MaintenanceManager
from the_redhuman_is.models import TimeSheet
from the_redhuman_is.models import Worker
from the_redhuman_is.models import deposit

from the_redhuman_is.forms import CustCommentsForm
from the_redhuman_is.forms import CustomerForm
from the_redhuman_is.forms import CustomerLocationFormSet
from the_redhuman_is.forms import CustomerReprFormSet
from the_redhuman_is.forms import DManagerForm
from the_redhuman_is.forms import DaysIntervalForm
from the_redhuman_is.forms import MManagerForm
from the_redhuman_is.forms import ServiceForm
from the_redhuman_is.forms import ShowFromDateToDateForm
from the_redhuman_is.forms import SingleDateForm

from the_redhuman_is.views.utils import date_from_string
from the_redhuman_is.views.utils import get_first_last_day

from .auth import staff_account_required


class LegalEntityIntervalForm(DaysIntervalForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['first_day'].required = True
        
    legal_entity = forms.ModelChoiceField(
        label='Юрлицо',
        queryset=models.LegalEntity.objects.all(),
        widget=autocomplete.ModelSelect2(
            attrs={'class': 'form-control form-control-sm'},
            url='the_redhuman_is:legal-entity-autocomplete'
        )
    )


@staff_account_required
@transaction.atomic
def new_customer(request):
    if request.method == "POST":
        cform = CustomerForm(request.POST)
        if cform.is_valid():
            customer = cform.save()
            models.create_customer_operating_accounts(customer)

            return redirect('the_redhuman_is:customer_list')
    else:
        cform = CustomerForm()
    return render(request, 'the_redhuman_is/new_customer.html', {'cform': cform})


# Карточка клиента
@staff_account_required
def customer_detail(request, pk):
    customer = get_object_or_404(Customer, pk=pk)

    try:
        request.user.groups.get(name='Менеджеры')
        try:
            models.Customer.objects.filter(
                maintenancemanager__worker__workeruser__user=request.user
            ).get(pk=customer.pk)
        except Customer.DoesNotExist:
            raise PermissionDenied
    except Group.DoesNotExist:
        pass

    today = datetime.date.today()
    default = {
        'from_date': (today - datetime.timedelta(days=30)),
        'to_date': today
    }
    form = ShowFromDateToDateForm(request.GET or default)
    customerlocs = customer.customerlocation_set.all()
    customerreprs = customer.customerrepr_set.all()
    comments = customer.custcomments_set.all()
    services = customer.customerservice_set.all()
    if not form.is_valid():
        d = default
    else:
        d = form.cleaned_data
    qs = TimeSheet.objects.filter(
        customer=customer,
        sheet_date__range=(d['from_date'], d['to_date'])
    )
    timesheets = qs.annotate(
        worker_turnouts__count=SubqueryCount('worker_turnouts'),
        worker_turnouts__hours_worked__sum=SubquerySum('worker_turnouts__hours_worked'),
        customer_sum=SubquerySum('worker_turnouts__turnoutcustomeroperation__operation__amount'),
    ).order_by('-sheet_date')
    total_hours = qs.aggregate(
        Sum('worker_turnouts__hours_worked')
    )

    dmanager_form = DManagerForm(
        initial={
            'worker': customer.developmentmanager_set.values_list('worker', flat=True).first()
        })
    mmanager_form = MManagerForm(
        initial={
            'worker': list(customer.maintenancemanager_set.values_list('worker', flat=True))
        }
    )

    return render(
        request,
        'the_redhuman_is/customer/details.html',
        {
            'customer': customer,
            'customerlocs': customerlocs,
            'customerreprs': customerreprs,
            'comments': comments,
            'timesheets': timesheets,
            'form': form,
            'total_hours': total_hours,
            'd_interval': d,
            'services': services,
            'service_form': ServiceForm(),
            'dmanager_form': dmanager_form,
            'mmanager_form': mmanager_form,
            'debts_first_day_form': SingleDateForm(
                field_name='debts_first_day',
                initial={
                    'debts_first_day': customer.debts_first_day
                }
            ),
            'legal_entity_form': LegalEntityIntervalForm(),
            'legal_entities': models.customer_legal_entities(customer),
        }
    )


# Редактирование клиента
@staff_account_required
def customer_edit(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    if request.method == "POST":
        cform = CustomerForm(request.POST, request.FILES or None, instance=customer)
        if cform.is_valid():
            customer = cform.save(commit=False)
            customer.save()
            return redirect('the_redhuman_is:customer_list')
    else:
        cform = CustomerForm(instance=customer)
    return render(request, 'the_redhuman_is/new_customer.html', {'cform': cform})


# Добавить обьект (для клиента)
@staff_account_required
def new_locations(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    if request.method == "POST":
        formset = CustomerLocationFormSet(request.POST)
        if formset.is_valid():
            customerlocations = formset.save(commit=False)
            for customerlocation in customerlocations:
                customerlocation.customer_id = customer
                customerlocation.save()
            return redirect('the_redhuman_is:customer_list')
    else:
        formset = CustomerLocationFormSet(queryset=CustomerLocation.objects.none())
    return render(request, 'the_redhuman_is/new_locations.html', {'formset': formset})


# Добавить представителей клиента
@staff_account_required
def new_representatives(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    if request.method == "POST":
        formset = CustomerReprFormSet(request.POST)
        if formset.is_valid():
            customerreprs = formset.save(commit=False)
            for customerrepr in customerreprs:
                customerrepr.customer_id = customer
                customerrepr.save()
            return redirect('the_redhuman_is:customer_list')
    else:
        formset = CustomerReprFormSet(queryset=CustomerRepr.objects.none())
    return render(request, 'the_redhuman_is/new_representatives.html', {'formset': formset})


#Оставить комментарий
@staff_account_required
def new_comment(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    user = request.user
    if request.method == "POST":
        form = CustCommentsForm(request.POST)
        if form.is_valid():
            comment = form.save(commit=False)
            comment.customer = customer
            comment.date = timezone.now()
            comment.save()
            return redirect('the_redhuman_is:customer_detail', pk=pk)
    else:
        form = CustCommentsForm(initial={
            'date': timezone.now(),
            'author': user,
        })
    return render(request, 'the_redhuman_is/new_comment.html', {'form': form})


@staff_account_required
@transaction.atomic
def add_service(request, pk):
    customer = models.Customer.objects.get(pk=pk)
    service = models.Service.objects.get(pk=request.POST["service"])
    customer_service = models.CustomerService.objects.filter(
        customer=customer,
        service=service
    )
    if not customer_service.exists():
        models.create_customer_service(customer, service)

    return redirect("the_redhuman_is:customer_detail", pk=pk)


@staff_account_required
@transaction.atomic
def add_mmanager(request, pk):
    customer = models.Customer.objects.get(pk=pk)
    managers = MaintenanceManager.objects.filter(customer=customer)
    managers.delete()

    for pk in request.POST.getlist('worker'):
        if pk != '':
            worker = Worker.objects.get(pk=pk)
            MaintenanceManager.objects.create(
                customer=customer,
                worker=worker
            )

    return JsonResponse({'success': True})


@staff_account_required
def add_dmanager(request, pk):
    customer = models.Customer.objects.get(pk=pk)
    managers = DevelopmentManager.objects.filter(customer=customer)
    managers.delete()

    for pk in request.POST.getlist('worker'):
        if pk != '':
            worker = Worker.objects.get(pk=pk)
            DevelopmentManager.objects.create(
                customer=customer,
                worker=worker
            )

    return JsonResponse({'success': True})


@staff_account_required
def set_deposit_amount(request, pk):
    deposit.set_deposit_amount(pk, request.POST['amount'])
    return redirect('the_redhuman_is:customer_detail', pk=pk)


@staff_account_required
def clear_deposit_setting(request, pk):
    deposit.clear_deposit_setting(pk)
    return redirect('the_redhuman_is:customer_detail', pk=pk)


@staff_account_required
def service_assortment_list(request, pk):
    customer_service = models.CustomerService.objects.get(pk=pk)
    box_types = models.BoxType.objects.filter(customer=customer_service.customer)
    return render(
        request,
        'the_redhuman_is/customer/service_assortment.html',
        {
            'customer_service': customer_service,
            'box_types': box_types
        }
    )


@staff_account_required
def service_add_assortment(request, pk):
    customer_service = models.CustomerService.objects.get(pk=pk)
    name = request.POST['name']
    models.BoxType.objects.create(
        customer=customer_service.customer,
        name=name
    )

    return HttpResponse('ok')


@staff_account_required
def set_debts_first_day(request, pk):
    debts_first_day = request.POST['debts_first_day']
    customer = models.Customer.objects.get(pk=pk)
    customer.debts_first_day = date_from_string(debts_first_day)
    customer.save()

    return redirect("the_redhuman_is:customer_detail", pk=pk)


@require_POST
@staff_account_required
def add_legal_entity(request, pk):
    first_day, last_day = get_first_last_day(request, set_initial=False)
    customer = models.Customer.objects.get(pk=pk)
    legal_entity = models.LegalEntity.objects.get(pk=request.POST['legal_entity'])

    models.add_customer_legal_entity(
        customer,
        legal_entity,
        first_day,
        last_day
    )

    return redirect('the_redhuman_is:customer_detail', pk=pk)
