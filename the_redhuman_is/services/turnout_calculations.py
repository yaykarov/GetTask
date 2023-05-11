# -*- coding: utf-8 -*-

import decimal

from django.core.exceptions import ObjectDoesNotExist

from django.db import transaction

from django.db.models import Q

from finance.models import (
    Operation,
    update_if_changed,
)

from finance.model_utils import get_root_account

from the_redhuman_is.models.delivery import DeliveryRequest
from the_redhuman_is.models.hostel import update_hostel_bonus

from the_redhuman_is.models.models import (
    CustomerOperatingAccounts,
    CustomerService,
    TimeSheet,
    WorkerTurnout,
)
from the_redhuman_is.models.paysheet_v2 import Paysheet_v2EntryOperation

from the_redhuman_is.models.turnout_calculators import (
    _amount_calculator,
    PositionCalculator,
)
from the_redhuman_is.models.turnout_operations import (
    TurnoutAdjustingOperation,
    TurnoutCustomerOperation,
    TurnoutDeduction,
    TurnoutOperationToPay,
    TurnoutTaxOperation,
)


_PLANNED_TAX_FACTOR = decimal.Decimal(0.09)


def _amount_change_message(current_amount, new_amount):
    assert current_amount != new_amount

    if new_amount > current_amount:
        action = 'увеличилась'
    else:
        action = 'уменьшилась'

    return 'сумма {} с {:.2f} до {:.2f} на {:.2f}'.format(
        action,
        current_amount,
        new_amount,
        abs(current_amount - new_amount)
    )


#
# Класс для расчета операций, которые генерирует факт выхода работника
# Клиенту - стоимость смены
# Работнику - стоимость услуги + компенсация проживания + надбавка за должность
# Плюс планируемый налог/корректирующие вычеты
#
# Если у выхода нет связанного CustomerService - считаем, что оплачивать нечего и удаляем
# все операции, если возможно. Иначе - оставляем оплаченное начисление работнику и создаем
# (корректируем) вычеты
#
# Предполагается, что за блокировку/атомарность отвечает внешний код.
#
class TurnoutCalculation:
    def __init__(self, turnout, author, deduction_worker=None):
        self.turnout = turnout
        self.author = author
        self.deduction_worker = deduction_worker

    def setup(self):
        self.fetch_calculator_and_stuff()
        self.fetch_current_operations()
        self.setup_comment()
        self.setup_operations()

    def fetch_calculator_and_stuff(self):
        if self.deduction_worker is not None:
            self.deduction_worker_account = self.deduction_worker.worker_account

        self.worker = self.turnout.worker
        self.worker_account = self.worker.worker_account

        self.timesheet = TimeSheet.objects.get(worker_turnouts=self.turnout)
        self.customer = self.timesheet.customer
        self.customer_account = CustomerOperatingAccounts.objects.get(
            customer_id=self.customer
        )

        self.is_turnout_in_paysheet = Paysheet_v2EntryOperation.objects.filter(
            operation__turnoutoperationtopay__turnout=self.turnout
        ).exists()

        try:
            self.customer_service = CustomerService.objects.get(
                turnoutservice__turnout=self.turnout
            )
        except ObjectDoesNotExist:
            self.customer_service = None

        if self.customer_service is None:
            self.calculator = None
        else:
            self.calculator = _amount_calculator(
                self.timesheet.sheet_date,
                self.customer_service
            )

    def _fetch_turnout_operation(self, name, Model):
        try:
            value = Model.objects.get(turnout=self.turnout)
        except ObjectDoesNotExist:
            value = None
        setattr(self, name, value)

    def fetch_current_operations(self):
        self._fetch_turnout_operation('current_customer_operation', TurnoutCustomerOperation)
        self._fetch_turnout_operation('current_worker_operation', TurnoutOperationToPay)
        self._fetch_turnout_operation('current_tax_operation', TurnoutTaxOperation)
        self._fetch_turnout_operation('current_adjusting_operation', TurnoutAdjustingOperation)
        self._fetch_turnout_operation('current_deduction_operation', TurnoutDeduction)

        if self.current_deduction_operation is not None and self.deduction_worker is not None:
            operation = self.current_deduction_operation.operation
            assert operation.debet == self.deduction_worker_account.account

    def _delete_current_operation(self, operation_name):
        current_operation_name = f'current_{operation_name}'
        current_operation = getattr(self, current_operation_name)
        if current_operation is not None:
            operation = current_operation.operation
            current_operation.delete()
            operation.delete()
            setattr(self, current_operation_name, None)

    def delete_current_operations(self):
        OPERATION_NAMES = (
            'customer_operation',
            'worker_operation',
            'tax_operation',
            'adjusting_operation',
            'deduction_operation'
        )

        for operation_name in OPERATION_NAMES:
            self._delete_current_operation(operation_name)

    def setup_comment(self):
        self.comment = '{}/{}/{}/{}/{}'.format(
            self.customer.cust_name,
            self.timesheet.cust_location.location_name,
            self.timesheet.sheet_turn,
            self.customer_service.service.name if self.customer_service else '-',
            self.worker.position
        )
        try:
            delivery_request = DeliveryRequest.objects.get(
                requestworker__requestworkerturnout__workerturnout=self.turnout
            )
        except ObjectDoesNotExist:
            pass
        else:
            self.comment += ' ({}; {})'.format(
                delivery_request.pk,
                delivery_request.address()
            )

    def setup_customer_operation(self):
        assert self.customer_service is not None

        customer_amount = self.calculator.customer_calculator.get_amount(self.turnout)

        self.new_customer_operation = Operation(
            timepoint=self.timesheet.sheet_date,
            author=self.author,
            comment=self.comment,
            debet=self.customer_account.account_76_debts,
            credit=self.customer_service.account_76,
            amount=customer_amount,
        )

    def _new_worker_operation_amount(self):
        if self.customer_service is None:
            return None

        # Todo: is this a correct way to get foreman?
        if self.worker == self.timesheet.foreman:
            amount = self.calculator.foreman_calculator.get_amount(self.turnout)
        else:
            amount = self.calculator.worker_calculator.get_amount(self.turnout)

        # Надбавка за должность
        try:
            position_calculator = PositionCalculator.objects.get(
                Q(last_day__isnull=True) |
                Q(last_day__gte=self.timesheet.sheet_date),
                customer=self.customer,
                position=self.worker.position,
                first_day__lte=self.timesheet.sheet_date,
            )
        except ObjectDoesNotExist:
            pass
        else:
            amount += position_calculator.calculator.get_amount(self.turnout)

        return amount

    def setup_worker_and_tax_operation(self):
        assert self.customer_service is not None

        customer_amount = self.new_customer_operation.amount
        self.full_worker_amount = self._new_worker_operation_amount()

        if self.worker.selfemployment_data.filter(deletion_ts__isnull=True).exists():
            debit = self.customer_service.account_20_selfemployed_work

            tax_debit = self.customer_service.account_20_selfemployed_taxes

            self.full_worker_amount /= decimal.Decimal(0.94) # Current self employment tax rate
            self.full_worker_amount = round(self.full_worker_amount)

            tax_amount = (customer_amount - self.full_worker_amount) * _PLANNED_TAX_FACTOR
        else:
            debit = self.customer_service.account_20_general_work

            tax_debit = self.customer_service.account_20_general_taxes

            self.full_worker_amount = round(self.full_worker_amount)

            tax_amount = customer_amount * _PLANNED_TAX_FACTOR

        if self.is_turnout_in_paysheet:
            worker_amount = self.current_worker_operation.operation.amount
        else:
            worker_amount = self.full_worker_amount

        self.new_worker_operation = Operation(
            timepoint=self.timesheet.sheet_date,
            author=self.author,
            comment=self.comment,
            debet=debit,
            credit=self.worker_account.account,
            amount=worker_amount,
        )

        root_77 = get_root_account('77. ')
        self.new_tax_operation = Operation(
            timepoint=self.timesheet.sheet_date,
            author=self.author,
            comment=f'Планируемый налог за выход {self.turnout.pk}/{self.comment}',
            debet=tax_debit,
            credit=root_77,
            amount=tax_amount,
        )

    def setup_deduction(self, worker_deduction_amount):
        if self.deduction_worker is not None:
            # Todo: another concurrency problem here
            worker_saldo = max(0, -1 * self.worker_account.account.turnover_saldo())

            if worker_saldo < worker_deduction_amount:
                extra_deduction_amount = worker_deduction_amount - worker_saldo
                worker_deduction_amount = worker_saldo

                extra_deduction_comment = 'Перенос части вычета за переплату ' \
                    'с работника {} за выход {}/{}'.format(
                        self.worker,
                        self.turnout.pk,
                        self.comment
                    )

                self.new_deduction_operation = Operation(
                    author=self.author,
                    comment=extra_deduction_comment,
                    debet=self.deduction_worker_account.account,
                    credit=self.customer_account.account_90_1_disciplinary_deductions,
                    amount=extra_deduction_amount,
                )

        self.new_adjusting_operation = Operation(
            timepoint=self.timesheet.sheet_date,
            author=self.author,
            comment=f'Вычет за переплату за выход {self.turnout.pk}/{self.comment}',
            debet=self.worker_account.account,
            credit=self.customer_account.account_90_1_disciplinary_deductions,
            amount=worker_deduction_amount,
        )

    def setup_adjusting_and_deduction_operations(self):
        self.new_adjusting_operation = None
        self.new_deduction_operation = None

        if not self.is_turnout_in_paysheet:
            return

        last_paid_turnout = WorkerTurnout.objects.filter(
            worker=self.worker,
            turnoutoperationtopay__operation__isnull=False,
            turnoutoperationtopay__operation__paysheet_entry_operation__isnull=False
        ).order_by(
          'timesheet__sheet_date'
        ).last()

        if self.customer_service is None:
            current_worker_amount = self._current_worker_amount()
            if current_worker_amount > 0:
                self.setup_deduction(current_worker_amount)
        else:
            new_worker_amount = self.new_worker_operation.amount

            if self.full_worker_amount > new_worker_amount:
                # Need to make extra payment
                self.new_adjusting_operation = Operation(
                    timepoint=self.timesheet.sheet_date,
                    author=self.author,
                    comment=f'Доп. начисление за выход {self.turnout.pk}/{self.comment}',
                    debet=self.new_worker_operation.debet,
                    credit=self.worker_account.account,
                    amount=self.full_worker_amount - self.new_worker_operation.amount,
                )

            elif self.full_worker_amount < new_worker_amount:
                # Need to make deduction
                worker_deduction_amount = new_worker_amount - self.full_worker_amount

                self.setup_deduction(worker_deduction_amount)

    def setup_operations(self):
        if self.customer_service is None:
            self.new_customer_operation = None
            self.new_tax_operation = None

            self.new_worker_operation = None
            if self.is_turnout_in_paysheet and self.current_worker_operation is not None:
                self.new_worker_operation = self.current_worker_operation.operation
        else:
            self.setup_customer_operation()

            self.setup_worker_and_tax_operation()

        self.setup_adjusting_and_deduction_operations()

    # get_xxx_operation_report():
    #
    # Возвращает (комментарий про изменение суммы, флаг confirmation_required).
    # Подтверждение требуется, если операция 'ухудшает' состояние deduction_worker
    # или работника (появляется новый вычет, увеличивается его сумма,
    # или же уменьшается сумма выплаты)

    def _current_worker_amount(self):
        if self.current_worker_operation is None:
            return 0
        else:
            return self.current_worker_operation.operation.amount

    def get_worker_operation_report(self):
        if self.new_worker_operation is None:
            new_worker_amount = 0
        else:
            new_worker_amount = self.new_worker_operation.amount

        current_worker_amount = self._current_worker_amount()

        message = None
        if new_worker_amount != current_worker_amount:
            message = 'Начисление работнику {} изменилось: {}'.format(
                self.worker,
                _amount_change_message(current_worker_amount, new_worker_amount)
            )

        return message, new_worker_amount < current_worker_amount

    def get_adjusting_operation_report(self):
        if self.new_adjusting_operation is None:
            new_adjusting_amount = 0
        else:
            new_adjusting_amount = self.new_adjusting_operation.amount

            if self.new_adjusting_operation.debet == self.worker_account.account:
                new_adjusting_amount = -1 * new_adjusting_amount

        if self.current_adjusting_operation is None:
            current_adjusting_amount = 0
        else:
            current_adjusting_amount = self.current_adjusting_operation.operation.amount

            if self.current_adjusting_operation.operation.debet == self.worker_account.account:
                current_adjusting_amount = -1 * current_adjusting_amount

        # Positive amount means extra payment, negative - deduction

        message = None
        confirmation_required = new_adjusting_amount < current_adjusting_amount
        if new_adjusting_amount != current_adjusting_amount:
            if new_adjusting_amount > 0:
                message_prefix = 'Корректирующее начисление'
            else:
                message_prefix = 'Корректирующий вычет'
                new_adjusting_amount = -1 * new_adjusting_amount
                current_adjusting_amount = -1 * current_adjusting_amount
            message = '{} работнику {} {}: {}'.format(
                message_prefix,
                self.worker,
                'изменилось' if new_adjusting_amount > 0 else 'изменился',
                _amount_change_message(current_adjusting_amount, new_adjusting_amount)
            )

        return message, confirmation_required

    def get_deduction_operation_report(self):
        if self.new_deduction_operation is None:
            new_deduction_amount = 0
        else:
            new_deduction_amount = self.new_deduction_operation.amount

        if self.current_deduction_operation is None:
            current_deduction_amount = 0
        else:
            current_deduction_amount = self.current_deduction_operation.operation.amount

        message = None
        if new_deduction_amount != current_deduction_amount:
            message = 'Корректирующий вычет работнику {} изменился: {}'.format(
                self.deduction_worker,
                _amount_change_message(current_deduction_amount, new_deduction_amount)
            )

        return message, new_deduction_amount > current_deduction_amount

    def get_reports(self):
        reports = []
        reports.append(self.get_worker_operation_report())
        reports.append(self.get_adjusting_operation_report())
        reports.append(self.get_deduction_operation_report())

        confirmation_required = False
        messages = []
        for message, flag in reports:
            if flag:
                confirmation_required = True
            if message is not None:
                messages.append(message)

        return messages, confirmation_required

    def _commit_operation(self, operation_name, Model, ignore_is_closed=False):
        current_operation = getattr(self, f'current_{operation_name}')
        new_operation = getattr(self, f'new_{operation_name}')
        if current_operation is None:
            if new_operation is not None:
                new_operation.save()
                Model.objects.create(
                    turnout=self.turnout,
                    operation=new_operation
                )
        else:
            if new_operation is None:
                self._delete_current_operation(operation_name)
            else:
                operation = current_operation.operation
                operation_was_closed = operation.is_closed
                if operation.is_closed and ignore_is_closed:
                    operation.is_closed = False

                update_if_changed(
                    operation,
                    new_operation.amount,
                    new_operation.debet,
                    new_operation.credit,
                    comment=new_operation.comment,
                    timepoint=new_operation.timepoint,
                )
                if operation_was_closed and ignore_is_closed:
                    Operation.objects.filter(pk=operation.pk).update(is_closed=True)

    def commit_operations(self):
        self._commit_operation('customer_operation', TurnoutCustomerOperation)
        self._commit_operation('worker_operation', TurnoutOperationToPay, True)
        self._commit_operation('tax_operation', TurnoutTaxOperation)
        self._commit_operation('adjusting_operation', TurnoutAdjustingOperation)
        self._commit_operation('deduction_operation', TurnoutDeduction)


@transaction.atomic
def update_turnout_payments(turnout_pk, author, deduction_worker=None, force_commit=False):
    turnout = WorkerTurnout.objects.select_for_update().get(pk=turnout_pk)

    calculation = TurnoutCalculation(turnout, author, deduction_worker)
    calculation.setup()

    messages, confirmation_required = calculation.get_reports()

    if force_commit:
        confirmation_required = False

    if not confirmation_required:
        calculation.commit_operations()
        update_hostel_bonus(turnout, author)

        # Deposit is disabled right now
#        update_worker_deposit(turnout.timesheet.customer, turnout.worker, author)

    return messages, confirmation_required


def update_not_paid_turnout_payments(worker, author):
    last_paid_turnout = WorkerTurnout.objects.filter(
        worker=worker,
        turnoutoperationtopay__operation__isnull=False,
        turnoutoperationtopay__operation__paysheet_entry_operation__isnull=False
    ).order_by(
      'timesheet__sheet_date'
    ).last()

    turnouts_to_update = WorkerTurnout.objects.filter(
        worker=worker,
        turnoutoperationtopay__operation__isnull=False,
        turnoutoperationtopay__operation__paysheet_entry_operation__isnull=True,
    )
    if last_paid_turnout:
        turnouts_to_update = turnouts_to_update.filter(
            timesheet__sheet_date__gte=last_paid_turnout.timesheet.sheet_date
        )

    for turnout in turnouts_to_update:
        update_turnout_payments(turnout.pk, author, force_commit=True)
