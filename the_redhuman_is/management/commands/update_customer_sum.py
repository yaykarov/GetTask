# -*- coding: utf-8 -*-

from django.core.management.base import BaseCommand

from django.db.models import Q

from finance.models import update_if_changed

from the_redhuman_is import models

from utils.date_time import date_from_string


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('--customer', type=int, required=True)
        parser.add_argument('--location', type=int)
        parser.add_argument('--first_day', type=date_from_string, required=True)
        parser.add_argument('--last_day', type=date_from_string, required=True)

    # see models/turnout_calculators.py for reference
    def handle(self, *args, **options):
        customer = models.Customer.objects.get(pk=options['customer'])
        location_pk = options.get('location', None)
        print(customer)

        first_day = options['first_day']
        last_day = options['last_day']

        turnouts = models.WorkerTurnout.objects.filter(
            timesheet__customer=customer,
            timesheet__sheet_date__range=(first_day, last_day)
        )
        if location_pk is not None:
            turnouts = turnouts.filter(
                timesheet__cust_location_id=location_pk
            )

        for turnout in turnouts:
            timesheet = turnout.timesheet
            if not hasattr(turnout, 'turnoutservice'):
                continue
            customer_service = turnout.turnoutservice.customer_service

            calculator = models.AmountCalculator.objects.get(
                Q(servicecalculator__last_day__isnull=True) |
                Q(servicecalculator__last_day__gte=timesheet.sheet_date),
                servicecalculator__customer_service=customer_service,
                servicecalculator__first_day__lte=timesheet.sheet_date,
            )

            customer_amount = calculator.customer_calculator.get_amount(turnout)

            turnout_customer_operation = models.TurnoutCustomerOperation.objects.filter(
                turnout=turnout
            )
            if turnout_customer_operation.exists():
                if turnout_customer_operation.count() > 1:
                    raise Exception(
                        "Multiple operations for turnout {}".format(
                            turnout
                        )
                    )
                operation = turnout_customer_operation.first().operation
                update_if_changed(
                    operation,
                    customer_amount,
                    timepoint=timesheet.sheet_date
                )
