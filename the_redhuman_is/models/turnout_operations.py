# -*- coding: utf-8 -*-

from django.db import models

import finance

from the_redhuman_is.models.models import WorkerTurnout


class TurnoutOperationToPay(models.Model):
    turnout = models.OneToOneField(
        WorkerTurnout,
        on_delete=models.PROTECT,
        verbose_name='Выход'
    )
    operation = models.ForeignKey(
        finance.models.Operation,
        on_delete=models.PROTECT,
        verbose_name='Операция'
    )

    def __str__(self):
        return '{} {}'.format(self.turnout, self.operation)


class TurnoutAdjustingOperation(models.Model):
    turnout = models.OneToOneField(
        WorkerTurnout,
        on_delete=models.PROTECT,
        verbose_name='Выход'
    )
    operation = models.ForeignKey(
        finance.models.Operation,
        on_delete=models.PROTECT,
        verbose_name='Операция'
    )

    def __str__(self):
        return '{} {}'.format(self.turnout, self.operation)


# Todo: remove this
class TurnoutOperationIsPayed(models.Model):
    turnout = models.ForeignKey(
        WorkerTurnout,
        on_delete=models.PROTECT,
        verbose_name='Выход'
    )
    operation = models.ForeignKey(
        finance.models.Operation,
        on_delete=models.PROTECT,
        verbose_name='Операция'
    )

    def __str__(self):
        return '{} {}'.format(self.turnout, self.operation)


class TurnoutCustomerOperation(models.Model):
    turnout = models.OneToOneField(
        WorkerTurnout,
        on_delete=models.PROTECT,
        verbose_name='Выход'
    )
    operation = models.ForeignKey(
        finance.models.Operation,
        on_delete=models.PROTECT,
        verbose_name='Операция'
    )

    def __str__(self):
        return '{} {}'.format(self.turnout, self.operation)


class TurnoutTaxOperation(models.Model):
    turnout = models.OneToOneField(
        WorkerTurnout,
        on_delete=models.PROTECT,
        verbose_name='Выход'
    )
    operation = models.ForeignKey(
        finance.models.Operation,
        on_delete=models.PROTECT,
        verbose_name='Операция'
    )

    def __str__(self):
        return '{} {}'.format(self.turnout, self.operation)


class TurnoutDeduction(models.Model):
    turnout = models.ForeignKey(
        WorkerTurnout,
        on_delete=models.PROTECT,
        related_name='deductions'
    )
    operation = models.ForeignKey(
        finance.models.Operation,
        on_delete=models.PROTECT,
    )

    def __str__(self):
        return '{} {}'.format(self.turnout, self.operation)


class TurnoutBonus(models.Model):
    turnout = models.ForeignKey(
        WorkerTurnout,
        on_delete=models.PROTECT,
    )
    operation = models.ForeignKey(
        finance.models.Operation,
        on_delete=models.PROTECT,
    )

    def __str__(self):
        return '{} {}'.format(self.turnout, self.operation)


class CustomerFine(models.Model):
    turnout = models.ForeignKey(
        WorkerTurnout,
        on_delete=models.PROTECT,
    )
    operation = models.OneToOneField(
        finance.models.Operation,
        on_delete=models.PROTECT,
    )

    def __str__(self):
        return '{} {}'.format(self.turnout, self.operation)
