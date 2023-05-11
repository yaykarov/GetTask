import collections
import itertools
import operator

from datetime import timedelta

from django.db.models import (
    Count,
    Exists,
    IntegerField,
    Max,
    OuterRef,
    Subquery,
)
from django.http import JsonResponse

from rest_framework.fields import DateField
from rest_framework.serializers import Serializer

from the_redhuman_is.async_utils.telephony import get_call_history

from the_redhuman_is.models.delivery import (
    DeliveryRequest,
    LocationZoneGroup,
    OnlineStatusMark,
    RequestWorker,
    RequestWorkerTurnout,
    ZoneGroup,
)
from the_redhuman_is.models.worker import Worker

from the_redhuman_is.views.backoffice_app.analytics.auth import analytics_api
from the_redhuman_is.views.backoffice_app.delivery.main_workplace import (
    worker_driver_calls_history
)

from utils import (
    extract_phones,
    days_from_interval,
)


def _call_format_in_place(call):
    del call['users']
    del call['dispatchers']


class DateRangeSerializer(Serializer):
    first_day = DateField(input_formats=['%d.%m.%Y'])
    last_day = DateField(input_formats=['%d.%m.%Y'])


@analytics_api(['GET'])
def list_calls(request):
    serializer = DateRangeSerializer(data=request.GET)
    serializer.is_valid(raise_exception=True)
    history = worker_driver_calls_history(**serializer.validated_data)
    for item in history:
        _call_format_in_place(item)
    return JsonResponse({
        'calls': history,
    })


def _calls_turnout_summary(first_day, last_day):
    workers_qs = Worker.objects.filter(
        mobileappworker__isnull=False,
        tel_number__isnull=False,
    ).values_list(
        'pk',
        'tel_number',
        'workerzone__zone_id',
        'workeruser__user_id',
    ).order_by(
        'pk'
    )

    phone_to_worker = {
        phone: (worker, zone)
        for worker, phone, zone, _ in workers_qs
    }
    user_to_worker = {
        user: (worker, zone)
        for worker, _, zone, user in workers_qs
    }
    worker_to_zone = {
        worker: zone
        for worker, _, zone, _ in workers_qs
    }
    zones_qs = ZoneGroup.objects.order_by(
        'pk'
    ).values_list(
        'pk',
        'name',
        'code',
        'weekendrest'
    )
    zones = {
        pk: {'name': name, 'code': code, 'rest': bool(rest)}
        for pk, name, code, rest in zones_qs
    }
    zones[None] = None
    weekend_rest_zones = {pk for pk, _, _, rest in zones_qs if rest is not None}

    # calls
    all_calls = collections.defaultdict(set)
    successful_calls = collections.defaultdict(set)

    requests = DeliveryRequest.objects.filter(
        date__range=(
            first_day - timedelta(days=1),
            last_day - timedelta(days=1)
        ),
        driver_phones__isnull=False
    ).annotate(
        zone=Subquery(
            LocationZoneGroup.objects.filter(
                location=OuterRef('location')
            ).values(
                'zone_group'
            ),
            output_field=IntegerField()
        )
    ).order_by(
        'date',
        'zone',
    ).values(
        'date',
        'zone',
        'driver_phones',
    )
    driver_phones = {
        key: {
            phone for request in group for phone in extract_phones(request['driver_phones'])
        }
        for key, group in itertools.groupby(
            requests,
            key=operator.itemgetter('date', 'zone')
        )
    }

    history = get_call_history(
        first_day - timedelta(days=1),
        last_day - timedelta(days=1)
    )

    for call in filter(
        lambda item: item['call_type'][:3] == 'out',
        history
    ):
        call_date = call['start_time'].date()
        try:
            phone = call['phones'][0]
            weekday = call_date.isoweekday()
            worker, zone = phone_to_worker[phone]
            try:
                if phone in driver_phones[call_date, zone]:
                    continue
            except KeyError:
                pass
            if not 5 != weekday != 6 and zone in weekend_rest_zones:
                call_date += timedelta(days=7 - weekday)
            all_calls[call_date, zone].add(worker)
            if call['successful']:
                successful_calls[call_date, zone].add(worker)
        except (IndexError, KeyError):
            pass

    # online
    def _get_online_marks_qs(online_only=False):
        online_marks_qs = OnlineStatusMark.objects.filter(
            timestamp__date__range=(
                first_day - timedelta(days=1),
                last_day - timedelta(days=1)
            ),
        )
        if online_only:
            online_marks_qs = online_marks_qs.filter(
                online=True
            )
        return online_marks_qs.values(
            'timestamp__date',
            'user',
        ).annotate(
            Max('timestamp')
        ).values_list(
            'timestamp__date',
            'user',
            'timestamp__max',
        )

    have_marks = {
        (signup_date, user): max_timestamp
        for signup_date, user, max_timestamp in _get_online_marks_qs()
    }

    online = collections.defaultdict(set)
    for signup_date, user, max_timestamp in _get_online_marks_qs(online_only=True):
        if max_timestamp == have_marks[signup_date, user]:
            try:
                worker, zone = user_to_worker[user]
                online[signup_date, zone].add(worker)
            except KeyError:
                pass

    # turnouts
    turnouts_qs = RequestWorker.objects.filter(
        requestworkerturnout__isnull=False,
        request__date__range=(first_day, last_day)
    ).values_list(
        'request__date',
        'worker'
    ).order_by(
        'request__date',
        'worker',
    ).distinct()

    turnouts = collections.defaultdict(set)
    for request_date, worker in turnouts_qs:
        zone = worker_to_zone[worker]
        turnouts[request_date, zone].add(worker)

    # no turnouts ever
    no_turnout_worker_qs = Worker.objects.order_by(
    ).annotate(
        has_turnout=Exists(
            RequestWorkerTurnout.objects.filter(
                requestworker__worker=OuterRef('pk')
            )
        )
    ).filter(
        mobileappworker__isnull=False,
        has_turnout=False,
    )
    no_turnout_diff_counts = {
        (input_date, zone): count
        for input_date, zone, count in no_turnout_worker_qs.filter(
            input_date__date__gt=first_day,
            input_date__date__lte=last_day,
        ).values(
            'input_date__date',
            'workerzone__zone_id',
        ).annotate(
            Count('pk')
        ).values_list(
            'input_date__date',
            'workerzone__zone_id',
            'pk__count',
        )
    }
    no_turnout_diff_counts.update({
        (first_day, zone): count
        for zone, count in no_turnout_worker_qs.filter(
            input_date__date__lte=first_day
        ).values(
            'workerzone__zone_id',
        ).annotate(
            Count('pk')
        ).values_list(
            'workerzone__zone_id',
            'pk__count',
        )
    })

    days_axis = days_from_interval(first_day, last_day)
    no_turnout_counts = {}
    for day, zone in itertools.product(days_axis, zones.keys()):
        no_turnout_counts[day, zone] = (
            no_turnout_counts.get((day - timedelta(days=1), zone), 0) +
            no_turnout_diff_counts.get((day, zone), 0)
        )

    def _get_element(today, zone):
        yesterday = today - timedelta(days=1)
        return {
            'date': today,
            'zone': zones[zone],
            'call_attempt': len(all_calls[yesterday, zone]),
            'call': len(successful_calls[yesterday, zone]),
            'call_online': len(successful_calls[yesterday, zone] & online[yesterday, zone]),
            'call_turnout': len(successful_calls[yesterday, zone] & turnouts[today, zone]),
            'no_call_online': len(online[yesterday, zone] - all_calls[yesterday, zone]),
            'no_online_turnout': len(turnouts[today, zone] - online[yesterday, zone]),
            'no_call_online_turnout': len(
                online[yesterday, zone] &
                turnouts[today, zone] -
                all_calls[yesterday, zone]
            ),
            'no_turnouts': no_turnout_counts[today, zone],

        }

    return list(itertools.starmap(_get_element, itertools.product(days_axis, zones.keys())))


@analytics_api(['GET'])
def calls_turnout_summary(request):
    serializer = DateRangeSerializer(data=request.GET)
    serializer.is_valid(raise_exception=True)

    return JsonResponse({
        'calls_turnouts': _calls_turnout_summary(**serializer.validated_data)
    })
