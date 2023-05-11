# -*- coding: utf-8 -*-
import finance
import io
import zipfile

from django.db import transaction

from finance import model_utils

from django.shortcuts import (
    get_object_or_404,
    redirect,
    render,
)
from django.http import HttpResponse
from django.utils import timezone
from django.db.models import (
    Q,
    Sum,
)

from the_redhuman_is.models import (
    Act,
    Rko,
    RkoOperation,
    Worker,
    WorkerTurnout,
)

from the_redhuman_is.forms import (
    CustomOperationForm,
    CutedOperationForm,
    OperationForm,
    WorkerSearchForm,
)

from . import (
    excel,
    models,
)
from .auth import staff_account_required
from .exceptions import MigException, ContractException


""" Касса """
# Выплата зарплаты рабочим
@staff_account_required
def to_pay_salary(request, pk, msg=None):
    worker = get_object_or_404(Worker, pk=pk)
    if request.method == "POST":
        form = WorkerSearchForm(data=request.POST or None)
        if form.is_valid():
            worker = form.cleaned_data["worker"]

    rkos = models.Rko.objects.filter(worker=worker, is_actual=True, rkooperation__isnull=True)
    rko = None
    if rkos.exists():
        rko = rkos.first()
    kass_root = model_utils.get_account("50. Касса")
    acc_kass = finance.models.Account.objects.get(name__istartswith="Касса старая", parent=kass_root)

    user = request.user
    k_op = finance.models.Operation.objects.filter(
        Q(debet=acc_kass) | Q(credit=acc_kass)).order_by("id").last()

    total_kd_ops = acc_kass.turnover_debet()
    total_kc_ops = acc_kass.turnover_credit()
    kass_saldo = acc_kass.turnover_saldo()
    turnouts = worker.worker_turnouts.filter(
        is_payed=False,
        act__isnull=True
    )
    turnouts = turnouts.prefetch_related('worker', 'timesheet',
                                         'timesheet__customer',
                                         'timesheet__cust_location')
    turnouts = turnouts.order_by('timesheet')

    avgs = worker.worker_turnouts.filter(
        is_payed=False,
        act__isnull=True
    ).aggregate(
        Sum('turnoutoperationtopay__operation__amount'),
        Sum('hours_worked')
    )

    acts = worker.worker_turnouts.filter(
        is_payed=False,
        act__isnull=False,
        act__rko__isnull=True
    ).order_by('timesheet')

    acts_avgs = worker.worker_turnouts.filter(
        is_payed=False,
        act__isnull=False,
        act__rko__isnull=True
    ).aggregate(
        Sum('hours_worked'),
        Sum('turnoutoperationtopay__operation__amount')
    )

    rko_avgs = worker.worker_turnouts.filter(
        is_payed=False,
        act__isnull=False,
        act__rko__isnull=False,
        act__rko__is_actual=True
    ).aggregate(
        Sum('hours_worked'),
        Sum('turnoutoperationtopay__operation__amount')
    )

    acts_in_rko = worker.worker_turnouts.filter(
        is_payed=False,
        act__isnull=False,
        act__rko__isnull=False,
        act__rko=rko
    ).order_by('timesheet')

    operating_account = worker.worker_account
    worker_acc = operating_account.account
    w_ops = finance.models.Operation.objects.filter(Q(debet=worker_acc) | Q(credit=worker_acc))
    total_wd_ops = worker_acc.turnover_debet()
    total_wc_ops = worker_acc.turnover_credit()
    worker_saldo = - worker_acc.turnover_saldo()
    if acts_avgs['turnoutoperationtopay__operation__amount__sum'] is None and rko_avgs['turnoutoperationtopay__operation__amount__sum'] is None:
        saldo_1 = worker_saldo
        saldo_2 = 0
    elif acts_avgs['turnoutoperationtopay__operation__amount__sum'] is not None and rko_avgs['turnoutoperationtopay__operation__amount__sum'] is None:
        saldo_1 = worker_saldo - acts_avgs['turnoutoperationtopay__operation__amount__sum']
        saldo_2 = acts_avgs['turnoutoperationtopay__operation__amount__sum']
    elif acts_avgs['turnoutoperationtopay__operation__amount__sum'] is not None and rko_avgs['turnoutoperationtopay__operation__amount__sum'] is not None:
        saldo_1 = worker_saldo - acts_avgs['turnoutoperationtopay__operation__amount__sum']
        saldo_2 = rko_avgs['turnoutoperationtopay__operation__amount__sum']
    elif acts_avgs['turnoutoperationtopay__operation__amount__sum'] is None and rko_avgs['turnoutoperationtopay__operation__amount__sum'] is not None:
        saldo_1 = worker_saldo - rko_avgs['turnoutoperationtopay__operation__amount__sum']
        saldo_2 = rko_avgs['turnoutoperationtopay__operation__amount__sum']
    form = WorkerSearchForm()
    form_po = CutedOperationForm(
        initial={
            'debet': worker_acc,
            'credit': acc_kass,
            'author': user,
            'amount': saldo_1,
        }
    )
    form_acts = CutedOperationForm(
        initial={
            'debet': worker_acc,
            'credit': acc_kass,
            'author': user,
            'amount': saldo_2,
        }
    )
    return render(request, 'the_redhuman_is/cashier-salary.html', {
        'form': form,
        'form_po': form_po,
        'form_acts': form_acts,
        'worker': worker,
        'k_op': k_op,
        'w_ops': w_ops,
        'total_wd_ops': total_wd_ops,
        'total_wc_ops': total_wc_ops,
        'total_kd_ops': total_kd_ops,
        'total_kc_ops': total_kc_ops,
        'kass_saldo': kass_saldo,
        'worker_saldo': worker_saldo,
        'acc_kass': acc_kass,
        'turnouts': turnouts,
        'acts': acts,
        'avgs': avgs,
        'acts_avgs': acts_avgs,
        'rko': rko,
        'acts_in_rko': acts_in_rko,
        'rko_avgs': rko_avgs,
        'msg': msg
        })


# Провести РКО
def form_acts(request, pk):
    rko = Rko.objects.get(pk=pk)
    if request.method == "POST":
        form_acts = CutedOperationForm(request.POST or None)
        if form_acts.is_valid():
            with transaction.atomic():
                operation = form_acts.save(commit=False)
                account = form_acts.cleaned_data["debet"]
                operating_account = account.worker_account
                worker = operating_account.worker
                operation.save()
                comment = 'РКО №{0} от {1}, '.format(rko.id, rko.date)
                turnouts = worker.worker_turnouts.filter(
                    turnoutoperationtopay__operation__paysheet_entry_operations__isnull=True,
                    act__isnull=False,
                    act__rko=rko
                )
                for turnout in turnouts:
                    act = Act.objects.get(turnout=turnout)
                    turnout.is_payed = True
                    turnout.save(update_fields=['is_payed'])
                    comment += 'Табель №{0} от {1} Клиент: {2}-{3}-{4} {5} Акт №{6} от {7}, '.format(
                        turnout.timesheet.pk,
                        turnout.timesheet.sheet_date,
                        turnout.timesheet.customer,
                        turnout.timesheet.cust_location,
                        turnout.timesheet.sheet_turn,
                        worker.position,
                        act.pk,
                        act.date
                    )
                rko.is_actual = False
                rko.save(update_fields=['is_actual'])
                operation.comment = comment
                operation.save(update_fields=['comment'])
                RkoOperation.objects.create(rko=rko, operation=operation)

    return redirect('the_redhuman_is:to_pay_salary', pk=worker.pk)


# Провести выходы
# Todo: Get rid of this. There are paysheets for that.
def form_po(request, pk):
    if request.method == "POST":
        form_po = CutedOperationForm(request.POST or None)
        if form_po.is_valid():
            with transaction.atomic():
                operation = form_po.save(commit=False)
                account = form_po.cleaned_data["debet"]
                operating_account = account.worker_account
                worker = operating_account.worker
                operation.save()
                turnouts = worker.worker_turnouts.filter(
                    act__isnull=True
                )
                if turnouts.exists():
                    operation.comment += ' '
                turnouts.update(is_payed=True)
                for turnout in turnouts:
                    models.TurnoutOperationIsPayed.objects.create(
                        turnout=turnout,
                        operation=operation
                    )
                    operation.comment += 'Табель №{0} от {1} Клиент: {2}-{3}-{4} {5}, '.format(
                        turnout.timesheet.pk,
                        turnout.timesheet.sheet_date,
                        turnout.timesheet.customer,
                        turnout.timesheet.cust_location,
                        turnout.timesheet.sheet_turn,
                        worker.position
                    )
                operation.save(update_fields=['comment'])

    return redirect('the_redhuman_is:to_pay_salary', pk=worker.pk)


# Создать РКО
def create_rko(request, pk):
    worker = Worker.objects.get(pk=pk)
    if Rko.objects.filter(worker=worker, is_actual=True).exists():
        return redirect('the_redhuman_is:to_pay_salary', pk=worker.pk)
    else:
        rko = Rko.objects.create(
            date=timezone.now(),
            worker=worker,
        )
        return redirect('the_redhuman_is:to_pay_salary', pk=worker.pk)


# Добавить акт в расходник
@staff_account_required
def add_act_into_rko(request, pk, pk_rko):
    act = Act.objects.get(turnout__pk=pk)
    if Rko.objects.filter(pk=pk_rko).exists():
        rko = Rko.objects.get(pk=pk_rko)
        act.rko = rko
        act.save(update_fields=['rko'])
        return redirect('the_redhuman_is:to_pay_salary', pk=rko.worker.pk)
    else:
        return redirect('the_redhuman_is:to_pay_salary', pk=act.turnout.worker.pk)


# Поменять статус на "Оплачено" всем Актам для конкретного рабочего
@staff_account_required
def all_acts_status_change(request, pk):
    WorkerTurnout.objects.filter(worker_id__pk=pk, is_payed=False).update(is_payed=True)
    return redirect('the_redhuman_is:to_pay_salary', pk=pk)


# Скачать акты
@staff_account_required
def download_acts(request, pk):
    worker = Worker.objects.get(pk=pk)
    acts = WorkerTurnout.objects.filter(worker_id=worker, act__isnull=False)
    response = HttpResponse(content_type='application/zip')
    today = timezone.now()
    response['Content-Disposition'] = "attachment; filename*=''Acts-{0}.zip".format(today.strftime("%d-%m-%Y"))
    proxyFile = io.BytesIO()
    with zipfile.ZipFile(proxyFile, "w") as myzip:
        try:
            for act in acts:
                contract_values = act.make_multiple_dict()
                for i in range(0,len(contract_values)):
                    values = contract_values[i]
                    buffer = io.BytesIO()
                    doc = excel.create_act(values)
                    doc.save(buffer)
                    filename = "contract"+str(i)+"/"+"{0}-No{1}-{2}.xls".format(act.date, act.id, worker)
                    myzip.writestr(filename, buffer.getvalue())
        except MigException as exc:
            return redirect('the_redhuman_is:worker_edit', pk=worker.pk ,msg=exc.get_value())
        except ContractException as exc:
            return redirect('the_redhuman_is:to_pay_salary', pk=worker.pk, msg=str(exc))
    response.write(proxyFile.getvalue())
    return response


# Скачать РКО
@staff_account_required
def download_rko(request, pk):
    today = timezone.now()
    rko = Rko.objects.get(pk=pk)
    values = rko.make_dict()
    doc = excel.create_rko(values)
    response = HttpResponse(content_type='application/ms-excel')
    response['Content-Disposition'] = 'attachment; filename={0} {1}.xls'.format(rko.pk, rko.date.strftime("%d-%m-%Y"))
    doc.save(response)
    return response


# Создать операцию
@staff_account_required
def create_operation(request, item):
    user = request.user
    item = item
    if request.method == "POST":
        form = OperationForm(request.POST or None)
        if form.is_valid():
            operation = form.save(commit=False)
            operation.save()
            return redirect('the_redhuman_is:cashier_workspace')
    else:
        # Касса
        # Платеж за общехозяйственные расходы
        if item == "1":
            debet = model_utils.get_account("26")
            credit = model_utils.get_account("Касса старая")
        # Выдача денег подотчетному лицу
        elif item == "2":
            debet = model_utils.get_account("71")
            credit = model_utils.get_account("Касса старая")
        # Расчетный счет
        # Платеж на 302 счет
        elif item == "3":
            debet = model_utils.get_account("76")
            credit = model_utils.get_account("51. Юнистрим")
        # Платеж за общехозяйственные расходы
        elif item == "4":
            debet = model_utils.get_account("26")
            credit = model_utils.get_account("51. Юнистрим")
        # Выплата з/п
        elif item == "5":
            debet = model_utils.get_account("70")
            credit = model_utils.get_account("51. Юнистрим")
        # Уплата налогов
        elif item == "6":
            debet = model_utils.get_account("26")
            credit = model_utils.get_account("51. Юнистрим")
            comment = "Уплата налога ___ за период с ___ по ___"
        # Поступление наличных от переводов
        elif item == "7":
            debet = model_utils.get_account("51. Юнистрим")
            credit = model_utils.get_account("76")
        # Поступление от клиента (редкость маловероятная)
        elif item == "8":
            debet = model_utils.get_account("51. Юнистрим")
            credit = model_utils.get_account("62")
        form = OperationForm(initial={
            'debet': debet,
            'credit': credit,
            'author': user
            })
        return render(
            request,
            'the_redhuman_is/create_operations.html',
            {
                'form': form
            }
        )


# Создать операцию из списка на выбор
@staff_account_required
def choose_operation(request):
    user = request.user
    if request.method == "POST":
        o_form = CustomOperationForm(request.POST or None)
        if o_form.is_valid():
            item = o_form.cleaned_data['choice']
            comment = o_form.cleaned_data['comment']
            amount = o_form.cleaned_data['amount']
            # Платеж за общехозяйственные расходы
            if item == "Платеж за общехозяйственные расходы":
                debet = model_utils.get_account("26")
                credit = model_utils.get_account("Касса старая")
            # Выдача денег подотчетному лицу
            elif item == "Выдача денег подотчетному лицу":
                debet = model_utils.get_account("71")
                credit = model_utils.get_account("Касса старая")
            # Расчетный счет
            # Платеж на 302 счет
            elif item == "Платеж на 302 счет":
                debet = model_utils.get_account("76")
                credit = model_utils.get_account("51. Юнистрим")
            # Платеж за общехозяйственные расходы
            elif item == "Платеж за общехозяйственные расходы":
                debet = model_utils.get_account("26")
                credit = model_utils.get_account("51. Юнистрим")
            # Уплата налогов
            elif item == "Уплата налогов":
                debet = model_utils.get_account("26")
                credit = model_utils.get_account("51. Юнистрим")
                comment = "Уплата налога ___ за период с ___ по ___"
            # Поступление наличных от переводов
            elif item == "Поступление наличных от переводов на р/с":
                debet = model_utils.get_account("51. Юнистрим")
                credit = model_utils.get_account("76")
            # Поступление от клиента (редкость маловероятная)
            elif item == "Поступление от клиента":
                debet = model_utils.get_account("51. Юнистрим")
                credit = model_utils.get_account("62")

            operation = finance.models.Operation.objects.create(
                timepoint=timezone.now(),
                author=request.user,
                comment=comment,
                debet=debet,
                credit=credit,
                amount=amount
            )
            return redirect('the_redhuman_is:cashier_workspace')
    else:
        o_form = CustomOperationForm()
        return render(request, 'the_redhuman_is/create_operations.html', {'o_form': o_form,})


def acts(request):
    acts = Act.objects.all()
    return render(request, 'the_redhuman_is/acts.html', {'acts': acts,})
