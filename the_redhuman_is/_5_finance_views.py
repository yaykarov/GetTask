# -*- coding: utf-8 -*-

import decimal
import datetime

import xlwt

from django.contrib.contenttypes.models import ContentType
from django.contrib.postgres.aggregates import ArrayAgg

from django.db import transaction

from django.db.models import (
    Exists,
    Min,
    OuterRef,
    Q,
    Subquery,
)
from django.http import (
    HttpResponse,
    JsonResponse,
)
from django.shortcuts import (
    render,
    redirect,
)
from django.views.decorators.http import require_POST

import finance
from finance import model_utils
from finance.models import Account

from .auth import staff_account_required

from the_redhuman_is.forms import (
    CustomerSelectionForm,
    DaysIntervalForm,
    ExpenseSelectionForm,
    LegalEntitySelectionForm,
    MakeExpenseForm,
    OperationForm,
    WorkerSearchForm,
    _rename_field,
)

from the_redhuman_is import models
from the_redhuman_is.models import (
    AccountablePerson,
    Act,
    AdministrationCostType,
    Customer,
    CustomerLocation,
    CustomerOperatingAccounts,
    IndustrialCostType,
    LegalEntity,
    PeriodCloseDocument,
    Reconciliation,
    Rko,
    SheetPeriodClose,
    TimeSheet,
)

from the_redhuman_is.services.finance.period_closure import create_period_closure_document

from the_redhuman_is.services.app_flavors import is_app_flavor_master

from the_redhuman_is.views.utils import get_first_last_day


""" Учет """
# Todo: remove
# Карточка счета
@staff_account_required
def account_detail(request, pk):
    return HttpResponse("moved to operating_account.detail")


# Todo: remove
# Обновить имя счета l1 каждого рабочего на 70
@staff_account_required
def accs_to_all(request):
    return HttpResponse("this one was removed")


# Карточка счета рабочего
@staff_account_required
def detalisation_70(request):
    operating_accounts = models.WorkerOperatingAccount.objects.all()
    return render(
        request,
        "the_redhuman_is/70-detalisation.html",
        {
            "operating_accounts": operating_accounts
        }
    )


# Выгрузить акты в ЗУП (excel)
@staff_account_required
def export_deeds_xls(request):
    default_style = xlwt.XFStyle()

    date_style = xlwt.XFStyle()
    date_style.num_format_str = 'DD.MM.YYYY'

    columns = [
        ('Фамилия',                  'turnout__worker__last_name',                                     default_style),
        ('Имя',                      'turnout__worker__name',                                          default_style),
        ('Отчество',                 'turnout__worker__patronymic',                                    default_style),
        ('Дата рождения',            'turnout__worker__birth_date',                                    date_style),
        ('Номер договора',           'turnout__contract__id',                                          default_style),
        ('Номер акта',               'id',                                                             default_style),
        ('Дата акта',                'date',                                                           date_style),
        ('Сумма акта',               'turnout__turnoutoperationtopay__operation__amount',              default_style),
        ('id',                       'turnout__worker__id',                                            default_style),
    ]

    wb = xlwt.Workbook(encoding='utf-8')
    ws = wb.add_sheet('Акты+выплаты')

    rows = Act.objects.all().values_list(*[key for caption, key, style in columns])

    caption_style = xlwt.XFStyle()
    caption_style.font.bold = True

    for col_num in range(len(columns)):
        caption, key, style = columns[col_num]
        ws.write(0, col_num, caption, caption_style)
        for i in range(len(rows)):
            ws.write(i + 1, col_num, rows[i][col_num], style)

    response = HttpResponse(content_type='application/ms-excel')
    response['Content-Disposition'] = 'attachment; filename="Deeds.xls"'
    wb.save(response)
    return response


# Выгрузить акты в ЗУП (excel)
@staff_account_required
def export_rkos_xls(request):
    default_style = xlwt.XFStyle()

    date_style = xlwt.XFStyle()
    date_style.num_format_str = 'DD.MM.YYYY'

    columns = [
        ('Фамилия',                  'worker__last_name',                                     default_style),
        ('Имя',                      'worker__name',                                          default_style),
        ('Отчество',                 'worker__patronymic',                                    default_style),
        ('Дата рождения',            'worker__birth_date',                                    date_style),
        ('Номер договора',           'act__turnout__contract__id',                            default_style),
        ('Номер акта',               'act__id',                                               default_style),
        ('Номер РКО',                'id',                                                    default_style),
        ('Дата РКО',                 'date',                                                  date_style),
        ('Сумма РКО',                'operation__amount',                                     default_style),
        ('Непроведенный',            'is_actual',                                             default_style),
        ('id рабочего',              'worker__id',                                            default_style),
    ]

    wb = xlwt.Workbook(encoding='utf-8')
    ws = wb.add_sheet('РКО')

    rows = Rko.objects.all().values_list(*[key for caption, key, style in columns])

    caption_style = xlwt.XFStyle()
    caption_style.font.bold = True

    for col_num in range(len(columns)):
        caption, key, style = columns[col_num]
        ws.write(0, col_num, caption, caption_style)
        for i in range(len(rows)):
            ws.write(i + 1, col_num, rows[i][col_num], style)

    response = HttpResponse(content_type='application/ms-excel')
    response['Content-Disposition'] = 'attachment; filename="RKOs.xls"'
    wb.save(response)
    return response


# Начисление зарплаты
@staff_account_required
@transaction.atomic
def make_payroll(request):
    parent = model_utils.get_account("26.")
    acc_exp = Account.objects.get(name='З/п', parent=parent)
    k_ops = finance.models.Operation.objects.filter(
        Q(debet=acc_exp) | Q(credit=acc_exp)
    ).filter(
        timestamp__gte=datetime.date.today() - datetime.timedelta(1)
    )

    if request.method == "POST":
        form_tp = OperationForm(request.POST or None)
        form = WorkerSearchForm(data=request.POST or None)
        if form_tp.is_valid():
            first_day, last_day = get_first_last_day(request, set_initial=False)
            if (first_day and not last_day) or (not first_day and last_day):
                raise Exception('Нужно заполнить обе границы интервала, либо не заполнять интервал вообще')
            operation_tp = form_tp.save(commit=False)
            operation_tp.save()
            if first_day and last_day:
                interval = finance.models.IntervalPayment.objects.create(
                    operation=operation_tp,
                    first_day=first_day,
                    last_day=last_day
                )

            return redirect('the_redhuman_is:make_payroll')
        if form.is_valid():
            worker = form.cleaned_data["worker"]
            operating_account = worker.worker_account
            worker_acc = operating_account.account
            w_ops = finance.models.Operation.objects.filter(
                Q(debet=worker_acc) | Q(credit=worker_acc)
            ).order_by("-timepoint")
            total_wd_ops = worker_acc.turnover_debet()
            total_wc_ops = worker_acc.turnover_credit()
            worker_saldo = - worker_acc.turnover_saldo()
            form = WorkerSearchForm()
            form_tp = OperationForm(
                initial={
                    'debet': acc_exp,
                    'credit': worker_acc,
                    'author': request.user
                }
            )
            return render(
                request,
                'the_redhuman_is/make_payroll.html',
                {
                    'form': form,
                    'payment_interval_form': DaysIntervalForm(),
                    'form_tp': form_tp,
                    'worker': worker,
                    'w_ops': w_ops,
                    'k_ops': k_ops,
                    'total_wd_ops': total_wd_ops,
                    'total_wc_ops': total_wc_ops,
                    'worker_saldo': worker_saldo
                }
            )
    else:
        form = WorkerSearchForm()

        initial = {
            'author': request.user
        }
        worker_param = request.GET.get('worker')
        if worker_param:
            worker = models.Worker.objects.get(pk=worker_param)
            worker_account = worker.worker_account.account
            initial['credit'] = worker_account
            initial['amount'] = worker_account.turnover_saldo()
            turnouts = worker.get_turnouts().filter(
                turnoutservice__isnull=False
            )
            initial['comment'] = 'Начисление для компенсации фактических выплат'
            if turnouts.exists():
                turnout = turnouts.last()
                customer_service = models.TurnoutService.objects.get(
                    turnout=turnout
                ).customer_service
                initial['debet'] = customer_service.account_20_general_work
        else:
            initial['debet'] = acc_exp
        form_tp = OperationForm(initial=initial)

        return render(
            request,
            'the_redhuman_is/make_payroll.html',
            {
                'form': form,
                'payment_interval_form': DaysIntervalForm(),
                'form_tp': form_tp,
                'k_ops': k_ops,
            }
        )


_COMMON_TAX_TYPES = [
    ('ndfl', 'НДФЛ'),
    ('fss_1', 'ФСС, ВН и М'),
    ('fss_2', 'ФСС, НС и ПЗ'),
    ('pfr', 'ОПС'),
    ('oms', 'ОМС'),
]


_SIMPLE_TAX_TYPES = _COMMON_TAX_TYPES + [
    ('usn', 'УСН'),
    ('psn', 'ПСН'),
    ('oms_ip', 'ФОМС за ИП'),
    ('pfr_ip_fix', 'ОПС за ИП фиксированные взносы'),
    ('pfr_ip_1', 'ОПС за ИП 1%'),
]


_GENERAL_TAX_TYPES = _COMMON_TAX_TYPES + [
    ('revenue', 'Налог на прибыль'),
    ('vat', 'НДС'),
]


# Начисление расходов
def expense_page(request):
    material_types = models.MaterialType.objects.all().order_by('name')
    admin_types = AdministrationCostType.objects.all().order_by('name')
    industrial_types = IndustrialCostType.objects.all().order_by('name')

    account50_children = model_utils.get_root_account('50').descendants()

    root_51 = model_utils.get_root_account('51')

    if is_app_flavor_master():
        gt_51 = model_utils.get_account('ГЕТ', root_51)
        sae_51 = model_utils.get_account('ИП С', root_51)

        gt_51_children = gt_51.descendants()
        sae_51_children = [a for a in sae_51.descendants() if a.pk not in [11630, 11473]]

        for account in gt_51_children + sae_51_children:
            account.name = f'{account.parent.name}/{account.name}'

        account51_extra_children = (
            [model_utils.get_account('КЛАСС', root_51)] +
            gt_51_children +
            sae_51_children
        )

        extra_pks = {a.pk for a in account51_extra_children}

    else:
        account51_extra_children = ()
        extra_pks = {}

    account51_children = [a for a in root_51.descendants() if a.pk not in extra_pks]

    account71_children = finance.models.Account.objects.filter(
        accountableperson__isnull=False
    )
    timepoint = datetime.datetime.now().strftime('%d.%m.%Y %h')
    worker_form = WorkerSearchForm()
    worker_form.set_autocomplete_url('the_redhuman_is:all-worker-autocomplete')

    customer_form = CustomerSelectionForm()
    _rename_field(customer_form.fields, 'customer', 'legal_entity_customer')

    expense_form = ExpenseSelectionForm()
    expense_form.fields['expense'].widget.forward=['expense_filter']

    return render(
        request,
        'the_redhuman_is/make_expense.html',
        {
            'form': MakeExpenseForm(),
            'payment_interval_form': DaysIntervalForm(),
            'expense_form': expense_form,
            'legal_entity_form': LegalEntitySelectionForm(),
            'legal_entity_customer': customer_form,
            'worker_form': worker_form,
            'admin_types': admin_types,
            'material_types': material_types,
            'simple_tax_types': _SIMPLE_TAX_TYPES,
            'general_tax_types': _GENERAL_TAX_TYPES,
            'industrial_types': industrial_types,
            'account50_children': account50_children,
            'account51_general_children': account51_children,
            'account51_extra_children': account51_extra_children,
            'account71_children': account71_children,
            'timepoint': timepoint,
        }
    )


def uses_simple_tax_system(request, pk):
    legal_entity = LegalEntity.objects.get(pk=pk)
    return JsonResponse({ 'simple_tax_system': legal_entity.uses_simple_tax_system() })


def _taxes_accounts(legal_entity_pk, tax_type, customer_pk):
    legal_entity = LegalEntity.objects.get(pk=legal_entity_pk)
    tax_types = _SIMPLE_TAX_TYPES if legal_entity.uses_simple_tax_system() else _GENERAL_TAX_TYPES
    if tax_type not in [k for k, v in tax_types]:
        raise Exception('Тип налога {} не соответствует юрлицу'.format(tax_type))

    root_77 = model_utils.get_root_account('77')

    if tax_type == 'ndfl':
        return (
            root_77,
            legal_entity.legal_entity_common_accounts.account_68_01,
        )
    elif tax_type == 'fss_1':
        return (
            root_77,
            legal_entity.legal_entity_common_accounts.account_69_1_1,
        )
    elif tax_type == 'fss_2':
        return (
            root_77,
            legal_entity.legal_entity_common_accounts.account_69_1_2,
        )
    elif tax_type == 'pfr':
        return (
            root_77,
            legal_entity.legal_entity_common_accounts.account_69_2,
        )
    elif tax_type == 'oms':
        return (
            root_77,
            legal_entity.legal_entity_common_accounts.account_69_3,
        )
    elif tax_type == 'usn':
        return (
            root_77,
            legal_entity.legal_entity_simple_tax_system_accounts.account_68_12,
        )
    elif tax_type == 'psn':
        return (
            root_77,
            legal_entity.legal_entity_simple_tax_system_accounts.account_68_14,
        )
    elif tax_type == 'oms_ip':
        return (
            root_77,
            legal_entity.legal_entity_simple_tax_system_accounts.account_69_06_3,
        )
    elif tax_type == 'pfr_ip_fix':
        return (
            root_77,
            legal_entity.legal_entity_simple_tax_system_accounts.account_69_06_5_1,
        )
    elif tax_type == 'pfr_ip_1':
        return (
            root_77,
            legal_entity.legal_entity_simple_tax_system_accounts.account_69_06_5_2,
        )
    elif tax_type == 'revenue':
        return (
            root_77,
            legal_entity.legal_entity_general_tax_system_accounts.account_68_04_2,
        )
    elif tax_type == 'vat':
        customer = models.Customer.objects.get(pk=customer_pk)
        return (
            customer.customer_accounts.account_90_3_root,
            legal_entity.legal_entity_general_tax_system_accounts.account_68_02,
        )
    else:
        raise Exception('Неизвестный тип налога <{}>.'.format(tax_type))


# Todo: fix broken idempotence (make it be post)
@transaction.atomic
def make_expense(request):
    cost_group = request.GET.get('cost_group')
    credit_param = request.GET.get('credit')

    paysheet = None
    expense = None
    person = None
    amount = None
    comment = None
    credit = None
    if credit_param:
        credit = finance.models.Account.objects.get(pk=credit_param)

    create_closed_operation = False

    if cost_group in ['material', 'industrial']:
        cost_type_id = request.GET.get('cost_type')
        customer_id = request.GET.get('customer')
        customer = Customer.objects.get(pk=customer_id)
        if cost_group == 'industrial':
            cost_type = IndustrialCostType.objects.filter(pk=cost_type_id).first()
            if cost_type is None:
                raise AttributeError('Нет статьи расходов')
            customer_accounts = models.get_or_create_customer_industrial_accounts(
                customer=customer,
                cost_type=cost_type
            )
            debet = customer_accounts.account_20
        else:
            material = models.MaterialType.objects.get(pk=cost_type_id)
            customer_10_subaccount = models.get_or_create_customer_10_subaccount(
                customer,
                material
            )
            debet = customer_10_subaccount.account_10
    elif cost_group == 'expenses':
        expense_id = request.GET.get('expense')
        expense = models.Expense.objects.get(pk=expense_id)
        assigned_person = models.get_accountable_person(expense)
        if assigned_person:
            credit = assigned_person.account_71
        debet = expense.provider.account_60
        amount = expense.amount
        comment = 'Оплата расхода №{} "{}"'.format(expense.id, expense.comment)
    elif cost_group == 'office':
        cost_type_id = request.GET.get('cost_type')
        debet = AdministrationCostType.objects.get(pk=cost_type_id).account_26
    elif cost_group in ['accountable_person', 'accountable_change']:
        create_closed_operation = True

        person_id = request.GET.get('accperson')
        person = AccountablePerson.objects.get(pk=person_id)
        if cost_group == 'accountable_person':
            debet = person.account_71
        else:
            debet = credit
            credit = person.account_71

        expense_id = request.GET.get('expense')
        if expense_id:
            expense = models.Expense.objects.get(pk=expense_id)
            amount = expense.amount
            comment = 'Выдача подотчетных средств. Расход №{}.'.format(expense.id)
        else:
            paysheet_prefix = 'paysheet_'
            prepayment_prefix = 'prepayment_'
            paysheet_id = request.GET.get('paysheet')
            if paysheet_id:
                if paysheet_id[:len(paysheet_prefix)] == paysheet_prefix:
                    pk = paysheet_id[len(paysheet_prefix):]
                    paysheet = models.Paysheet_v2.objects.get(pk=pk)
                elif paysheet_id[:len(prepayment_prefix)] == prepayment_prefix:
                    pk = paysheet_id[len(prepayment_prefix):]
                    paysheet = models.Prepayment.objects.get(pk=pk)
                else:
                    raise AttributeError('Unknown paysheet type.')
                amount = paysheet.total_amount
                comment = 'Выдача подотчетных средств. {}'.format(paysheet)

    elif cost_group == 'deposit':
        worker = models.Worker.objects.get(
            pk=request.GET['worker']
        )
        debet = worker.worker_account.account
        credit = worker.deposit.account
    elif cost_group == 'taxes':
        debet, credit = _taxes_accounts(
            request.GET['legal_entity'],
            request.GET['tax_type'],
            request.GET.get('customer')
        )
        comment = ''
    else:
        raise AttributeError('Неправильная группа расходов')

    execute_operation = request.GET.get('execute_operation')
    if execute_operation:
        time_str = request.GET.get('timepoint')
        if time_str is None:
            timepoint = datetime.datetime.now()
        else:
            timepoint = datetime.datetime.strptime(time_str, '%d.%m.%Y %H:%M')
        amount = decimal.Decimal(request.GET.get('amount'))
        if amount <= 0:
            raise AttributeError('Сумма должна быть положительной')
        comment = request.GET.get('comment')

        operation = finance.models.Operation.objects.create(
            timepoint=timepoint,
            author=request.user,
            comment=comment,
            debet=debet,
            credit=credit,
            amount=amount,
            is_closed=create_closed_operation
        )

        if expense or cost_group in ['industrial', 'office', 'taxes']:
            if expense:
                first_day = expense.first_day
                last_day = expense.last_day
            else:
                first_day, last_day = get_first_last_day(request, set_initial=False)
            if last_day < first_day:
                raise AttributeError('Начало периода должно быть не позднее конца.')
            interval = finance.models.IntervalPayment.objects.create(
                operation=operation,
                first_day=first_day,
                last_day=last_day
            )

        if paysheet:
            # Ведомость выбирается по подотчетному лицу, так что
            # подотчетное лицо для нее должно существовать (гонки игнорируем)
            models.AccountableDocumentOperation.objects.create(
                document=models.DocumentWithAccountablePerson.objects.get(
                    content_type=ContentType.objects.get_for_model(
                        type(paysheet)
                    ),
                    object_id=paysheet.id
                ),
                operation=operation
            )

        if expense:
            if person:
                document = models.set_accountable_person(expense, person)
                models.AccountableDocumentOperation.objects.create(
                    document=document,
                    operation=operation
                )
            else:
                models.ExpensePaymentOperation.objects.create(
                    expense=expense,
                    operation=operation
                )

        message = 'Проведена операция с дебетом "{}"'
        'и кредитом "{}" в размере {}, комментарий - "{}"'.format(
            debet,
            credit,
            amount,
            comment
        )

        result = {
            'success': True,
            'message': message
        }
    else:
        result = {
            'debet': str(debet),
            'credit': str(credit) if credit else '',
        }
        if amount is not None:
            result['amount'] = amount
        if comment:
            result['comment'] = comment

    return JsonResponse(result)


# Все операции пользователя
def get_user_operations(request):
    today = datetime.datetime.now().date()
    yesterday = today - datetime.timedelta(days=1)
    operations = finance.models.Operation.objects.filter(
        author=request.user.pk,
        timestamp__date__range=(yesterday, today)
    ).order_by(
        '-timestamp'
    )
    rows = []
    for operation in operations:
        rows.append(
            [
                str(operation.pk),
                str(operation.debet),
                str(operation.credit),
                operation.amount,
                operation.timepoint.strftime('%d.%m.%Y %H:%M'),
                operation.comment
            ]
        )
    return JsonResponse(
        {'operations': rows}
    )

# Редактирование операции (todo: make it to be POST)
@transaction.atomic
def user_operation_edit(request):
    operation = finance.models.Operation.objects.get(pk=request.GET["pk"])
    if not (operation.author == request.user or request.user.is_superuser):
        raise Exception("Ндостаточно прав доступа")

    message = ""
    if request.GET.get('delete'):
        message = "Удалена операция №"+str(operation.pk)
        if hasattr(operation, 'expense_payment'):
            operation.expense_payment.delete()
        operation.delete()
    else:
        first_day, last_day = get_first_last_day(request, set_initial=False)
        if (first_day and not last_day) or (not first_day and last_day):
            raise Exception('Нужно заполнить обе границы интервала, либо не заполнять интервал вообще')
        interval = finance.models.IntervalPayment.objects.filter(operation=operation)
        if interval.exists():
            interval = interval.get()
            if first_day:
                interval.first_day = first_day
                interval.last_day = last_day
                interval.save()
            else:
                interval.delete()
        else:
            if first_day:
                interval = finance.models.IntervalPayment.objects.create(
                    operation=operation,
                    first_day=first_day,
                    last_day=last_day
                )

        amount = request.GET.get('amount')
        if amount:
            amount = float(amount)
            if amount <= 0:
                raise AttributeError("Сумма меньше либо равно нулю")
            if operation.amount != amount:
                message += "Сумма изменена с " + str(operation.amount) + " на " + str(amount)+ "; "
                operation.amount = amount
        comment = request.GET.get('comment')
        if comment and operation.comment != comment:
            message += "Комментарий изменен с " + str(operation.comment) + " на "+ str(comment)
            operation.comment = comment
        timepoint_str = request.GET.get("timepoint")
        if timepoint_str:
            timepoint = datetime.datetime.strptime(timepoint_str, '%d.%m.%Y %H:%M')
            if operation.timepoint != timepoint:
                message += "Время изменено с " + str(operation.timepoint) + " на " + str(timepoint)
                operation.timepoint = timepoint
        operation.save()

    return JsonResponse({'message': message})


def get_period_closing_requirements(start_date, end_date):
    timesheets = TimeSheet.objects.order_by().filter(
        sheet_date__gte=start_date,
        sheet_date__lt=end_date,
    )

    unclosed_recon_timesheets = timesheets.annotate(
        unclosed_recon=Subquery(
            Reconciliation.objects.filter(
                Q(location__isnull=True) | Q(location=OuterRef('cust_location')),
                customer=OuterRef('customer'),
                first_day__lte=OuterRef('sheet_date'),
                last_day__gte=OuterRef('sheet_date'),
                is_closed=False
            ).values('pk')
        )
    ).filter(
        unclosed_recon__isnull=False
    ).values(
        'customer',
        'cust_location'
    ).annotate(
        unclosed_recons=ArrayAgg('unclosed_recon', distinct=True)
    )

    unclosed_recon_timesheets_data = {
        (timesheet['customer'], timesheet['cust_location']): timesheet['unclosed_recons']
        for timesheet in unclosed_recon_timesheets
    }

    no_recon_timesheets = timesheets.annotate(
        has_recon=Exists(
            Reconciliation.objects.filter(
                Q(location__isnull=True) | Q(location=OuterRef('cust_location')),
                customer=OuterRef('customer'),
                first_day__lte=OuterRef('sheet_date'),
                last_day__gte=OuterRef('sheet_date'),
            )
        )
    ).filter(
        has_recon=False
    ).values(
        'customer',
        'cust_location'
    ).annotate(
        min_date=Min('sheet_date')
    ).values(
        'customer',
        'cust_location',
        'min_date'
    )

    no_recon_timesheets_data = {
        (timesheet['customer'], timesheet['cust_location']): timesheet['min_date']
        for timesheet in no_recon_timesheets
    }

    customer_location_pairs = list(
        unclosed_recon_timesheets_data.keys() | no_recon_timesheets_data.keys()
    )
    customer_names = {
        customer.pk: customer.cust_name
        for customer in Customer.objects.filter(
            pk__in={pair[0] for pair in customer_location_pairs}
        ).values_list('pk', 'cust_name', named=True)
    }
    location_names = {
        location.pk: location.location_name
        for location in CustomerLocation.objects.filter(
            pk__in={pair[1] for pair in customer_location_pairs}
        ).values_list('pk', 'location_name', named=True)
    }
    data = [
        {
            'customer': {'id': pair[0], 'name': customer_names[pair[0]]},
            'location': {'id': pair[1], 'name': location_names[pair[1]]},
            'unclosed_ts': unclosed_recon_timesheets_data.get(pair),
            'no_recon_ts': no_recon_timesheets_data.get(pair),
        }
        for pair in customer_location_pairs
    ]
    data.sort(key=lambda x: (x['customer']['name'], x['location']['name']))
    return data


# Закрытие месяца
def period_close_document(request):
    messages = []
    if not finance.models.Account.objects.filter(name__startswith='99.').exists():
        messages.append({"message": "Нет счета 99", "action": "no-99", "type": "danger"})

    none_account = False
    for customer_account in CustomerOperatingAccounts.objects.all():
        if customer_account.account_90_2_root is None or customer_account.account_90_9_root is None:
            none_account = True
            continue
        if len(customer_account.account_90_2_root.descendants()) > 0 \
                or len(customer_account.account_90_9_root.descendants()) > 0:
            messages.append({"message": "У счетов клиентов в 90.2 или 90.2 счетах есть унаследованные счета. Удалить?",
                             "action": "root-descendant-acc", "type": "danger"})
            break

    if none_account:
        messages.append({"message": "У некоторых клиентов нет счетов в 90", "action": "no-90-customer-root", "type": "danger"})
    messages.reverse()
    if request.method == 'POST':
        try:
            day_begin = datetime.datetime.strptime(request.POST['begin'], "%d.%m.%Y").date()
            day_end = datetime.datetime.strptime(request.POST['end'], "%d.%m.%Y").date()
            create_period_closure_document(day_begin, day_end, request.user)
        except Exception as exc:
            messages.append({"message": exc.args[0], "action": None, "type": "danger"})

    documents = PeriodCloseDocument.objects.all().order_by('-create_timepoint')

    last_document = documents.first()
    if last_document is not None:
        start_date = last_document.end + datetime.timedelta(days=1)
        end_date = datetime.date(start_date.year + start_date.month // 12, start_date.month % 12 + 1, 1)
        closing_requirements = get_period_closing_requirements(start_date, end_date)
    else:
        start_date = end_date = None
        closing_requirements = []

    return render(
        request,
        'the_redhuman_is/period_close_document.html',
        {
            'messages': messages,
            'documents': documents,
            'next_period_start': start_date,
            'next_period_end': end_date - datetime.timedelta(days=1) if end_date is not None else None,
            'closing_requirements': closing_requirements,
        }
    )


@require_POST
def ajax_close_document_actions(request):
    doc_id = request.POST.get('document_id')
    action = request.POST.get('action')
    if doc_id and action == 'delete':
        if not request.user.is_superuser:
            raise Exception('Недостаточно прав')
        document = PeriodCloseDocument.objects.get(pk=doc_id)
        document.delete()
        return JsonResponse({'success': True, 'messages': ['Удален документ №'+str(document.pk)]})
    elif action == 'no-99':
        if finance.models.Account.objects.filter(name__startswith='99.', parent=None).exists():
            return JsonResponse({'success': True, 'messages': ['99й корневой счет уже существует']})
        else:
            finance.models.Account.objects.create(name='99. Прибыли и убытки', parent=None)
            return JsonResponse({'success': True, 'messages': ["Создан корневой счет '99. Прибыли и убытки'"]})
    elif action == 'no-90-customer-root':

        for customer_account in CustomerOperatingAccounts.objects.all():
            customer_account.save()

        return JsonResponse({'success': True, 'messages': ['Необходимые счета созданы']})
    else:
        return JsonResponse({}, status=400)


def ajax_get_close_documents(request):
    doc_id = request.GET.get('document_id')
    if doc_id:
        sheet_ops = SheetPeriodClose.objects.filter(close_document=doc_id)
        document = []
        for sheet_op in sheet_ops:
            row = dict()
            row['debet'] = str(sheet_op.close_operation.debet)
            row['credit'] = str(sheet_op.close_operation.credit)
            row['close_operation'] = sheet_op.close_operation.amount
            document.append(row)
        return JsonResponse({'document': document})
    else:
        documents = PeriodCloseDocument.objects.all().order_by('-create_timepoint')
        return JsonResponse({'documents': documents})
