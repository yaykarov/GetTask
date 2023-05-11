# -*- coding: utf-8 -*-

import datetime

from django.db import transaction
from django.db.models import Sum
from django.http import HttpResponse
from django.http import JsonResponse
from django.utils.timezone import make_aware

from finance import model_utils

from finance.models import Operation

from the_redhuman_is import models
from the_redhuman_is.auth import staff_account_required

from the_redhuman_is.models.deposit import ensure_worker_deposit


@staff_account_required
def oldi_hostel(request):
    saldo_date = make_aware(datetime.datetime(day=8, month=1, year=2019))

    # ОЛДИ
    customer = models.Customer.objects.get(pk=26)

    root = model_utils.get_account('76.')
    special_account = model_utils.ensure_account(root, 'Технический')

    workers = models.Worker.objects.filter(
        worker_turnouts__timesheet__customer=customer
    ).distinct()

    response = []

    with transaction.atomic():
        for worker in workers:
            account = worker.worker_account.account

            operations = Operation.objects.filter(
                timepoint__lt=saldo_date
            )

            debit = operations.filter(
                debet=account
            ).aggregate(
                Sum('amount')
            )['amount__sum']

            credit = operations.filter(
                credit=account
            ).aggregate(
                Sum('amount')
            )['amount__sum']

            if debit is None and credit is None:
                continue

            if debit is None:
                debit = 0.0

            if credit is None:
                credit = 0.0

            amount = credit - debit

            if amount <= 0:
                continue

            operation = Operation.objects.create(
                timepoint=saldo_date,
                author=request.user,
                comment='Техническая проводка, оплата общежития',
                debet=account,
                credit=special_account,
                amount=amount
            )

            response.append((str(worker), amount, operation.pk))

    return JsonResponse(response, safe=False)


@staff_account_required
def deposit_for_all_workers(request):
    for worker in models.Worker.objects.all():
        ensure_worker_deposit(worker)

    return HttpResponse('ok')


@staff_account_required
def fix_deposits(request):
    root = model_utils.get_account("76")
    deposits = model_utils.ensure_account(root, "Депозиты")
    for deposit in models.WorkerDeposit.objects.all():
        account = deposit.account
        account.parent = deposits
        account.save()

    return HttpResponse('ok')


@staff_account_required
def oldi_workers(request):
    first_day = datetime.date(year=2019, month=4, day=16)
    last_day = datetime.date(year=2019, month=4, day=30)
    workers = models.Worker.objects.filter(
        worker_turnouts__timesheet__customer__pk=26, # oldi
        worker_turnouts__timesheet__sheet_date__range=(first_day, last_day)
    ).exclude(
        worker_turnouts__timesheet__sheet_date__gt=last_day
    ).distinct()

    return JsonResponse(
        [str(w) + ';' + w.tel_number for w in workers],
        safe=False
    )
