# -*- coding: utf-8 -*-

from ..auth import staff_account_required

from the_redhuman_is.models import Bank, BankService, BankServiceParams, BankCalculatorCommissionFix, BankCalculatorCommission1, BankCalculatorCommission2, CommissionOperation

from the_redhuman_is.forms import BankFormSet, BankServiceFormSET, BankServiceForm, BankServiceParamsForm, BankServiceParamsFormSET

from django.shortcuts import render

from django.http import JsonResponse

from django.shortcuts import get_object_or_404

import finance


@staff_account_required
def index(request):
    banks = Bank.objects.all().order_by('name')
    return render(request, 'the_redhuman_is/banks/index.html', {'banks': banks})


@staff_account_required
def manage_bank(request):
    if request.method == "POST":
        formset = BankFormSet(
            request.POST,
        )

        if formset.is_valid():
            pks = []
            stations = formset.save(commit=False)

            for form in formset:
                if form['id'].value() != '':
                    pks.append(int(form['id'].value()))

            for station in stations:
                station.save()
                if station.id not in pks:
                    pks.append(station.id)

            for form in formset.deleted_forms:
                pk = int(form['id'].value())
                Bank.objects.filter(pk=pk).delete()
                pks.remove(pk)

            pks.sort()

            return JsonResponse({'success': True, 'pks': pks})
        else:
            return JsonResponse(formset.errors, status=400, safe=False)


@staff_account_required
def service_type(request):
    services = BankService.objects.all().order_by('type')
    return render(request, 'the_redhuman_is/banks/service_types.html', {'services': services})


@staff_account_required
def manage_service_type(request):
    if request.method == "POST":
        formset = BankServiceFormSET(
            request.POST,
        )

        if formset.is_valid():
            pks = []
            services = formset.save(commit=False)

            for form in formset:
                if form['id'].value() != '':
                    pks.append(int(form['id'].value()))

            for service in services:
                service.save()
                if service.id not in pks:
                    pks.append(service.id)

            for form in formset.deleted_forms:
                pk = int(form['id'].value())
                BankService.objects.filter(pk=pk).delete()
                pks.remove(pk)

            pks.sort()

            return JsonResponse({'success': True, 'pks': pks})
        else:
            return JsonResponse(formset.errors, status=400, safe=False)
    else:
        n = request.GET.get("n")
        prefix = 'form-' + n
        form = BankServiceForm(prefix=prefix)
        return render(request, 'the_redhuman_is/banks/service_type_form.html', {'form': form})


@staff_account_required
def service(request, bank_pk):
    bank = get_object_or_404(Bank, pk=bank_pk)
    services_params = BankServiceParams.objects.filter(bank=bank).order_by('service__type')
    return render(request, 'the_redhuman_is/banks/services.html', {'bank': bank, 'services_params': services_params})


@staff_account_required
def manage_service(request, bank_pk):
    if request.method == "POST":
        formset = BankServiceParamsFormSET(
            request.POST,
        )

        if formset.is_valid():

            pks = []

            for form in formset:

                if form['id'].value() != '':
                    bank_service_param = BankServiceParams.objects.get(pk=int(form['id'].value()))
                else:
                    bank_service_param = BankServiceParams()

                bank_service_param.service_id = int(form['service'].value())
                bank_service_param.bank_id = bank_pk

                if form['calculator_type'].value() == 'fix':
                    bank_service_param.calculator = BankCalculatorCommissionFix.objects.create(val=form['val'].value())
                elif form['calculator_type'].value() == 'commission1':
                    bank_service_param.calculator = BankCalculatorCommission1.objects.create(val=form['val'].value())
                else:
                    bank_service_param.calculator = BankCalculatorCommission2.objects.create(val=form['val'].value())

                bank_service_param.save()
                pks.append(bank_service_param.id)

            for form in formset.deleted_forms:
                pk = int(form['id'].value())
                BankServiceParams.objects.filter(pk=pk).delete()
                pks.remove(pk)

            pks.sort()

            return JsonResponse({'success': True, 'pks': pks})
        else:
            return JsonResponse(formset.errors, status=400, safe=False)
    else:
        n = request.GET.get("n")
        prefix = 'form-' + n
        form = BankServiceParamsForm(prefix=prefix)
        form.fields['service'].widget.url += '?bank_id=' + str(bank_pk)

        return render(request, 'the_redhuman_is/banks/service_form.html', {'form': form})


@staff_account_required
def edit_service(request):

    if request.POST:
        id = request.POST.get('id')
        service_param = BankServiceParams.objects.get(pk=id)
        service_param.service_id = int(request.POST.get('service'))
        calculator_type = request.POST.get('calculator_type')
        val = float(request.POST.get('val'))

        if calculator_type not in service_param.calc_content_type.name:
            service_param.calculator.delete()

            if calculator_type == 'fix':
                service_param.calculator = BankCalculatorCommissionFix.objects.create(val=val)
            elif calculator_type == 'commission1':
                service_param.calculator = BankCalculatorCommission1.objects.create(val=val)
            else:
                service_param.calculator = BankCalculatorCommission2.objects.create(val=val)

        service_param.calculator.val = val
        service_param.calculator.save()

        service_param.save()

        return render(request, 'the_redhuman_is/banks/service_row.html', {'service_param': service_param})

    service_id = request.GET.get('id')
    service_param = BankServiceParams.objects.get(pk=service_id)

    calculator_type = 'fix'

    if '1' in service_param.calc_content_type.name:
        calculator_type = 'commission1'
    elif '2' in service_param.calc_content_type.name:
        calculator_type = 'commission2'

    prefix = 'edit-form-' + service_id
    form = BankServiceParamsForm(prefix=prefix, initial={
        'val': service_param.calculator.val,
        'service': service_param.service,
        'calculator_type': calculator_type
    })

    return render(request, 'the_redhuman_is/banks/service_edit_form.html', {'service_param': service_param,
                                                                            'form': form})


