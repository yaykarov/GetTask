# -*- coding: utf-8 -*-
from django.contrib.auth.models import User

from django.contrib.contenttypes.models import ContentType

from django.db import (
    models,
    transaction,
)

from django.db.models import (
    Case,
    CharField,
    DecimalField,
    F,
    OuterRef,
    Q,
    Subquery,
    Value,
    When,
)
from django.db.models.functions import (
    Coalesce,
    Concat,
)

import finance

from the_redhuman_is.models.photo import add_photo

from the_redhuman_is.models.expenses import (
    Expense,
    ExpenseDeductionOperation,
    Provider,
    ProviderFine,
)
from the_redhuman_is.models.models import (
    Customer,
    CustomerFineDeduction,
    CustomerOperatingAccounts,
    IndustrialCostType,
    MaterialType,
    WorkerBonus,
    WorkerDeduction,
    WorkerOperatingAccount,
    WorkerTurnout,
    get_or_create_customer_10_subaccount,
    get_or_create_customer_industrial_accounts,
)
from the_redhuman_is.models.photo import (
    Photo,
    get_photos,
)
from the_redhuman_is.models.turnout_operations import (
    CustomerFine,
    TurnoutBonus,
    TurnoutDeduction,
)
from the_redhuman_is.models.paysheet_v2 import Paysheet_v2EntryOperation
from the_redhuman_is.models.worker import Worker


class OperationsPack(models.Model):
    timestamp = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Время создания'
    )
    author = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        verbose_name='Автор'
    )
    comment = models.TextField('Комментарий')

    def __str__(self):
        return '{}/{}'.format(
            self.author,
            self.comment or '-'
        )


class OperationsPackItem(models.Model):
    pack = models.ForeignKey(
        OperationsPack,
        on_delete=models.CASCADE,
        verbose_name='Группа операций',
        related_name='items'
    )
    operation = models.ForeignKey(
        finance.models.Operation,
        on_delete=models.PROTECT,
        verbose_name='Операция',
        related_name='pack_items'
    )

    def __str__(self):
        return '{}/{}'.format(
            self.pack,
            self.operation
        )


@transaction.atomic
def rollback_operations_pack(pack, remove_from_paysheet=False):
    operations = finance.models.Operation.objects.filter(
        pack_items__pack=pack
    )

    CustomerFineDeduction.objects.filter(
        fine__in=operations,
        deduction__in=operations
    ).delete()

    marker_models = [
        CustomerFine,
        TurnoutBonus,
        TurnoutDeduction,
        WorkerBonus,
        WorkerDeduction,
    ]

    if remove_from_paysheet:
        marker_models.append(Paysheet_v2EntryOperation)

    for model in marker_models:
        model.objects.filter(
            operation__in=operations
        ).delete()

    if hasattr(pack, 'deductions_file'):
        deductions_file = pack.deductions_file
        deductions_file.operations_pack = None
        deductions_file.save()

    ops = list(operations)

    pack.delete()

    for op in ops:
        op.delete()


def _deductions_file_upload_location(instance, filename):
    return 'vkusvill/performance/{}/{}'.format(
        instance.id,
        filename
    )


class DeductionsFile(models.Model):
    timestamp = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Время создания'
    )
    author = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        verbose_name='Автор'
    )
    data_file = models.FileField(upload_to=_deductions_file_upload_location)
    customer = models.ForeignKey(
        Customer,
        on_delete=models.PROTECT,
        verbose_name='Клиент',
        related_name='deductions_files'

    )
    operations_pack = models.OneToOneField(
        OperationsPack,
        on_delete=models.PROTECT,
        verbose_name='Группа операций',
        related_name='deductions_file',
        null=True,
        blank=True
    )

    def on_import_complete(self, pack):
        self.operations_pack = pack
        self.save()


@transaction.atomic
def create_deductions_file(author, data_file, customer_pk):
    deductions_file = DeductionsFile.objects.create(
        author=author,
        customer=Customer.objects.get(pk=customer_pk),
    )
    deductions_file.data_file = data_file
    deductions_file.save()
    return deductions_file


@transaction.atomic
def create_fines(
            author,
            customer_pk,
            material_type_pk,
            fines,
            operations_pack_comment=None
        ):

    customer_account = CustomerOperatingAccounts.objects.get(
        customer__pk=customer_pk,
    )

    material_account = None
    if material_type_pk:
        raise Exception('Внесение штрафов/вычетов в материалы заблокировано!')
        material_account = get_or_create_customer_10_subaccount(
            customer=Customer.objects.get(pk=customer_pk),
            material_type=MaterialType.objects.get(pk=material_type_pk)
        )

    operations_pack = None
    if operations_pack_comment is not None:
        operations_pack = OperationsPack.objects.create(
            author=author,
            comment=operations_pack_comment
        )

    for data in fines:
        if 'fine' in data:
            if material_account:
                raise Exception('Unsupported fine while material_type is defined!')

            turnout = data['turnout']

            customer_fine_operation = finance.models.Operation.objects.create(
                timepoint=data['date'],
                author=author,
                comment='Штраф. {}'.format(data['comment']),
                debet=customer_account.account_76_fines,
                credit=customer_account.account_76_debts,
                amount=data['fine']
            )

            CustomerFine.objects.create(
                operation=customer_fine_operation,
                turnout=turnout,
            )

            if operations_pack:
                OperationsPackItem.objects.create(
                    pack=operations_pack,
                    operation=customer_fine_operation
                )

        if 'deduction' in data:
            worker_operating_account = data['worker'].worker_account.account
            if material_account:
                credit = material_account.account_10
            else:
                if 'fine' in data:
                    credit = customer_account.account_90_1_fine_based_deductions
                else:
                    credit = customer_account.account_90_1_disciplinary_deductions

            amount = max(0, min(-1 * worker_operating_account.turnover_saldo(), data['deduction']))

            deduction_operation = finance.models.Operation.objects.create(
                timepoint=data['date'],
                author=author,
                comment='Вычет. {}'.format(data['comment']),
                debet=worker_operating_account,
                credit=credit,
                amount=amount,
            )

            if 'turnout' in data:
                TurnoutDeduction.objects.create(
                    operation=deduction_operation,
                    turnout=data['turnout']
                )
            else:
                WorkerDeduction.objects.create(
                    operation=deduction_operation
                )

            if operations_pack:
                OperationsPackItem.objects.create(
                    pack=operations_pack,
                    operation=deduction_operation
                )

        if 'deduction' in data and 'fine' in data:
            CustomerFineDeduction.objects.create(
                fine=customer_fine_operation,
                deduction=deduction_operation
            )

    return operations_pack


def deduction_accounts(customer_pk=None, customers=None):
    if customer_pk:
        return finance.models.Account.objects.filter(
            Q(account_90_1_disciplinary_deduction_accounts__customer__pk=customer_pk) |
            Q(account_90_1_fine_based_deduction_accounts__customer__pk=customer_pk) |
            Q(account_90_1_industrial_accounts__customer__pk=customer_pk)
        )
    elif customers is not None:
        return finance.models.Account.objects.filter(
            Q(account_90_1_disciplinary_deduction_accounts__customer__in=customers) |
            Q(account_90_1_fine_based_deduction_accounts__customer__in=customers) |
            Q(account_90_1_industrial_accounts__customer__in=customers)
        )
    else:
        return finance.models.Account.objects.filter(
            Q(account_90_1_disciplinary_deduction_accounts__isnull=False) |
            Q(account_90_1_fine_based_deduction_accounts__isnull=False) |
            Q(account_90_1_industrial_accounts__isnull=False)
        )


@transaction.atomic
def _create_deduction(
            author,
            comment,
            customer_pk,
            fine_amount,
            fine_date,
            worker_pk,
            deduction_date_type,
            deduction_date,
            turnout_pk,
            deduction_amount_type,
            deduction_amount,
            deduction_type,
            expense_pk,
            industrial_cost_type_pk,
            is_fine_based=False,
        ):

    if deduction_date_type == 'turnout':
        turnout = WorkerTurnout.objects.get(
            pk=turnout_pk,
            worker__pk=worker_pk,
            timesheet__customer__pk=customer_pk
        )

        operation_timepoint = turnout.timesheet.sheet_date
    elif deduction_date_type == 'fine_date':
        operation_timepoint = fine_date
    elif deduction_date_type == 'date':
        operation_timepoint = deduction_date
    else:
        raise Exception('Unknown deduction_date_type value: {}'.format(deduction_date_type))

    if deduction_type == 'disciplinary':
        customer_account = CustomerOperatingAccounts.objects.get(
            customer__pk=customer_pk,
        )

        if is_fine_based:
            credit = customer_account.account_90_1_fine_based_deductions
        else:
            credit = customer_account.account_90_1_disciplinary_deductions

    elif deduction_type == 'industrial_cost':
        industrial_accounts = get_or_create_customer_industrial_accounts(
            Customer.objects.get(pk=customer_pk),
            IndustrialCostType.objects.get(pk=industrial_cost_type_pk)
        )

        credit = industrial_accounts.account_90_1

    elif deduction_type == 'material':
        expense = Expense.objects.get(pk=expense_pk)

        credit = expense.expense_debit
    else:
        raise Exception('Unknown deduction_type value: {}'.format(deduction_type))

    if deduction_amount_type == 'by_fine':
        amount = fine_amount
    elif deduction_amount_type == 'arbitrary':
        amount = deduction_amount
    else:
        raise Exception('Unknown deduction_amount_type value: {}'.format(deduction_amount_type))

    worker_operating_account = WorkerOperatingAccount.objects.get(
        worker__pk=worker_pk
    ).account

    operation = finance.models.Operation.objects.create(
        timepoint=operation_timepoint,
        author=author,
        comment='Вычет. {}'.format(comment),
        debet=worker_operating_account,
        credit=credit,
        amount=amount
    )

    if deduction_type == 'material':
        ExpenseDeductionOperation.objects.create(
            expense=expense,
            operation=operation
        )

    if deduction_date_type == 'turnout':
        deduction = TurnoutDeduction.objects.create(
            operation=operation,
            turnout=turnout
        )
    else:
        deduction = WorkerDeduction.objects.create(
            operation=operation
        )

    return deduction


@transaction.atomic
def _create_fine(
            author,
            comment,
            fine_amount,
            fine_date,
            customer_pk,
            fine_type,
            provider_pk,
            worker_pk,
            turnout_pk,
            images,
            deduction_operation
        ):

    customer_account = CustomerOperatingAccounts.objects.get(
        customer__pk=customer_pk,
    )

    if fine_type == 'customer':
        turnout = WorkerTurnout.objects.get(
            pk=turnout_pk,
            worker__pk=worker_pk,
            timesheet__customer__pk=customer_pk
        )

        operation_timepoint = turnout.timesheet.sheet_date

        credit = customer_account.account_76_debts

    elif fine_type == 'provider':
        operation_timepoint = fine_date

        provider = Provider.objects.get(pk=provider_pk)
        credit = provider.account_60_fines
    else:
        raise Exception('Unknown fine_type value: {}'.format(fine_type))

    operation = finance.models.Operation.objects.create(
        timepoint=operation_timepoint,
        author=author,
        comment='Штраф. {}'.format(comment),
        debet=customer_account.account_76_fines,
        credit=credit,
        amount=fine_amount
    )

    if fine_type == 'customer':
        target = CustomerFine.objects.create(
            operation=operation,
            turnout=turnout,
        )
    elif fine_type == 'provider':
        target = ProviderFine.objects.create(
            operation=operation,
            provider=provider
        )

    for image in images:
        add_photo(target, image)

    CustomerFineDeduction.objects.create(
        fine=operation,
        deduction=deduction_operation
    )


@transaction.atomic
def create_claim(
            author,
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
            images,
        ):

    if claim_type not in ['deduction', 'fine']:
        raise Exception('Unknown claim_type value: {}'.format(claim_type))

    if claim_type == 'fine':
        if deduction_date_type:
            raise Exception('deduction_date_type should not be set if claim_type is fine')
        if fine_type == 'customer':
            deduction_date_type = 'turnout'
        else:
            deduction_date_type = 'fine_date'

        if deduction_type:
            raise Exception('deduction_type should not be set if claim_type is fine')
        deduction_type = 'disciplinary'

    else:
        if deduction_amount_type:
            raise Exception('deduction_amount_type should not be sef if claim_type is not fine')
        deduction_amount_type = 'arbitrary'

    deduction = _create_deduction(
        author,
        comment,
        customer_pk,
        fine_amount,
        fine_date,
        worker_pk,
        deduction_date_type,
        deduction_date,
        turnout_pk,
        deduction_amount_type,
        deduction_amount,
        deduction_type,
        expense_pk,
        industrial_cost_type_pk,
        is_fine_based=(claim_type=='fine')
    )

    if claim_type == 'fine':
        _create_fine(
            author,
            comment,
            fine_amount,
            fine_date,
            customer_pk,
            fine_type,
            provider_pk,
            worker_pk,
            turnout_pk,
            images,
            deduction.operation
        )


def claims_list(first_day, last_day):
    deductions = finance.models.Operation.objects.filter(
        Q(workerdeduction__isnull=False) | Q(turnoutdeduction__isnull=False),
        timestamp__date__range=(first_day, last_day),
    ).annotate(
        claim_type=Case(
            When(
                deductions__isnull=False,
                then=Value('fine')
            ),
            default=Value('deduction'),
            output_field=CharField()
        ),
        first_photo=Coalesce(
            Subquery(
                Photo.objects.filter(
                     content_type=ContentType.objects.get_for_model(ProviderFine),
                     object_id=OuterRef('deductions__fine__providerfine')
                 ).values('pk')[:1]
            ),
            Subquery(
                Photo.objects.filter(
                     content_type=ContentType.objects.get_for_model(CustomerFine),
                     object_id=OuterRef('deductions__fine__customerfine')
                 ).values('pk')[:1]
            ),
        ),
        customer_name=Case(
            When(
                turnoutdeduction__isnull=False,
                then=F('turnoutdeduction__turnout__timesheet__customer__cust_name')
            ),
            When(
                credit__account_90_1_fine_based_deduction_accounts__isnull=False,
                then=F('credit__account_90_1_fine_based_deduction_accounts__customer__cust_name')
            ),
            When(
                credit__account_90_1_disciplinary_deduction_accounts__isnull=False,
                then=F('credit__account_90_1_disciplinary_deduction_accounts__customer__cust_name')
            ),
            When(
                credit__account_90_1_industrial_accounts__isnull=False,
                then=F('credit__account_90_1_industrial_accounts__customer__cust_name')
            ),
            When(
                credit__account_10_subaccounts__isnull=False,
                then=F('credit__account_10_subaccounts__customer__cust_name')
            ),
            output_field=CharField()
        ),
        claim_by=Case(
            When(
                deductions__fine__credit__account_76_debts_accounts__isnull=False,
                then=F('deductions__fine__credit__account_76_debts_accounts__customer__cust_name')
            ),
            When(
                deductions__fine__credit__account_60_provider_fines__isnull=False,
                then=F('deductions__fine__credit__account_60_provider_fines__name')
            ),
            default=Value('-'),
            output_field=CharField()
        ),
        fine_amount=Case(
            When(
                deductions__isnull=False,
                then=F('deductions__fine__amount')
            ),
            output_field=DecimalField()
        ),
        deduction_type=Case(
            When(
                credit__account_90_1_fine_based_deduction_accounts__isnull=False,
                then=Value('На основе штрафа')
            ),
            When(
                credit__account_90_1_disciplinary_deduction_accounts__isnull=False,
                then=Value('Дисциплинарный')
            ),
            When(
                credit__account_90_1_industrial_accounts__isnull=False,
                then=Value('За наши услуги')
            ),
            When(
                credit__account_10_subaccounts__isnull=False,
                then=Value('За материалы')
            ),
            default=Value('Неизвестный тип вычета О_о?'),
            output_field=CharField()
        ),
        fine_id=F('deductions__fine'),
        worker_id=F('debet__worker_account__worker'),
        worker_full_name=Subquery(
            Worker.objects.filter(
                pk=OuterRef('worker_id')
            ).annotate(
                full_name=Concat(
                    'last_name',
                    Value(' '),
                    'name',
                    Value(' '),
                    'patronymic',
                    output_field=CharField()
                )
            ).values('full_name'),
            output_field=CharField()
        )
    ).order_by(
        '-timestamp'
    )

    return deductions


def claims_photos(pk):
    # pk - deduction operation pk
    # photos could be attached to CustomerFine object or to ProviderFine object

    customer_fine = CustomerFine.objects.filter(
        operation__fines__deduction__pk=pk
    )
    if customer_fine.exists():
        return get_photos(customer_fine.get())

    provider_fine = ProviderFine.objects.filter(
        operation__fines__deduction__pk=pk
    )
    # provider_fine should exists if customer_fine does not exist
    return get_photos(provider_fine.get())
