# -*- coding: utf-8 -*-

import datetime

from django.shortcuts import render
from django.utils import timezone

from the_redhuman_is import forms
from the_redhuman_is import models

from utils import date_time

from the_redhuman_is.auth import staff_account_required


# [begin, end)
def _interval(year, month):
    begin = datetime.datetime(year=year, month=month, day=1)
    next_year = year
    next_month = month + 1
    if next_month >= 13:
        next_month = 1
        next_year = year + 1
    end = datetime.datetime(year=next_year, month=next_month, day=1)
    return begin, end


def _worked(location, year, month):
    begin, end = _interval(year, month)
    workers = models.Worker.objects.filter(
        worker_turnouts__timesheet__cust_location=location,
        worker_turnouts__timesheet__sheet_date__gte=begin,
        worker_turnouts__timesheet__sheet_date__lt=end,
    ).distinct()
    return begin, end, workers


def _hired_fired(location, year, month):
    begin, end, workers = _worked(location, year, month)
    hired = workers.exclude(
        worker_turnouts__timesheet__sheet_date__lt=begin,
    )
    fired = workers.exclude(
        worker_turnouts__timesheet__sheet_date__gte=end,
    )
    hired_fired = hired.exclude(
        worker_turnouts__timesheet__sheet_date__gte=end,
    )
    return hired, fired, hired_fired


def _hired_fired_disjoint(location, year, month):
    hired, fired, hired_fired = _hired_fired(location, year, month)
    hired_unique = hired.exclude(pk__in=fired)
    fired_unique = fired.exclude(pk__in=hired)
    return hired_unique, fired_unique, hired_fired


def _customer_location_row(location, months):
    result = []
    for year, month in months:
        hired, fired, hired_fired = _hired_fired(location, year, month)
        result.append(
            (
                hired.count(),
                fired.count(),
                hired_fired.count(),
                year,
                month
            )
        )

    return result


@staff_account_required
def hired_fired(request):
    last = timezone.now()
    first = datetime.datetime(year=last.year-1, month=last.month, day=1)
    months = date_time.months(first, last)

    managers = models.MaintenanceManager.objects.all()
    form_initial = {}
    param_manager_pk = request.GET.get('manager')
    if param_manager_pk:
        worker = models.Worker.objects.get(pk=param_manager_pk)
        managers = managers.filter(worker=worker)
        form_initial['manager'] = worker

    locations = models.CustomerLocation.objects.filter(
        customer_id__maintenancemanager__in=managers
    ).distinct()

    data = []
    sum_row = [(0, 0, 0) for i in range(len(months))]
    for location in locations:
        row = _customer_location_row(location, months)
        for i in range(len(row)):
            hired, fired, hired_fired, year, month = row[i]
            sum_hired, sum_fired, sum_hired_fired = sum_row[i]
            sum_row[i] = (sum_hired + hired, sum_fired + fired, sum_hired_fired + hired_fired)
        data.append((location, row))

    def _key(item):
        location, row = item
        return '{} {}'.format(location.customer_id, location)

    return render(
        request,
        'the_redhuman_is/reports/hired_fired.html',
        {
            'form': forms.StaffTurnoverForm(initial=form_initial),
            'months': [datetime.datetime(year=year, month=month, day=1) for year, month in months],
            'data': sorted(data, key=_key),
            'sum_row': sum_row,
        }
    )


# Todo: make location_pk optional?
@staff_account_required
def hired_fired_details(request, location_pk, year, month):
    year = int(year)
    month = int(month)
    location = models.CustomerLocation.objects.get(pk=location_pk)
    hired, fired, hired_fired = _hired_fired_disjoint(location, year, month)

    return render(
        request,
        'the_redhuman_is/reports/hired_fired_details.html',
        {
            'hired': hired,
            'fired': fired,
            'hired_fired': hired_fired,
        }
    )
