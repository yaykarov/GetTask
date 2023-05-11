# -*- coding: utf-8 -*-

import datetime

from django.shortcuts import render

from .. import forms
from .. import models

from the_redhuman_is.auth import staff_account_required
from utils.date_time import date_from_string


def _days(first_day, last_day):
    return [
        first_day + datetime.timedelta(days=d) for d in range(
            0,
            (last_day-first_day).days + 1
        )
    ]


def _absents(location, day):
    previous_day = day - datetime.timedelta(days=1)
    return models.Worker.objects.filter(
        worker_turnouts__timesheet__cust_location=location,
        worker_turnouts__timesheet__sheet_date=previous_day
    ).exclude(
        worker_turnouts__timesheet__sheet_date=day
    ).distinct()


def _customer_location_row(location, days):
    result = []
    for day in days:
        absents = _absents(location, day)
        result.append(absents.count())

    return result


@staff_account_required
def report_absent(request):
    last_day = datetime.date.today()
    first_day = last_day - datetime.timedelta(days=7)
    managers = models.MaintenanceManager.objects.all()

    user_groups = request.user.groups.values_list('name', flat=True)
    if 'Менеджеры' in user_groups:
        managers = managers.filter(
            worker__workeruser__user=request.user
        )

    param_first_day = request.GET.get('first_day')
    param_last_day = request.GET.get('last_day')
    param_manager_pk = request.GET.get('manager')

    if param_first_day:
        first_day = date_from_string(param_first_day)

    if param_last_day:
        last_day = date_from_string(param_last_day)

    manager = None
    if param_manager_pk:
        manager = models.Worker.objects.get(pk=int(param_manager_pk))
        managers = managers.filter(worker=manager)

    locations = models.CustomerLocation.objects.filter(
        customer_id__maintenancemanager__in=managers
    ).distinct()

    days = _days(first_day, last_day)

    data = []
    for location in locations:
        turnouts = models.WorkerTurnout.objects.filter(
            timesheet__cust_location=location,
            timesheet__sheet_date__gte=first_day,
            timesheet__sheet_date__lte=last_day
        )
        if turnouts.exists():
            data.append(
                (
                    location,
                    _customer_location_row(location, days)
                )
            )

    return render(
        request,
        'the_redhuman_is/reports/absent.html',
        {
            'days': days,
            'data': data,
            'form': forms.ManagerAndIntervalForm(
                initial={
                    'manager': manager,
                    'first_day': first_day,
                    'last_day': last_day,
                }
            )
        }
    )


@staff_account_required
def absent_details(request, location_pk, date):
    day = date_from_string(date)
    location = models.CustomerLocation.objects.get(pk=location_pk)

    return render(
        request,
        'the_redhuman_is/reports/workers_list.html',
        {
            'title': 'Невышедшие рабочие',
            'location': location,
            'day': day,
            'workers': _absents(location, day),
        }
    )
