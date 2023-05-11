# -*- coding: utf-8 -*-

from the_redhuman_is import models


def find_worker(customer_pk, full_name):
    from the_redhuman_is.views.fine_utils import _find_worker

    worker, _ = _find_worker(
        customer_pk,
        full_name
    )

    if not worker:
        alias = models.K2KAlias.objects.filter(alias=full_name)
        if alias.exists():
            worker = alias.get().worker

    return worker


def get_gathered_turnouts(first_day, last_day, location_pks):
    result = {}

    turnouts = models.WorkerTurnout.objects.filter(
        timesheet__sheet_date__range=(first_day, last_day),
        timesheet__cust_location__pk__in=location_pks,
        hours_worked__gt=0
    ).select_related(
        'worker',
        'timesheet'
    )

    for turnout in turnouts:
        day = turnout.timesheet.sheet_date
        worker = turnout.worker
        hours = turnout.hours_worked
        is_night = turnout.timesheet.sheet_turn == 'Ночь'
        service = turnout.turnoutservice.customer_service.service

        if day not in result:
            result[day] = {}

        if worker not in result[day]:
            result[day][worker] = []

        result[day][worker].append(
            (
                service.pk,
                hours,
                is_night
            )
        )

    return result


def find_difference(file_turnouts, location_pks, is_k2k=False):
    days = sorted(file_turnouts.keys())
    first_day = days[0]
    last_day = days[-1]

    gathered_turnouts = get_gathered_turnouts(
        first_day,
        last_day,
        location_pks
    )

    def _have_night_turnout(turnouts):
        for service_pk, hours, is_night in turnouts:
            if is_night:
                return True
        return False

    def _have_day_turnout(turnouts):
        for service_pk, hours, is_night in turnouts:
            if not is_night:
                return True
        return False

    def _is_full_day(data):
        for worker, turnouts in data.items():
            if _have_day_turnout(turnouts):
                return True
        return False

    def _transform_turnouts(turnouts, only_night=False, only_day=False):
        data = {}
        for service_pk, hours, is_night in turnouts:
            if only_day and is_night:
                continue
            if only_night and not is_night:
                continue
            if service_pk not in data:
                data[service_pk] = 0
            data[service_pk] += hours
        return data

    _services_cache = {}
    def _service(service_pk):
        if service_pk not in _services_cache:
            _services_cache[service_pk] = models.Service.objects.get(pk=service_pk)
        return _services_cache[service_pk]

    itella_missed_days = []
    alpha_missed_days = []

    different_hours = []

    itella_missed_turnouts = []
    alpha_missed_turnouts = []

    def _report_different_hours(day, worker, service_pk, file_hours, gathered_hours):
        different_hours.append(
            (
                day,
                worker,
                _service(service_pk),
                file_hours,
                gathered_hours
            )
        )

    for day, workers in file_turnouts.items():
        if day in gathered_turnouts:

            is_fake_first_day = (
                is_k2k and
                day == first_day and
                not _is_full_day(file_turnouts[first_day])
            )

            for worker, turnouts in workers.items():
                gathered_worker_turnouts = gathered_turnouts[day].get(worker)
                if gathered_worker_turnouts:
                    if day == last_day:
                        gathered_data_night = _transform_turnouts(
                            gathered_worker_turnouts,
                            only_night=True
                        )
                        gathered_data_day = _transform_turnouts(
                            gathered_worker_turnouts,
                            only_day=True
                        )
                        for service_pk, hours, is_night in turnouts:
                            if service_pk in gathered_data_night:
                                # В последний день отчета Ителлы попадает только первая часть
                                # ночной смены. Поэтому если у нас есть ночная смена за эту дату
                                # то сравниваем часы из файла с частью этой смены.
                                is_error = (hours + 8) != gathered_data_night[service_pk]
                            else:
                                gathered_hours = gathered_data_day.get(service_pk, 0)
                                is_error = (hours != gathered_hours)

                            if is_error:
                                _report_different_hours(
                                    day,
                                    worker,
                                    service_pk,
                                    hours,
                                    gathered_hours
                                )
                    else:
                        file_data = _transform_turnouts(turnouts)
                        gathered_data = _transform_turnouts(
                            gathered_worker_turnouts,
                            only_night=is_fake_first_day
                        )

                        for service_pk, hours in file_data.items():
                            gathered_hours = gathered_data.get(service_pk, 0)
                            if is_fake_first_day:
                                # В этом случае у Ителлы в первом дне интервала -
                                # только "ночные" части смен, предполагаем, что дневная
                                # часть составляет 3 часа
                                is_error = (hours + 3) != gathered_hours
                            else:
                                is_error = (hours != gathered_hours)

                            if is_error:
                                _report_different_hours(
                                    day,
                                    worker,
                                    service_pk,
                                    hours,
                                    gathered_hours
                                )

                        for service_pk, hours in gathered_data.items():
                            if service_pk not in file_data:
                                _report_different_hours(
                                    day,
                                    worker,
                                    service_pk,
                                    0,
                                    hours,
                                )
                else:
                    alpha_missed_turnouts.append(
                        (
                            day,
                            worker
                        )
                    )
        else:
            alpha_missed_days.append(day)

    for day, workers in gathered_turnouts.items():
        if day in file_turnouts:

            is_fake_first_day = (
                is_k2k and
                day == first_day and
                not _is_full_day(file_turnouts[first_day])
            )

            for worker, turnouts in workers.items():
                if is_fake_first_day:
                    if not _have_night_turnout(turnouts):
                        continue

                file_worker_turnouts = file_turnouts[day].get(worker)
                if not file_worker_turnouts:
                    itella_missed_turnouts.append(
                        (
                            day,
                            worker
                        )
                    )
        else:
            itella_missed_days.append(day)

    itella_missed_days.sort()
    alpha_missed_days.sort()

    different_hours.sort(key=lambda d: d[0])

    itella_missed_turnouts.sort(key=lambda d: d[0])
    alpha_missed_turnouts.sort(key=lambda d: d[0])

    return (
        itella_missed_days,
        itella_missed_turnouts,
        alpha_missed_days,
        alpha_missed_turnouts,
        different_hours
    )
