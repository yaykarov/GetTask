# -*- coding: utf-8 -*-

import datetime

from django.db.models import Q
from django.http import HttpResponse
from django.http import JsonResponse
from django.utils import timezone

import applicants
import finance

from the_redhuman_is import models

from the_redhuman_is.auth import staff_account_required


def _special(worker):
    return str(worker) in [
        'Абрамов Евгений Анатольевич',
        'Аляутдинов Рустям Равилевич',
        'Белоглазов Константин Андреевич',
        'Бухвостов Геннадий Юрьевич',
        'Ерышев Денис Михайлович',
        'Иванкович Алексей Владимирович',
        'Карюкин Александр Николаевич',
        'Клодченко Юрий Евгеньевич',
        'Кулешов Анатолий Анатольевич',
        'Кучишкин Владимир Витальевич',
        'Пенчик Александр Иванович',
        'Подлужный Дмитрий Яковлевич',
        'Рахманов Эльдар Иззетович',
        'Татур Олег Эдуардович',
        'Умеров Тимур Радионович',
        'Шестернев Максим Вячеславович',
    ]

def _value(worker):
    WORKERS = {
        'Абдразяков Альберт Кадирович': 1800,
        'Алексеев Станислав Викторович': 1000,
        'Амелюшкин Алексей Евгеньевич': 3000,
        'Беляев Евгений Николаевич': 1800,
        'Гончаров Денис Леонидович': 3000,
        'Зайцев Андрей Дмитриевич': 2400,
        'Захарьин Александр Владимирович': 3000,
        'Калашников Сергей Анатольевич': 3000,
        'Калуцкий Александр Олегович': 2400,
        'Курзин Геннадий Павлович': 3000,
        'Малинин Виталий Сергеевич': 3000,
        'Медведев Антон Сергеевич': 3000,
        'Миросенко Александр Юрьевич': 1400,
        'Михайлечко Евгений Владимирович': 2000,
        'Растегаев Алексей Анатольевич': 3000,
        'Хохлов Александр Александрович': 3000,
        'Чернов Артем Владимирович': 3000,
        'Швагурцев Игорь Вячеславович': 2400,
        'Шишкин Николай Иванович': 2200,
        'Яковенко Александр Юрьевич': 2200
    }
    return WORKERS.get(str(worker))


@staff_account_required
def paysheet_details_for_worker(request):
    worker = models.Worker.objects.get(
        pk=request.GET['worker_pk']
    )
    paysheet_entries = models.Paysheet_v2Entry.objects.filter(
        worker=worker
    )
    result = {}
    for entry in paysheet_entries:
        result[str(entry)] = []
        operations = models.Paysheet_v2EntryOperation.objects.filter(
            entry=entry
        )
        for op in operations:
            result[str(entry)].append(str(op))

    return JsonResponse(result)


@staff_account_required
def fix_missed_calls(request):
    initial_status = applicants.models.StatusInitial.objects.get().status
    apps = applicants.models.active_applicants().filter(
        author=None,
        worker_link__isnull=True,
        status=initial_status
    )
    for app in apps:
        same = applicants.models.active_applicants().filter(
            phone=app.phone
        )
        if same.count() > 1:
            app.active = False
            app.save()

    apps = applicants.models.active_applicants().filter(
        author=None
    )
    result = {}
    for app in apps:
        phone = app.phone
        if phone not in result:
            result[phone] = []
        result[phone].append(str(app))
    duplicates = {}
    for key, value in result.items():
        if len(value) > 1:
            duplicates[key] = value
    duplicates['000'] = len(duplicates)
    return JsonResponse(duplicates)


@staff_account_required
def fix_prepayment_date(request):
    for prepayment in models.Prepayment.objects.all():
        for item in prepayment.workers.all():
            if item.operation:
                item.operation.timepoint = prepayment.last_day
                item.operation.save()

    return HttpResponse('ok')


@staff_account_required
def fix_future_operation(request):
    deadline = timezone.now() + datetime.timedelta(days=1)
    operations = finance.models.Operation.objects.filter(
        timepoint__gte=deadline
    )
    for o in operations:
        o.timepoint = o.timepoint.replace(year=2018)
        o.save()
    return JsonResponse([str(o.timepoint) for o in operations], safe=False)


@staff_account_required
def block_paysheet_operations(request):
    operations = finance.models.Operation.objects.filter(
        is_closed=False
    ).filter(
        Q(paysheet_entry_operation__isnull=False) |
        Q(paysheet_v2_operation__isnull=False) |
        Q(workerprepayment__isnull=False)
    )

    result = [str(o) for o in operations]

    operations.update(
        is_closed=True
    )

    return JsonResponse(result, safe=False)
