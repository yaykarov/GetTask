import datetime
from typing import Optional

from django.core.exceptions import ValidationError
from django.db.models import Q

from the_redhuman_is.models.models import (
    Customer,
    CustomerLocation,
    TimeSheet,
)
from the_redhuman_is.models.reconciliation import Reconciliation
from utils.functools import pairwise


def assert_can_reconcile_turnout(
        location: CustomerLocation,
        customer: Customer,
        turnout_date: datetime.date,
        verbose_class_name: str
):
    closed_reconciliation = _get_reconciliation_if_closed(
        customer.pk,
        location.pk,
        turnout_date
    )
    if closed_reconciliation is not None:
        # if it's closed
        raise ValidationError(  # disallow all timesheet changes
            'Попытка изменить/создать {}, который попадает в закрытую сверку {}'.format(
                verbose_class_name,
                closed_reconciliation,
            )
        )
    # if it's not closed or does not exist
    try:
        _check_sequence(location.pk, turnout_date)
    except ValidationError as ex:
        raise ValidationError(
            'Первый {} для объекта {} за {} не может быть создан,'
            ' так как это приведет к конфликту сверок: {}'.format(
                verbose_class_name,
                location,
                turnout_date,
                ex.message
            )
        )


def _get_reconciliation_if_closed(
        customer_id: int,
        location_id: int,
        date: datetime.date
) -> Optional[Reconciliation]:
    return Reconciliation.objects.filter(
        Q(location__isnull=True) | Q(location=location_id),
        customer=customer_id,
        first_day__lte=date,
        last_day__gte=date,
        is_closed=True
    ).first()  # get reconciliation which spans this date


def _check_sequence(location_id: int, date: datetime.date) -> None:
    has_earlier_timesheets = TimeSheet.objects.filter(
        cust_location=location_id,
        sheet_date__lte=date
    ).exists()

    # if earlier timesheets exist:
    #   if the reconciliation is open, we can add a timesheet/turnout
    #   if the reconciliation does not exist, a gap cannot exist
    #       and we can add a timesheet/turnout after the tail end of the sequence

    # if earlier timesheets do not exist, absence of gaps is not guaranteed
    if not has_earlier_timesheets:
        validate_reconciliation_sequence(location_id, date)


def validate_reconciliation_sequence(location_id: int, date: datetime.date):
    # get concurrent and future reconciliations
    reconciliations = list(
        Reconciliation.objects.filter(
            Q(location__isnull=True) | Q(location=location_id),
            last_day__gte=date,
        ).values('id', 'first_day', 'last_day')
    )
    if not reconciliations:  # if none exist, the date is safe
        return
    first_recon = reconciliations[0]
    # if a concurrent reconciliation does not exist,
    # existing future reconciliations will not allow to create it,
    # and the date will be impossible to reconcile
    if reconciliations[0]['first_day'] > date:
        raise ValidationError(
            'Дата {} раньше первой сверки {} ({} - {})'.format(
                date,
                first_recon[0]['id'],
                first_recon[0]['first_day'],
                first_recon[0]['last_day'],
            )
        )
    # otherwise we need to check the sequence for (absence of) gaps
    for prv, nxt in pairwise(reconciliations):
        if prv['last_day'] + datetime.timedelta(days=1) != nxt['first_day']:
            raise ValidationError(
                'Нестыковка сверок {} ({} - {}) и {} ({} - {})'.format(
                    prv['id'],
                    prv['first_day'],
                    prv['last_day'],
                    nxt['id'],
                    nxt['first_day'],
                    nxt['last_day'],
                )
            )


def ensure_unclosed(
        customer_id: int,
        location_id: int,
        date: datetime.date,
        check_if_can_create_reconciliation: bool = False
):
    closed_reconciliation = _get_reconciliation_if_closed(customer_id, location_id, date)
    if closed_reconciliation is not None:
        raise ValidationError(f'Сверка {closed_reconciliation} закрыта.')
    if check_if_can_create_reconciliation:
        _check_sequence(location_id, date)
