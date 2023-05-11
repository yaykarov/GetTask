from datetime import (
    datetime,
    time,
    timedelta,
)

from django.core.exceptions import ValidationError

from django.db import transaction

from django.db.models import (
    Exists,
    OuterRef,
    Q,
    Subquery,
)

from django.db.models.signals import pre_delete


from the_redhuman_is.models import (
    AdministrationCostType,
    CustomerOperatingAccounts,
    PeriodCloseDocument,
    Reconciliation,
    SheetPeriodClose,
    TimeSheet,
    LegalEntity,
    Bank,
)

from finance.models import (
    Account,
    Operation,
)

from the_redhuman_is.services.finance.common import (
    close_operations,
    get_account_credit_turnover,
    get_account_debit_turnover,
    get_account_saldo,
    lock_root_account_99,
)

from utils.date_time import as_default_timezone


def is_period_closed(timepoint):
    return PeriodCloseDocument.objects.filter(
        created=True,
        begin__lte=timepoint,
        end__gte=timepoint
    ).exists()


def can_close_period(first_day, last_day):
    timesheets = TimeSheet.objects.order_by().filter(
        sheet_date__gte=first_day,
        sheet_date__lt=last_day,
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
    )
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
    )
    return not unclosed_recon_timesheets.exists() and not no_recon_timesheets.exists()


@transaction.atomic
def create_period_closure_document(first_day, last_day, author):
    account_99 = lock_root_account_99()

    if PeriodCloseDocument.objects.latest('end').end + timedelta(days=1) != first_day:
        raise ValidationError('Закрываемый период не следует сразу за последним закрытым')
    if (is_period_closed(first_day) or is_period_closed(last_day)):
        raise ValidationError('Период уже закрыт')
    if not can_close_period(first_day, last_day):
        raise ValidationError('Невозможно закрыть период')

    document = PeriodCloseDocument.objects.create(
        begin=first_day,
        end=last_day,
        author=author
    )
    FORMAT = '%d.%m.%y'
    period_comment = 'Закрытие периода #{} c {} по {}'.format(
        document,
        datetime.strftime(first_day, FORMAT),
        datetime.strftime(last_day, FORMAT)
    )

    def _create_final_operation(debit, credit, amount):
        operation = Operation.objects.create(
            timepoint=as_default_timezone(datetime.combine(last_day, time()) + timedelta(days=1) - timedelta.resolution),
            author=author,
            comment=period_comment,
            debet=debit,
            credit=credit,
            amount=amount,
            is_closed=True,
        )
        SheetPeriodClose.objects.create(
            close_document=document,
            close_operation=operation
        )

    def _close_saldo(account, target_debit):
        saldo = get_account_saldo(account, first_day, last_day)
        if saldo != 0:
            if saldo > 0:
                debit = target_debit
                credit = account
            else:
                debit = account
                credit = target_debit
            _create_final_operation(debit, credit, abs(saldo))

    def _close_debit_turnover(account, target_debit):
        turnover = get_account_debit_turnover(account, first_day, last_day)
        if turnover != 0:
            _create_final_operation(target_debit, account, turnover)

    customer_accounts = CustomerOperatingAccounts.objects.all(
    ).prefetch_related(
        'customer__industrial_accounts'
    )

    # расходы клиентов
    for customer_account in customer_accounts:
        for account_20 in customer_account.account_20_root.descendants():
            if account_20.children.exists():
                continue
            _close_saldo(
                account_20,
                customer_account.account_90_2_root
            )

        _close_saldo(
            customer_account.account_90_2_root,
            customer_account.account_90_9_root
        )

        for account_10 in customer_account.account_10_root.descendants():
            if account_10.children.exists():
                continue
            _close_saldo(
                account_10,
                customer_account.account_90_9_root
            )

        for account in customer_account.account_90_1_root.descendants():
            turnover = get_account_credit_turnover(account, first_day, last_day)
            if turnover != 0:
                _create_final_operation(
                    account,
                    customer_account.account_90_9_root,
                    turnover
                )

        # в т.ч. НДС
        _close_debit_turnover(
            customer_account.account_90_3_root,
            customer_account.account_90_9_root
        )

        _close_saldo(
            customer_account.account_90_9_root,
            account_99
        )

    # Общехозяйственные расходы
    for cost_type in AdministrationCostType.objects.all():
        _close_debit_turnover(
            cost_type.account_26,
            cost_type.account_90_2
        )

        _close_debit_turnover(
            cost_type.account_90_2,
            cost_type.account_90_9
        )

        _close_saldo(
            cost_type.account_90_9,
            account_99
        )

    # В т.ч. расходы на юрлиц
    for legal_entity in LegalEntity.objects.all():
        le_account_90_2 = legal_entity.legal_entity_common_accounts.account_90_2
        for account in legal_entity.expense_accounts():
            _close_debit_turnover(
                account,
                le_account_90_2
            )

        _close_debit_turnover(
            le_account_90_2,
            legal_entity.legal_entity_common_accounts.account_90_9
        )

        _close_saldo(
            legal_entity.legal_entity_common_accounts.account_90_9,
            account_99
        )

    # Банки
    for bank in Bank.objects.all():
        for account in bank.account_90_2.descendants():
            _close_saldo(account, account_99)

    PeriodCloseDocument.objects.filter(
        pk=document.pk
    ).update(
        created=True
    )

    close_operations(last_day)

    return document


@transaction.atomic
def pre_delete_period_closure_document(sender, instance, *args, **kwargs):
    sheets = SheetPeriodClose.objects.filter(close_document=instance)
    for sheet in sheets:
        operation = sheet.close_operation
        sheet.delete()
        operation.delete()

    # Спорно : (
    Operation.objects.filter(
        timepoint__date__range=(instance.begin, instance.end),
        is_closed=True
    ).update(
        is_closed=False
    )


pre_delete.connect(pre_delete_period_closure_document, sender=PeriodCloseDocument)
