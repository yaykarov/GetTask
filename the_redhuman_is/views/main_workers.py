# -*- coding: utf-8 -*-

# Todo: make this a part of the 'reports' module

import datetime

from django.db.models import Case
from django.db.models import IntegerField
from django.db.models import Q
from django.db.models import Sum
from django.db.models import When

from django.shortcuts import render

from django.utils import timezone

from the_redhuman_is import models
from the_redhuman_is.auth import staff_account_required
from the_redhuman_is.views.utils import get_first_last_day

from the_redhuman_is.forms import DaysIntervalForm


def _count_turnouts(
        workers,
        first_day,
        last_day,
        field_name='turnouts_count'):
    params = {
        field_name: Sum(
            Case(
                When(
                    Q(
                        worker_turnouts__timesheet__sheet_date__gte=first_day
                    ) & Q(
                        worker_turnouts__timesheet__sheet_date__lte=last_day
                    ),
                    then=1
                ),
                default=0
            ),
            output_field=IntegerField()
        )
    }

    pks = [w.pk for w in workers]
    annotated = models.Worker.objects.filter(
        pk__in=pks
    ).annotate(
        **params
    )
    return annotated


# workers should have turnouts_count annotation
def _data(workers, turnouts, target_turnouts_count, exact):
    russian = workers.filter(citizenship__name='РФ')
    not_russian = workers.exclude(citizenship__name='РФ')

    def _count(sample):
        if exact:
            _workers = sample.filter(
                turnouts_count=target_turnouts_count
            )
        else:
            _workers = sample.filter(
                turnouts_count__gte=target_turnouts_count
            )
        _turnouts = turnouts.filter(
            worker__in=_workers
        )
        return _workers.count(), _turnouts.count()

    return (
        _count(russian),
        _count(not_russian)
    )


def _percentage(part, total):
    if total > 0:
        percentage = part * 100.0 / total
    else:
        percentage = 0.0
    return '{:.2f}%'.format(percentage)


def _formatted_data(workers, turnouts, target_turnouts_count, exact=False):
    count_russian, count_not_russian = _data(
        workers,
        turnouts,
        target_turnouts_count,
        exact
    )

    workers_russian, turnouts_russian = count_russian
    workers_not_russian, turnouts_not_russian = count_not_russian

    workers_main = workers_russian + workers_not_russian
    turnouts_main = turnouts_russian + turnouts_not_russian

    return [
        ('Всего, чел.', workers_main),
        ('РФ, чел.', workers_russian),
        ('Не РФ, чел.', workers_not_russian),
        ('Всего, %', _percentage(workers_main, workers.count())),
        ('РФ, %', _percentage(workers_russian, workers.count())),
        (
            'Не РФ, %',
            _percentage(workers_not_russian, workers.count())
        ),
        (
            'Выходов всего, %',
            _percentage(turnouts_main, turnouts.count())
        ),
        (
            'Выходов РФ, %',
            _percentage(turnouts_russian, turnouts.count())
        ),
        (
            'Выходов не РФ, %',
            _percentage(turnouts_not_russian, turnouts.count())
        ),
        ('Выходов всего, шт', turnouts_main),
    ]


def _make_grid(workers, first_day, last_day, exact):
    turnouts = models.WorkerTurnout.objects.filter(
        timesheet__sheet_date__gte=first_day,
        timesheet__sheet_date__lte=last_day
    ).distinct(
    )

    row_names = []
    rows = []

    day_count = (last_day - first_day).days + 1
    for n in range(day_count):
        data = _formatted_data(
            workers,
            turnouts,
            n + 1,
            exact
        )

        if not row_names:
            row_names = [name for name, value in data]
            rows = [[] for i in range(len(data))]

        for i in range(len(data)):
            name, value = data[i]
            rows[i].append(value)

    row_names.insert(0, '')
    rows.insert(0, [i + 1 for i in range(day_count)])

    return zip(row_names, rows)


def _filter_workers(first_day, last_day):
    workers = models.Worker.objects.filter(
        worker_turnouts__timesheet__sheet_date__gte=first_day,
        worker_turnouts__timesheet__sheet_date__lte=last_day
    ).distinct()
    return workers


@staff_account_required
def workers_count(request):
    first_day, last_day = get_first_last_day(request)
    day_format = '%d.%m'
    normal_interval = '{}-{}'.format(
        first_day.strftime(day_format),
        last_day.strftime(day_format)
    )

    normal_workers = _filter_workers(
        first_day,
        last_day,
    )
    normal_workers = _count_turnouts(
        normal_workers,
        first_day,
        last_day
    )

    extended_first_day = first_day - datetime.timedelta(days=60)
    today = timezone.now().date()
    extended_interval = '{}-{}'.format(
        extended_first_day.strftime(day_format),
        today.strftime(day_format)
    )

    extended_workers = _filter_workers(
        first_day,
        last_day,
    )
    extended_workers = _count_turnouts(
        extended_workers,
        extended_first_day,
        today
    )

    return render(
        request,
        'the_redhuman_is/reports/main_workers/workers_count.html',
        {
            'first_day': first_day,
            'last_day': last_day,

            'grids': [
                (
                    'В столбцах - кол-во работников, у которых было ровно Х выходов и кол-во выходов у таких работников <br><br> на интервале {}'.format(normal_interval),
                    _make_grid(normal_workers, first_day, last_day, exact=True)
                ),
                (
                    'на интервале {}'.format(extended_interval),
                    _make_grid(extended_workers, first_day, last_day, exact=True)
                ),

                (
                    'В столбцах - кол-во работников, у которых было не меньше Х выходов и кол-во выходов у таких работников <br><br> на интервале {}'.format(normal_interval),
                    _make_grid(normal_workers, first_day, last_day, exact=False)
                ),
                (
                    'на интервале {}'.format(extended_interval),
                    _make_grid(extended_workers, first_day, last_day, exact=False)
                ),
            ],

            'filter_form': DaysIntervalForm(
                initial={
                    'first_day': first_day,
                    'last_day': last_day
                }
            )
        }
    )


@staff_account_required
def main_workers_distribution(request):
    turnouts_param = request.GET.get('target_turnouts_count')
    if turnouts_param and turnouts_param.isdigit():
        target_turnouts_count = int(turnouts_param)
    else:
        target_turnouts_count = 4

    interval_param = request.GET.get('target_interval')
    if interval_param in ['normal', 'extended']:
        target_interval = interval_param
    else:
        target_interval = 'normal'

    first_day, last_day = get_first_last_day(request)

    if target_interval == 'extended':
        target_first_day = first_day - datetime.timedelta(days=60)
        target_last_day = timezone.now().date()
    else:
        target_first_day = first_day
        target_last_day = last_day

    rows = []

    locations = models.CustomerLocation.objects.filter(
        timesheet__sheet_date__gte=first_day,
        timesheet__sheet_date__lte=last_day,
    ).distinct()

    def _add_row(name1, name2, turnouts):
        workers = models.Worker.objects.filter(
            worker_turnouts__in=turnouts
        ).distinct()

        workers = _count_turnouts(
            workers,
            target_first_day,
            target_last_day
        )

        rows.append(
            (
                name1,
                name2,
                _formatted_data(
                    workers,
                    turnouts,
                    target_turnouts_count
                )
            )
        )

    for location in locations:
        turnouts = models.WorkerTurnout.objects.filter(
            timesheet__sheet_date__gte=first_day,
            timesheet__sheet_date__lte=last_day,
            timesheet__cust_location=location,
        ).distinct()

        _add_row(location.customer_id, location.location_name, turnouts)

    # Итого
    turnouts = models.WorkerTurnout.objects.filter(
        timesheet__sheet_date__gte=first_day,
        timesheet__sheet_date__lte=last_day,
    ).distinct()

    _add_row('<b>Итого</b>', '-', turnouts)

    return render(
        request,
        'the_redhuman_is/reports/main_workers/distribution_over_clients.html',
        {
            'target_turnouts_count': target_turnouts_count,
            'target_interval': target_interval,
            'target_first_day': target_first_day,
            'target_last_day': target_last_day,
            'filter_form': DaysIntervalForm(
                initial={
                    'first_day': first_day,
                    'last_day': last_day
                }
            ),
            'data': rows
        }
    )


@staff_account_required
def workers_lifetime(request):
    first_day, last_day = get_first_last_day(request)

    turnouts_overall = models.WorkerTurnout.objects.filter(
        timesheet__sheet_date__gte=first_day,
        timesheet__sheet_date__lte=last_day,
    ).distinct()

    workers_overall = models.Worker.objects.filter(
        worker_turnouts__in=turnouts_overall
    ).distinct()

    rows = []
    max_count = 0

    def _add_row(name1, name2, turnouts):
        workers = models.Worker.objects.filter(
            worker_turnouts__in=turnouts
        ).distinct()

        workers = _count_turnouts(
            workers,
            first_day,
            last_day
        )

        row = {}

        for worker in workers:
            nonlocal max_count
            count = worker.turnouts_count
            if count > max_count:
                max_count = count
            row[count] = row.get(count, 0) + 1

        rows.append((name1, name2, row))

    locations = models.CustomerLocation.objects.filter(
        timesheet__sheet_date__gte=first_day,
        timesheet__sheet_date__lte=last_day,
    ).distinct()

    for location in locations:
        turnouts = models.WorkerTurnout.objects.filter(
            timesheet__sheet_date__gte=first_day,
            timesheet__sheet_date__lte=last_day,
            timesheet__cust_location=location,
        ).distinct()

        _add_row(location.customer_id, location.location_name, turnouts)

    postprocessed_rows = []

    for name1, name2, compressed_row in rows:
        row = []
        for i in range(max_count):
            count = compressed_row.get(i+1, 0)
            row.append(count)
        postprocessed_rows.append((name1, name2, row))

    graph_data = ''
    for name1, name2, row in postprocessed_rows:
        graph_data += (',{}-{}'.format(name1, name2))
    graph_data += '\\n'
    
    for i in range(max_count):
        graph_data += str(i+1)
        for name1, name2, row in postprocessed_rows:
            graph_data += ',{}'.format(row[i])
        graph_data += '\\n'

    return render(
        request,
        'the_redhuman_is/reports/main_workers/workers_lifetime.html',
        {
            'days_count': (last_day - first_day).days + 1,
            'filter_form': DaysIntervalForm(
                initial={
                    'first_day': first_day,
                    'last_day': last_day
                }
            ),
            'total_workers_count': workers_overall.count(),
            'graph_data': graph_data
        }
    )
