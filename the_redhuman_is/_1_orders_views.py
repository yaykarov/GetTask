# -*- coding: utf-8 -*-

from datetime import (
    datetime,
    timedelta,
)
import re
import decimal

from django.contrib.auth.models import Group

from django.contrib.auth.decorators import login_required
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import (
    ObjectDoesNotExist,
    PermissionDenied,
)
from django.db import transaction
from django.db.models import (
    Count,
    F,
    Q,
    Sum,
)
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from django.views.decorators.http import require_POST

import finance

from .auth import staff_account_required

from . import views

from the_redhuman_is import models
from the_redhuman_is.models import (
    Act,
    Contract,
    Customer,
    CustomerFine,
    CustomerFineDeduction,
    CustomerLocation,
    CustomerOperatingAccounts,
    CustomerOrder,
    CustomerService,
    NoWorkerPhoneException,
    Photo,
    RecruitmentOrder,
    TimeSheet,
    TurnoutBonus,
    TurnoutDeduction,
    Worker,
    WorkerTurnout,
)
from the_redhuman_is.models.delivery import (
    DeliveryRequestOperator,
)
from the_redhuman_is.models.worker import (
    WorkerUser,
)

from .forms import (
    ContractFormSet,
    CustomerOrderForm,
    CustomerOrderFormSet,
    TimeSheetForm,
    TimesheetTimelinessForm,
    ToAddContractForm,
    WorkerTurnoutFormSet,
)

from the_redhuman_is.services.turnout_calculations import update_turnout_payments

from utils.date_time import (
    date_time_from_string,
    time_interval_format,
)
from utils.numbers import (
    get_decimal,
    get_int,
)


def _get_int(value):
    try:
        value = int(value)
    except Exception as e:
        value = None

    return value


def _get_params(params):
    fines = {}
    bonuses = {}
    cfines = {}

    FIELDS_RX1 = re.compile("^id_fine_([0-9]+)_(\S+)$")
    FIELDS_RX2 = re.compile("^id_bonus_([0-9]+)_(\S+)$")
    FIELDS_RX3 = re.compile("^id_cfine_([0-9]+)_(\S+)$")

    for key in params.keys():
        m = FIELDS_RX1.match(key)
        if m:
            fine = {}

            turnout_id = int(m.group(1))
            if turnout_id not in fines:
                fines[turnout_id] = []

            amount_key = "val_fine_" + m.group(1) + "_" + m.group(2)
            comment_key = "comment_fine_" + m.group(1) + "_" + m.group(2)
            operation_key = "operation_fine_" + m.group(1) + "_" + m.group(2)
            fine_key = "id_fine_" + m.group(1) + "_" + m.group(2)

            if amount_key in params:
                fine['amount'] = get_decimal(params[amount_key])

            if comment_key in params:
                fine['comment'] = params[comment_key]

            if fine_key in params:
                fine['fine_id'] = params[fine_key]

            if operation_key in params:
                fine['operation'] = get_int(params[operation_key])

            fines[turnout_id].append(fine)

        m = FIELDS_RX2.match(key)
        if m:
            bonus = {}

            turnout_id = int(m.group(1))
            if turnout_id not in bonuses:
                bonuses[turnout_id] = []

            amount_key = "val_bonus_" + m.group(1) + "_" + m.group(2)
            comment_key = "comment_bonus_" + m.group(1) + "_" + m.group(2)
            operation_key = "operation_bonus_" + m.group(1) + "_" + m.group(2)
            bonus_key = "id_bonus_" + m.group(1) + "_" + m.group(2)

            if amount_key in params:
                bonus['amount'] = get_decimal(params[amount_key])

            if comment_key in params:
                bonus['comment'] = params[comment_key]

            if bonus_key in params:
                bonus['bonus_id'] = params[bonus_key]

            if operation_key in params:
                bonus['operation'] = get_int(params[operation_key])

            bonuses[turnout_id].append(bonus)

        m = FIELDS_RX3.match(key)
        if m:
            cfine = {}

            turnout_id = int(m.group(1))
            if turnout_id not in cfines:
                cfines[turnout_id] = []

            amount_key = "val_cfine_" + m.group(1) + "_" + m.group(2)
            comment_key = "comment_cfine_" + m.group(1) + "_" + m.group(2)
            operation_key = "operation_cfine_" + m.group(1) + "_" + m.group(2)
            cfine_key = "id_cfine_" + m.group(1) + "_" + m.group(2)

            if amount_key in params:
                cfine['amount'] = get_decimal(params[amount_key])

            if comment_key in params:
                cfine['comment'] = params[comment_key]

            if cfine_key in params:
                cfine['cfine_id'] = params[cfine_key]

            if operation_key in params:
                cfine['operation'] = get_int(params[operation_key])

            cfines[turnout_id].append(cfine)

    return fines, bonuses, cfines


""" Панель для обработки заявок """


# 2 создание заявок
@staff_account_required
def manage_order(request):
    if request.method == "POST":
        formset = CustomerOrderFormSet(
            request.POST,
        )

        if formset.is_valid():

            orders = []
            customerorders = formset.save(commit=False)

            for form in formset:
                if form['id'].value() != '':
                    orders.append(int(form['id'].value()))

            for customerorder in customerorders:

                order_pk = customerorder.pk

                customerorder.save()

                if order_pk is None:
                    recruitmentorder = RecruitmentOrder.objects.create(
                        customer_order=customerorder
                    )

                if customerorder.id not in orders:
                    orders.append(customerorder.id)

            for form in formset.deleted_forms:
                pk = int(form['id'].value())
                CustomerOrder.objects.filter(pk=pk).delete()
                orders.remove(pk)

            orders.sort()

            return JsonResponse({'success': True, 'orders': orders})
        else:
            return JsonResponse(formset.errors, status=400, safe=False)
    else:
        n = request.GET.get("n")
        prefix = 'form-' + n
        form = CustomerOrderForm(prefix=prefix)
        form.fields['cust_location'].widget.url = 'the_redhuman_is:actual-location-autocomplete'
        return render(request, 'the_redhuman_is/manage_order.html', {'form': form})


@staff_account_required
def new_orders(request):
    form = CustomerOrderForm()
    if request.method == "POST":
        formset = CustomerOrderFormSet(request.POST)
        if formset.is_valid():
            customerorders = formset.save(commit=False)
            for customerorder in customerorders:
                customerorder.save()
                recruitmentorder = RecruitmentOrder.objects.create(
                    customer_order=customerorder
                )
        return redirect('the_redhuman_is:orders_dashboard')
    elif "q" in request.GET and request.GET["q"]:
        q = request.GET.get("q")
        q = int(q)
        formset = CustomerOrderFormSet(
            queryset=CustomerOrder.objects.none()
        )
        formset.extra = q
        return render(request, 'the_redhuman_is/new_orders.html', {'formset': formset, 'form': form})
    else:
        return render(request, 'the_redhuman_is/new_orders.html', {'form': form, })


# 3 Все заявки
@staff_account_required
def list_orders(request):
    orders = CustomerOrder.objects.annotate(Count('timesheet'))
    orders = orders.prefetch_related('customer', 'cust_location')
    return render(request, 'the_redhuman_is/list_orders.html', {'orders': orders})


# 4. Незакрытые заявки (без табелей)
@staff_account_required
def unexecuted_orders(request):
    orders = CustomerOrder.objects.filter(timesheet__isnull=True)
    orders = orders.annotate(Count('timesheet'))
    orders = orders.prefetch_related('customer', 'cust_location')
    return render(request, 'the_redhuman_is/list_orders.html', {'orders': orders})


# 5. Заявки с табелем
@staff_account_required
def executed_orders(request):
    orders = CustomerOrder.objects.filter(timesheet__isnull=False)
    orders = orders.annotate(Count('timesheet'))
    orders = orders.prefetch_related('customer', 'cust_location')
    return render(request, 'the_redhuman_is/list_orders.html', {'orders': orders})


# 6. Табели всего
@staff_account_required
def timesheets(request):
    timesheets = TimeSheet.objects.annotate(workers=Count('worker_turnouts'))
    timesheets = timesheets.prefetch_related('customer', 'cust_location', 'customerorder', 'customer_repr', 'foreman')
    timesheets = timesheets.order_by('-sheet_date')
    return render(request, 'the_redhuman_is/timesheets.html', {'timesheets': timesheets})


# 6.1. Табели за период и суммы
@staff_account_required
def range_timesheets(request):
    beginStr = request.GET.get("begin")
    endStr = request.GET.get("end")
    display = request.GET.get("display") or None
    begin = datetime.strptime(beginStr, "%Y-%d-%m")
    end = datetime.strptime(endStr, "%Y-%d-%m")
    header = dict()
    if begin == end:
        query = Q(timesheet__sheet_date=begin)
        customer_query = Q(on_date=begin)
        header['range'] = 'Выходы за '+beginStr
    else:
        query = Q(timesheet__sheet_date__range=(begin,end))
        customer_query = Q(on_date__range=(begin,end))
        header['range'] = 'Выходы c '+beginStr+' по '+endStr

    customer_id = request.GET.get("customer")
    if customer_id:
        query &= Q(timesheet__customer__pk=customer_id)
        header['customer'] = 'Клиент: '+str(Customer.objects.get(pk=customer_id))

    location_id = request.GET.get("location")
    if location_id:
        query &= Q(timesheet__cust_location__pk=location_id)
        header['object'] = 'Объект: ' + CustomerLocation.objects.get(pk=location_id).location_name

    service_id = request.GET.get("service")
    if service_id:
        customer_service = CustomerService.objects.get(pk=service_id)
        query &= Q(turnoutservice__service=customer_service.service)
        header['service']= 'Услуга: '+str(CustomerService.objects.get(customer=customer_id))

    sheet_turn = request.GET.get("sheet_turn")
    if sheet_turn:
        query &= Q(timesheet__sheet_turn=sheet_turn)
        header['sheet_turn'] = 'Смена: '+sheet_turn

    customers1 = None
    mmanager = request.GET.get("mmanager")
    if mmanager:
        manager_set = models.MaintenanceManager.objects.filter(worker=mmanager)
        customers1 = []
        for manager in manager_set:
            customers1.append(manager.customer.pk)

        query &= Q(timesheet__customer__in=customers1)
        header['maint_managers'] = 'Менеджер по ведению: '+str(Worker.objects.get(pk=mmanager))

    customers2 = None
    dmanager = request.GET.get("dmanager")
    if dmanager:
        manager_set = models.DevelopmentManager.objects.filter(worker=dmanager)
        customers2 = []
        for manager in manager_set:
            customers2.append(manager.customer.pk)

        query &= Q(timesheet__customer__in=customers2)
        header['dev_managers'] = 'Менеджер по развитию: '+str(Worker.objects.get(pk=dmanager))

    # Если выбран клиент
    if customer_id:
        customer_query &= Q(customer__pk=customer_id)
    # Если выбран менеджер по ведению
    if customers1:
        customer_query &= Q(customer__in=customers1)
    # Если выбран менеджер по развитию
    if customers2:
        customer_query &= Q(customer__in=customers2)

    turnouts = WorkerTurnout.objects.filter(query).select_related("timesheet")
    turnout_values = turnouts.aggregate(
        perfs=Sum("performance"),
        hours=Sum("hours_worked"),
        turns=Count("pk"),
        workers=Count("worker", distinct=True),
        locations=Count("timesheet__cust_location_id", distinct=True)
    )
    performance = turnout_values.get("perfs", 0) or 0.0
    hours = turnout_values.get("hours", 0) or 0.0
    turns = turnout_values.get("turns", 0)
    worker_num = turnout_values.get("workers", 0)
    ordered_workers = CustomerOrder.objects.filter(
        customer_query
    ).aggregate(
        total_workers=Sum("number_of_workers")
    ).get("total_workers", 0) or 0
    noderived = ordered_workers - turns
    locations = turnout_values.get("locations",0.0) or 0.0
    timesheet_ids = turnouts.values_list("timesheet")
    timesheets = TimeSheet.objects.filter(
        pk__in=timesheet_ids
    ).annotate(
        turns=Count("worker_turnouts")
    ).annotate(
        noderived=F("customerorder__number_of_workers")-F("turns")
    )
    return render(
        request,
        'the_redhuman_is/timesheets.html',
        {
            'timesheets': timesheets,
            "total_values":
            {
                "performance": performance,
                "hours": hours,
                "turns": turns,
                "worker_num": worker_num,
                "locations": locations,
                "noderived": noderived
            },
            "display": display,
            "headers": header
        }
    )


# 6.2. Объекты табелей за период
@staff_account_required
def timesheet_locations(request):
    print(request.GET)
    beginStr = request.GET.get("begin")
    endStr = request.GET.get("end")
    #try:
    begin = datetime.strptime(beginStr,"%Y-%d-%m")
    end = datetime.strptime(endStr,"%Y-%d-%m")
    customer_id = request.GET.get("customer")
    header = dict()
    if begin == end:
        query = Q(sheet_date=begin)
        header['range'] = 'Выходы за ' + beginStr
    else:
        query = Q(sheet_date__range=(begin, end))
        header['range'] = 'Выходы c ' + beginStr + ' по ' + endStr

    customers1 = None
    mmanager = request.GET.get("mmanager")
    if mmanager:
        manager_set = models.MaintenanceManager.objects.filter(worker=mmanager)
        customers1 = []
        managers = ""
        for manager in manager_set:
            customers1.append(manager.customer.pk)
            managers += str(manager.worker) + "; "

        query &= Q(customer__in=customers1)
        header['maint_managers'] = 'Менеджеры по ведению: ' + managers

    customers2 = None
    dmanager = request.GET.get("dmanager")
    if dmanager:
        manager_set = models.DevelopmentManager.objects.filter(worker=dmanager)
        customers2 = []
        managers = ""
        for manager in manager_set:
            customers2.append(manager.customer.pk)
            managers += str(manager.worker) + "; "

        query &= Q(customer__in=customers2)
        header['dev_managers'] = 'Менеджеры по развитию: ' + managers

    # Если выбран клиент
    if customer_id:
        query &= Q(customer__pk=customer_id)
    # Если выбран менеджер по ведению
    if customers1:
        query &= Q(customer__in=customers1)
    # Если выбран менеджер по развитию
    if customers2:
        query &= Q(customer__in=customers2)

    timesheets = TimeSheet.objects.filter(query)
    ids = timesheets.values_list("cust_location")
    print(ids.count())
    locations = CustomerLocation.objects.filter(pk__in=ids).select_related("customer_id")
    return render(request, 'the_redhuman_is/timesheet_locations.html', {'locations': locations, "headers": header})
    #except:
    #    redirect('the_redhuman_is:timesheets')


# 7. Табели пустые, без рабочих
@staff_account_required
def empty_timesheets(request):
    timesheets = TimeSheet.objects.filter(is_executed=False, worker_turnouts__isnull=True)
    return render(request, 'the_redhuman_is/timesheets_open.html', {'timesheets': timesheets})


# 8. Табели открытые (с рабочими, но без часов)
@staff_account_required
def unexecuted_timesheets_hours_not(request):
    timesheets = TimeSheet.objects.exclude(worker_turnouts__isnull=True).filter(
        Q(is_executed=False, worker_turnouts__hours_worked=None) | Q(is_executed=False,
                                                                     worker_turnouts__hours_worked__lte=0)).distinct()
    return render(request, 'the_redhuman_is/timesheets_close.html', {'timesheets': timesheets})


# 9. Незакрытые табели
@staff_account_required
def unexecuted_timesheets(request):
    timesheets = TimeSheet.objects.exclude(worker_turnouts__isnull=True).filter(is_executed=False,
                                                                                worker_turnouts__hours_worked__gt=0).distinct()
    return render(request, 'the_redhuman_is/timesheets_close.html', {'timesheets': timesheets})


# 10. Закрыть табели
@staff_account_required
def execute_timesheets(request):
    timesheets = TimeSheet.objects.exclude(
        worker_turnouts__isnull=True
    ).filter(
        is_executed=False,
        worker_turnouts__hours_worked__gt=0
    ).distinct()
    for timesheet in timesheets:
        timesheet.is_executed=True
        timesheet.save()
    return redirect('the_redhuman_is:orders_dashboard')


@transaction.atomic
def _update_turnouts(request, timesheet, forms):
    warnings = []
    order = CustomerOrder.objects.get(timesheet=timesheet)
    customer_account = CustomerOperatingAccounts.objects.get(customer_id=timesheet.customer)

    # Получаем дополнительные поля
    fines, bonuses, cfines = _get_params(request.POST)

    # Т.к. зарплата бригадира может зависеть от показателей работы
    # всей бригады, сначала надо сохранить все выходы обычных рабочих
    indexes = []
    foreman_index = -1
    for i in range(len(forms)):
        form = forms[i]
        if form.is_valid():
            if foreman_index != -1 and form.cleaned_data.get('worker') == timesheet.foreman:
                foreman_index = i
            else:
                indexes.append(i)
    if foreman_index >= 0:
        indexes.append(foreman_index)

    for i in indexes:
        form = forms[i]
        turnout = form.save(commit=False)
        # In case it is brand new turnout
        turnout.timesheet = timesheet

        # Проверка на то, что мы не редактируем существующий выход, у которого залочена
        # операция начисления (скорее всего - есть в ведомости и была фактическая выплата)
        # и при этом увеличиваем часы (это запрещено, чтобы не генерировать фейковую прибыль
        # на пустом месте)
        if turnout.pk:
            saved_turnout = WorkerTurnout.objects.get(pk=turnout.pk)
            operation_to_pay = models.TurnoutOperationToPay.objects.filter(turnout=saved_turnout)
            if operation_to_pay.exists():
                operation = operation_to_pay.get().operation
                if operation.is_closed and (not saved_turnout.hours_worked or (saved_turnout.hours_worked < turnout.hours_worked)):
                    raise Exception(
                        'Выход {}: нельзя увеличивать часы у выходов с закрытой выплатой, заведите новый выход'.format(
                            saved_turnout
                        )
                    )

        # Todo: some other way to get data from field?
        service_pk_key = "form-{}-service".format(i)
        service_pk = request.POST.get(service_pk_key)
        if not service_pk:
            continue

        try:
            turnout.save()
        except NoWorkerPhoneException as e:
            warnings.append(
                'У работника по имени {} не заполнен (или неправильный) телефон!'.format(
                    turnout.worker
                )
            )
            continue

        customer_service = CustomerService.objects.get(
            pk=service_pk,
            customer=timesheet.customer,
        )

        turnout_service = models.TurnoutService.objects.filter(
            turnout=turnout
        )
        if turnout_service.exists():
            turnout_service = turnout_service.get()
            if turnout_service.customer_service != customer_service:
                turnout_service.customer_service = customer_service
                turnout_service.save()
        else:
            turnout_service = models.TurnoutService.objects.create(
                turnout=turnout,
                customer_service=customer_service
            )

        output_key_rx = re.compile(
            '^output_{}_{}_{}_(\d+)$'.format(
                i,
                timesheet.pk,
                turnout.worker.pk
            )
        )
        for key in request.POST.keys():
            m = output_key_rx.match(key)
            if m:
                box_type = models.BoxType.objects.get(pk=m.group(1))
                amount = int(request.POST[key])
                models.set_turnout_output(turnout, box_type, amount)

        deduction_worker = None
        try:
            with transaction.atomic():
                operator = DeliveryRequestOperator.objects.get(
                    request__requestworker__requestworkerturnout__workerturnout=turnout
                )
                deduction_worker = WorkerUser.objects.get(user=operator.operator).worker
        except ObjectDoesNotExist:
            pass

        update_turnout_payments(
            turnout.pk,
            request.user,
            deduction_worker,
            force_commit=True
        )

        worker = turnout.worker
        worker_operating_account = worker.worker_account

        # Просто вычет

        if i in fines:
            for fine in fines[i]:
                if 'operation' in fine and fine['operation']:
                    if 'amount' in fine:
                        operation = finance.models.Operation.objects.get(pk=fine['operation'])
                        finance.models.update_if_changed(
                            operation,
                            fine['amount'],
                            debit=worker_operating_account.account,
                            comment=fine['comment'],
                            timepoint=timesheet.sheet_date
                        )
                    else:
                        finance.models.Operation.objects.filter(pk=fine['operation']).delete()
                else:
                    if fine['amount'] > 0:
                        operation = finance.models.Operation.objects.create(
                            timepoint=timesheet.sheet_date,
                            author=request.user,
                            comment=fine['comment'],
                            debet=worker_operating_account.account,
                            credit=customer_account.account_90_1_disciplinary_deductions,
                            amount=fine['amount'],
                        )

                if 'fine_id' not in fine or fine['fine_id'] == '':
                    if fine['amount'] > 0:
                        turnout_fine = TurnoutDeduction.objects.create(
                            turnout=turnout,
                            operation=operation
                        )
                        turnout_fine.save()
                else:
                    if 'amount' not in fine:
                        TurnoutDeduction.objects.filter(pk=fine['fine_id']).delete()

        # Штраф со стороны клиенты

        if i in cfines:
            for fine in cfines[i]:
                if 'operation' in fine and fine['operation']:
                    customer_fine_operation = finance.models.Operation.objects.get(
                        pk=fine['operation']
                    )
                    customer_fine_deduction = CustomerFineDeduction.objects.get(
                        fine=customer_fine_operation
                    )

                    if 'amount' in fine:
                        amount = decimal.Decimal(fine['amount'])
                        if customer_fine_operation.amount == amount:
                            deduction = customer_fine_deduction.deduction
                            account = worker_operating_account.account
                            if deduction.debet != account:
                                deduction.debet = account
                                deduction.save()
                        else:
                            finance.models.update_if_changed(
                                customer_fine_deduction.deduction,
                                amount,
                                worker_operating_account.account,
                                comment='На основании штрафа от {} "{}"'.format(
                                    customer_fine_operation.timepoint.strftime('%d.%m.%Y'),
                                    fine['comment']
                                ),
                                timepoint=timesheet.sheet_date
                            )

                        finance.models.update_if_changed(
                            customer_fine_operation,
                            amount,
                            credit=customer_account.account_76_debts,
                            comment=fine['comment'],
                            timepoint=timesheet.sheet_date
                        )
                    else:
                        finance.models.Operation.objects.filter(
                            pk=customer_fine_operation.pk).delete()
                        finance.models.Operation.objects.filter(
                            pk=customer_fine_deduction.deduction.pk).delete()
                        CustomerFine.objects.filter(pk=customer_fine_operation.pk).delete()
                        TurnoutDeduction.objects.filter(
                            pk=customer_fine_deduction.deduction.pk).delete()
                        customer_fine_deduction.delete()
                else:
                    if 'amount' in fine and fine['amount'] > 0:
                        # Fine
                        turnout_service = turnout.turnoutservice
                        customer_fine_operation = finance.models.Operation.objects.create(
                            timepoint=timesheet.sheet_date,
                            author=request.user,
                            comment=fine['comment'],
                            debet=customer_account.account_76_fines,
                            credit=customer_account.account_76_debts,
                            amount=fine['amount'],
                        )

                        CustomerFine.objects.create(
                            turnout=turnout,
                            operation=customer_fine_operation
                        )

                        # Deduction
                        worker_operating_account = turnout.worker.worker_account
                        customer_deduction_operation = finance.models.Operation.objects.create(
                            timepoint=timesheet.sheet_date,
                            author=request.user,
                            comment='На основании штрафа от ' + str(
                                customer_fine_operation.timepoint.strftime('%d.%m.%Y')
                            ) + ' "' + fine['comment'] + '"',
                            debet=worker_operating_account.account,
                            credit=customer_account.account_90_1_fine_based_deductions,
                            amount=fine['amount'],
                        )

                        TurnoutDeduction.objects.create(
                            operation=customer_deduction_operation,
                            turnout=turnout
                        )

                        CustomerFineDeduction.objects.create(
                            fine=customer_fine_operation,
                            deduction=customer_deduction_operation
                        )

#        # Бонусы (использование временно (?) заблокировано)
#        #
#        if i in bonuses:
#            for bonus in bonuses[i]:
#                if 'operation' in bonus and bonus['operation']:
#                    if 'amount' in bonus:
#                        operation = finance.models.Operation.objects.get(pk=bonus['operation'])
#                        operation.amount = bonus['amount']
#                        operation.debet = debet
#                        operation.comment = bonus['comment']
#                        operation.save()
#                    else:
#                        finance.models.Operation.objects.filter(pk=bonus['operation']).delete()
#                else:
#                    if bonus['amount'] > 0:
#                        operation = finance.models.Operation.objects.create(
#                            timepoint=timesheet.sheet_date,
#                            author=request.user,
#                            comment=bonus['comment'],
#                            debet=debet,
#                            credit=worker_operating_account.account,
#                            amount=bonus['amount'],
#                        )
#
#                if 'bonus_id' not in bonus or bonus['bonus_id'] == '':
#                    if bonus['amount'] > 0:
#                        turnout_bonus = TurnoutBonus.objects.create(
#                            turnout=turnout,
#                            operation=operation
#                        )
#                        turnout_bonus.save()
#                else:
#                    if 'amount' not in bonus:
#                        TurnoutBonus.objects.filter(pk=bonus['bonus_id']).delete()

#    # Теперь нет
#    # Т.к. есть калькуляторы, учитывающие суммарное количество часов за сутки,
#    # обновляем все остальные выходы у этого клиента за это число
#    turnouts = WorkerTurnout.objects.filter(
#        timesheet__sheet_date=timesheet.sheet_date,
#        timesheet__customer=timesheet.customer,
#        turnoutservice__isnull=False,
#    ).exclude(
#        timesheet=timesheet
#    ).distinct(
#    )
#    for turnout in turnouts:
#        models.update_turnout_payments(turnout, request.user)

    return warnings, fines, bonuses, cfines


# 12. Добавить часы в табель с рабочими
# Todo: refactor
@staff_account_required
def add_hours(request, pk):
    turnout_output = []

    timesheet = TimeSheet.objects.get(pk=pk)
    turnouts = WorkerTurnout.objects.filter(timesheet=timesheet)
    warnings = []
    fines = {}
    bonuses = {}
    cfines = {}

    if request.method == "POST":
        formset = WorkerTurnoutFormSet(request.POST, request.FILES, queryset=turnouts)
        if formset.is_valid():
            warnings, fines, bonuses, cfines = _update_turnouts(request, timesheet, formset)

        if not warnings:
            return redirect("the_redhuman_is:timesheet", pk=pk)
    else:
        formset = WorkerTurnoutFormSet(queryset=turnouts)

        cfines_set = CustomerFine.objects.filter(turnout__in=turnouts).order_by('id')

        customer_fines = []
        for customer_fine in cfines_set:
            customer_fines.append(customer_fine.operation.id)

        customer_fines_deductions = CustomerFineDeduction.objects.filter(fine__in=customer_fines).order_by('id')
        customer_deductions = []
        for customer_fine_deduction in customer_fines_deductions:
            customer_deductions.append(customer_fine_deduction.deduction_id)

        fines_set = TurnoutDeduction.objects.filter(turnout__in=turnouts).exclude(operation__in=customer_deductions).order_by('id')
        bonuses_set = TurnoutBonus.objects.filter(turnout__in=turnouts).order_by('id')

        for cfine in cfines_set:
            if cfine.turnout_id not in cfines:
                cfines[cfine.turnout_id] = []
            amount = cfine.operation.amount
            if amount is None:
                cfine.operation.amount = ''
            else:
                cfine.operation.amount = str(amount).replace(',', '.')
            cfines[cfine.turnout_id].append(cfine)

        for fine in fines_set:
            if fine.turnout_id not in fines:
                fines[fine.turnout_id] = []
            amount = fine.operation.amount
            if amount is None:
                fine.operation.amount = ''
            else:
                fine.operation.amount = str(amount).replace(',', '.')
            fines[fine.turnout_id].append(fine)

        for bonus in bonuses_set:
            if bonus.turnout_id not in bonuses:
                bonuses[bonus.turnout_id] = []
            amount = bonus.operation.amount
            if bonus.operation.amount is None:
                bonus.operation.amount = ''
            else:
                bonus.operation.amount = str(amount).replace(',', '.')
            bonuses[bonus.turnout_id].append(bonus)

        for i in range(len(turnouts)):
            turnout_service = models.TurnoutService.objects.filter(turnout=turnouts[i])
            if turnout_service.exists():
                turnout_service = turnout_service.get()
                customer_service = turnout_service.customer_service
                formset[i].fields["service"].initial = customer_service

            if turnouts[i].id not in fines:
                fines[turnouts[i].id] = []
                fines[turnouts[i].id].append({'val': '', 'comment': ''})

            if turnouts[i].id not in bonuses:
                bonuses[turnouts[i].id] = []
                bonuses[turnouts[i].id].append({'val': '', 'comment': ''})

            if turnouts[i].id not in cfines:
                cfines[turnouts[i].id] = []
                cfines[turnouts[i].id].append({'val': '', 'comment': ''})

        fines[0] = []
        fines[0].append({'val': '', 'comment': ''})
        bonuses[0] = []
        bonuses[0].append({'val': '', 'comment': ''})
        cfines[0] = []
        cfines[0].append({'val': '', 'comment': ''})

        box_types = models.BoxType.objects.filter(customer=timesheet.customer)
        for box_type in box_types:
            data = {}
            data['box_type'] = box_type
            data['output'] = []
            for turnout in turnouts:
                pk = 0
                amount = 0
                output = models.TurnoutOutput.objects.filter(
                    turnout=turnout,
                    box_type=box_type
                )
                if output.exists():
                    amount = output.get().amount
                    pk = output.get().pk
                data['output'].append((pk, amount, turnout.worker.pk))

            data['output'].append((0, 0, 0))

            turnout_output.append(data)

    return render(
        request,
        'the_redhuman_is/new_turnouts.html',
        {
            'warnings': warnings,
            'formset': formset,
            'customer': timesheet.customer,
            'fines': fines,
            'bonuses': bonuses,
            'cfines': cfines,
            'turnout_output': turnout_output,
            'timesheet': timesheet,
        }
    )


# 13. Новый табель без часов
@staff_account_required
def new_timesheet(request, pk):
    order = get_object_or_404(CustomerOrder, pk=pk)
    if request.method == "POST":
        tform = TimeSheetForm(request.POST, request.FILES)
        if tform.is_valid():
            timesheet = tform.save(commit=False)
            timesheet.is_executed = False

            RecruitmentOrder.objects.filter(customer_order=order).update(is_actual=False)
            timesheet.save()
            order.timesheet = timesheet
            order.save(update_fields=['timesheet'])
            return redirect('the_redhuman_is:orders_dashboard')
    else:
        tform = TimeSheetForm(
            initial={
                'sheet_date': order.on_date,
                'sheet_turn': order.bid_turn,
                'customer': order.customer,
                'cust_location': order.cust_location,
            }
        )
    return render(request, 'the_redhuman_is/new_timesheet.html', {'tform': tform})


# 13. Редактирование табеля
@staff_account_required
def edit_timesheet(request, pk):
    timesheet = get_object_or_404(TimeSheet, pk=pk)

    if request.method == "POST":
        tform = TimeSheetForm(request.POST, request.FILES, instance=timesheet)
        if tform.is_valid():
            timesheet = tform.save()
            return redirect('the_redhuman_is:timesheet', pk=timesheet.id)
    else:
        tform = TimeSheetForm(instance=timesheet)

    return render(request, 'the_redhuman_is/edit_timesheet.html', {'pk': pk, 'tform': tform})


# Todo: there is some 'copy-paste' here
@require_POST
@staff_account_required
@transaction.atomic
def remove_worker(request, timesheet_pk, worker_pk):
    turnout = WorkerTurnout.objects.filter(
        timesheet__pk=timesheet_pk,
        worker__pk=worker_pk
    ).first()

    act = Act.objects.filter(
        turnout=turnout
    )
    if act.exists():
        act.get().delete()

    worker_operation = models.TurnoutOperationToPay.objects.filter(
        turnout=turnout
    )
    if worker_operation.exists():
        worker_operation = worker_operation.get()
        operation = worker_operation.operation
        paysheet_entry = models.Paysheet_v2EntryOperation.objects.filter(
            operation=operation
        )
        if paysheet_entry.exists():
            paysheet_entry.get().delete()
        worker_operation.delete()
        operation.delete()

    def _remove_turnout_operation(TurnoutOperation, turnout):
        turnout_operation = TurnoutOperation.objects.filter(
            turnout=turnout
        )
        if turnout_operation.exists():
            turnout_operation = turnout_operation.get()
            operation = turnout_operation.operation
            paysheet_entry = models.Paysheet_v2EntryOperation.objects.filter(
                operation=operation
            )
            if paysheet_entry.exists():
                paysheet_entry.get().delete()
            turnout_operation.delete()
            operation.delete()

    _remove_turnout_operation(models.TurnoutOperationToPay, turnout)
    _remove_turnout_operation(models.TurnoutCustomerOperation, turnout)
    _remove_turnout_operation(models.HostelBonusOperation, turnout)

    # Todo: tax & other

    turnout.delete()

    return redirect('the_redhuman_is:timesheet', pk=timesheet_pk)


# 14. Добавить фото в табель
@staff_account_required
def new_timesheet_to_close(request, pk):
    timesheet = get_object_or_404(TimeSheet, pk=pk)
    if request.method == "POST":
        tform = TimeSheetForm(request.POST, request.FILES, instance=timesheet)
        if tform.is_valid():
            timesheet = tform.save(commit=False)
            timesheet.is_executed = False
            timesheet.save()
            return redirect('the_redhuman_is:orders_dashboard')
    else:
        tform = TimeSheetForm(instance=timesheet)
    return render(request, 'the_redhuman_is/new_timesheet.html', {'tform': tform})


@staff_account_required
def new_contracts(request):
    """15. Добавить договоры в панели для заявок"""
    if request.method == "POST":
        wform = ToAddContractForm(request.POST)
        formset = ContractFormSet(request.POST, request.FILES)
        if wform.is_valid():
            ids = []
            d = wform.cleaned_data
            for worker in d["workers"]:
                contract = Contract.objects.create(c_worker=worker)
                contract.end_date = worker.m_date_of_exp
                contract.save()
                ids.append(contract.id)
            contracts = Contract.objects.filter(pk__in=ids)
            formset = ContractFormSet(queryset=contracts)
            formset.extra = 0
            return render(request, 'the_redhuman_is/new_contracts.html', {'formset': formset})
        if formset.is_valid():
            contracts = formset.save(commit=False)
            for contract in contracts:
                contract.save()
            return redirect('the_redhuman_is:orders_dashboard')
    else:
        wform = ToAddContractForm()
        formset = ContractFormSet()
    return render(request, 'the_redhuman_is/new_contracts.html', {'wform': wform})


# Карточка табеля
@staff_account_required
def timesheet(request, pk):
    obj = get_object_or_404(TimeSheet, pk=pk)
    try:
        request.user.groups.get(name='Менеджеры')
        try:
            models.Customer.objects.filter(
                maintenancemanager__worker__workeruser__user=request.user
            ).get(pk=obj.customer.pk)
        except Customer.DoesNotExist:
            raise PermissionDenied
    except Group.DoesNotExist:
        pass

    timesheet_images = Photo.objects.filter(
        object_id=obj.id,
        content_type=ContentType.objects.get_for_model(obj)
    )

    turnouts = obj.worker_turnouts.all()
    hours_worked = turnouts.aggregate(
        Sum('hours_worked')
    ).get('hours_worked__sum') or 0

    fines_set = CustomerFine.objects.filter(turnout__in=turnouts).order_by('id')

    fines = {}
    for fine in fines_set:
        if fine.turnout_id not in fines:
            fines[fine.turnout_id] = []
        if fine.operation.amount is None:
            fine.operation.amount = ''
        fines[fine.turnout_id].append(fine)

    for i in range(len(turnouts)):
        if turnouts[i].id not in fines:
            fines[turnouts[i].id] = []
            fines[turnouts[i].id].append({'val': '', 'comment': ''})

    fines[0] = []
    fines[0].append({'val': '', 'comment': ''})

    return render(
        request,
        "the_redhuman_is/timesheet.html",
        {
            "timesheet": obj,
            "timesheet_images": timesheet_images,
            "turnouts": turnouts,
            "hours_worked": hours_worked,
            "fines": fines,
            "is_for_customer": False
        }
    )


def open_timesheet(request, pk):
    timesheet = TimeSheet.objects.get(pk=pk)
    timesheet.is_executed = False
    timesheet.save()
    return redirect('the_redhuman_is:timesheet', pk=pk)


def close_timesheet(request, pk):
    TimeSheet.objects.filter(pk=pk).update(is_executed=True)
    return redirect('the_redhuman_is:timesheet', pk=pk)


def _image_or_login(request, customer, image):
    account = views.utils.get_customer_account(request)
    if account:
        if customer != account.customer:
            return redirect("login")
    return views.utils.render_image(request, image)


# Страница с изображением табеля
@login_required
def timesheet_image(request, pk):
    timesheet = TimeSheet.objects.get(pk=pk)
    return _image_or_login(request, timesheet.customer, timesheet.image)


# Страница с изображением табеля
@login_required
def timesheet_image2(request, pk):
    timesheet = TimeSheet.objects.get(pk=pk)
    return _image_or_login(request, timesheet.customer, timesheet.image2)


# Страница с изображением табеля
@login_required
def timesheet_image3(request, pk):
    timesheet = TimeSheet.objects.get(pk=pk)
    return _image_or_login(request, timesheet.customer, timesheet.image3)


# Страница с изображением табеля
@login_required
def timesheet_image4(request, pk):
    timesheet = TimeSheet.objects.get(pk=pk)
    return _image_or_login(request, timesheet.customer, timesheet.image4)


def _timesheet_delay(request, timesheet):
    if request.GET.get('delay_type') == 'after':
        expired, delay = timesheet.closing_delay()
    else: # assume 'before'
        expired, delay = timesheet.creation_delay()

    if delay is None:
        delay_str = '-'
    else:
        if delay == timedelta():
            delay_str = '0'
        else:
            delay_str = time_interval_format(delay, nbsp=True)

    return expired, delay_str


@staff_account_required
def timesheet_timeliness(request):
    first_day = timezone.now().replace(day=1)
    first_day_param = request.GET.get('first_day')
    if first_day_param:
        first_day = date_time_from_string(first_day_param)

    last_day = timezone.now()
    last_day_param = request.GET.get('last_day')
    if last_day_param:
        last_day = date_time_from_string(last_day_param)

    timesheets = TimeSheet.objects.filter(
        sheet_date__gte=first_day,
        sheet_date__lte=last_day
    ).distinct()

    locations_dict = timesheets.values('cust_location').distinct()
    locations = CustomerLocation.objects.filter(
        pk__in=[l['cust_location'] for l in locations_dict]
    )

    manager = None
    manager_param = request.GET.get('manager')
    if manager_param:
        manager = Worker.objects.get(pk=int(manager_param))
        locations = locations.filter(customer_id__maintenancemanager__worker=manager)

    days = [
        first_day + timedelta(days=d) for d in range(0, (last_day-first_day).days + 1)
    ]

    data = []

    expired_by_day = [0 for day in days]

    for location in locations:
        for shift in ['День', 'Ночь']:
            row = []
            expired_timesheets = 0
            for i in range(len(days)):
                day = days[i]
                day_timesheets = []
                for timesheet in timesheets.filter(sheet_date=day, cust_location=location, sheet_turn=shift):
                    expired, delay = _timesheet_delay(request, timesheet)
                    day_timesheets.append((timesheet, delay))
                    if expired:
                        expired_timesheets += 1
                        expired_by_day[i] += 1
                row.append(day_timesheets)
            data.append((location, shift, row, expired_timesheets))

    return render(
        request,
        'the_redhuman_is/reports/timesheet_timeliness.html',
        {
            'filter_form': TimesheetTimelinessForm(
                initial={
                    'manager': manager,
                    'first_day': first_day,
                    'last_day': last_day,
                    'delay_type': request.GET.get('delay_type', 'before'),
                }
            ),
            'days': days,
            'expired_by_day': expired_by_day,
            'data': data,
            'expired_overall': sum(expired_by_day)
        }
    )
