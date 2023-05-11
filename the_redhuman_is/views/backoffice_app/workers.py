from decimal import Decimal
from typing import Optional

import rest_framework_filters as filters

from django.contrib.contenttypes.models import ContentType
from django.db.models import Q

from django.http import JsonResponse
from django_filters import DateFilter
from rest_framework.exceptions import ValidationError
from rest_framework.fields import (
    BooleanField,
    DateField,
    IntegerField,
)
from rest_framework.serializers import Serializer

from the_redhuman_is.models.comment import Comment
from the_redhuman_is.models.worker import (
    PlannedContact,
    Worker,
    WorkerRating,
    WorkerTag,
)
from the_redhuman_is import services
from the_redhuman_is.services.delivery.utils import ObjectNotFoundError
from the_redhuman_is.views.backoffice_app.auth import bo_api
from the_redhuman_is.views.utils import ConflictError
from utils.filter import (
    ChoiceInFilter,
    ChoiceInConvertFilter,
    CompactChoiceFilter,
    FilterSet,
)
from utils.functools import merge_dicts
from utils.phone import format_phone
from utils.serializers import ChoiceReprField


_AVAILABILITY = {
    WorkerRating.AVAILABLE: 'available',
    WorkerRating.NO_ANSWER: 'no_answer',
    WorkerRating.NOT_AVAILABLE: 'not_available',
    WorkerRating.UNKNOWN: 'unknown'
}

_READINESS = {
    WorkerRating.TOMORROW: 'tomorrow',
    WorkerRating.ANOTHER_DAY: 'another_day',
    WorkerRating.NOT_READY: 'not_ready',
    WorkerRating.UNKNOWN: 'unknown',
}


class WorkerFilter(FilterSet):
    class Meta:
        model = Worker
        fields = []
    zone = CompactChoiceFilter(field_name='workerzone__zone')
    first_day = filters.DateFilter(field_name='last_active_day', lookup_expr='gte')
    status_code = ChoiceInFilter(
        field_name='status_code',
        choices=Worker.TURNOUT_STATUS_CHOICES
    )
    is_online_tomorrow = filters.BooleanFilter()
    planned_contact_day = DateFilter(method='filter_by_planned_contact_day')
    availability = ChoiceInConvertFilter(
        field_name='workerrating__availability',
        choices={v: k for k, v in _AVAILABILITY.items()},
    )
    readiness = ChoiceInConvertFilter(
        field_name='workerrating__readiness',
        choices={v: k for k, v in _READINESS.items()},
    )
    last_call_date = DateFilter(method='filter_by_last_call_date')

    @staticmethod
    def filter_by_planned_contact_day(queryset, name, value):
        return queryset.filter(
            Q(planned_contact_day__isnull=True) |
            Q(planned_contact_day__lte=value)
        )

    @staticmethod
    def filter_by_last_call_date(queryset, name, value):
        return queryset.filter(
            Q(workerrating__last_call__isnull=True) |
            Q(workerrating__last_call__date__lte=value)
        )


def get_worker_queryset(all_comments=False, with_selfie=False):
    worker_qs = Worker.objects.all(
    ).filter_mobile(
    ).with_last_turnout_date(
    ).with_turnout_status_code(
    ).with_contract_status(
    ).with_unconfirmed_count(
    ).with_is_online_tomorrow(
    ).with_last_active_day(
    ).with_planned_contact_day(
    ).with_registration_ok(
    ).with_talk_bank_bind_status(
    )
    worker_fields = [
        'id',
        'last_name',
        'name',
        'patronymic',
        'input_date',
        'citizenship_id',
        'citizenship__name',
        'tel_number',
        'status_code',
        'contract_status',
        'last_turnout_date',
        'workerzone__zone_id',
        'workerzone__zone__name',
        'workerzone__zone__code',
        'unconfirmed_count',
        'workertag__tag',
        'is_online_tomorrow',
        'planned_contact_day',
        'workerrating__last_call__date',
        'workerrating__is_benevolent',
        'workerrating__reliability',
        'workerrating__availability',
        'workerrating__readiness',
        'registration_ok',
        'talk_bank_bind_status',
    ]

    if all_comments:
        worker_qs = worker_qs.with_comments()
        worker_fields.append('comments')
    else:
        worker_qs = worker_qs.with_last_comment()
        worker_fields.append('last_comment')

    if with_selfie:
        worker_qs = worker_qs.with_selfie_if_loader()
        worker_fields.append('selfie')

    return worker_qs.values(
        *worker_fields
    )


def _quantize(value: Optional[Decimal], precision: Decimal = Decimal('1.0')):
    if value is None:
        return None
    return value.quantize(precision)


def serialize_worker_in_place(worker, balance):
    if worker['workerzone__zone_id'] is not None:
        worker['zone'] = {
            'id': worker.pop('workerzone__zone_id'),
            'name': worker.pop('workerzone__zone__name'),
            'code': worker.pop('workerzone__zone__code'),
        }
    else:
        del worker['workerzone__zone_id']
        del worker['workerzone__zone__name']
        del worker['workerzone__zone__code']
        worker['zone'] = None

    worker['citizenship'] = {
        'id': worker.pop('citizenship_id'),
        'name': worker.pop('citizenship__name'),
    }

    worker['last_call_date'] = worker.pop('workerrating__last_call__date')
    worker['is_benevolent'] = worker.pop('workerrating__is_benevolent')
    worker['reliability'] = _quantize(worker.pop('workerrating__reliability'))
    worker['availability'] = _AVAILABILITY[worker.pop('workerrating__availability')]
    worker['readiness'] = _READINESS[worker.pop('workerrating__readiness')]
    worker['balance'] = balance
    worker['tag'] = worker.pop('workertag__tag')
    worker['tel_number'] = format_phone(worker['tel_number'])


@bo_api(['GET'])
def worker_list(request):
    worker_qs = get_worker_queryset()
    if 'search_text' in request.GET:
        workers = list(
            worker_qs.filter_by_name_or_phone(
                request.GET['search_text']
            )
        )
    else:
        workers = list(WorkerFilter(request.GET, queryset=worker_qs).qs)

    worker_ids = [w['id'] for w in workers]
    accounts = services.worker.get_accounts_for_workers(worker_ids)
    balances = {
        pk: -account.turnover_saldo()
        for pk, account in accounts.items()
    }
    for worker in workers:
        serialize_worker_in_place(worker, balances[worker['id']])

    return JsonResponse(
        {
            'results': workers
        }
    )


@bo_api(['GET'])
def worker_detail(request, pk):
    try:
        worker = get_worker_queryset(
            all_comments=True,
            with_selfie=True,
        ).get(
            pk=pk
        )
    except Worker.DoesNotExist:
        raise ObjectNotFoundError(f'Работник {pk} не найден.')

    accounts = services.worker.get_accounts_for_workers([pk])
    balance = -accounts[pk].turnover_saldo()
    serialize_worker_in_place(worker, balance)

    return JsonResponse(worker)


@bo_api(['POST'])
def set_tag(request, pk):
    worker_tag, created = WorkerTag.objects.update_or_create(
        worker_id=pk,
        defaults={
            'author': request.user,
            'tag': request.data['tag']
        }
    )
    return JsonResponse({
        'tag': worker_tag.tag
    })


@bo_api(['POST'])
def add_comment(request, pk):
    Worker.objects.get(pk=pk)
    comment = Comment.objects.create(
        text=request.data['text'],
        author=request.user,
        object_id=pk,
        content_type=ContentType.objects.get_for_model(Worker),
    )
    return JsonResponse({
        'text': comment.text,
        'timestamp': comment.timestamp,
        'author': {
            'id': request.user.pk,
            'name': request.user.first_name,
        }
    })


class PlannedContactSerializer(Serializer):
    worker = IntegerField(source='worker_id', min_value=1)
    date = DateField(input_formats=['%d.%m.%Y'])


@bo_api(['POST'])
def set_planned_contact_day(request):
    serializer = PlannedContactSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    planned_contact = PlannedContact.objects.create(
        worker_id=data['worker_id'],
        date=data['date'],
        author=request.user
    )
    return JsonResponse(
        {
            'date': planned_contact.date,
            'timestamp': planned_contact.timestamp,
            'author': {
                'id': request.user.pk,
                'name': request.user.first_name,
            }
        }
    )


def _get_worker_rating_queryset():
    return WorkerRating.objects.values(
        'worker',
        'last_call__date',
        'is_benevolent',
        'reliability',
        'availability',
        'readiness',
    )


def get_worker_rating_detail(worker_id):
    rating = _get_worker_rating_queryset(
    ).get(
        worker_id=worker_id
    )
    rating['reliability'] = _quantize(rating['reliability'])
    rating['availability'] = _AVAILABILITY[rating['availability']]
    rating['readiness'] = _READINESS[rating['readiness']]
    rating['last_call_date'] = rating.pop('last_call__date')
    return rating


class WorkerUpdateParamsSerializer(Serializer):
    worker = IntegerField(min_value=1, source='worker_id')


class WorkerUpdateFieldsSerializer(Serializer):
    is_benevolent = BooleanField()
    availability = ChoiceReprField(choices=list(_AVAILABILITY.items()))
    readiness = ChoiceReprField(choices=list(_READINESS.items()))

    def validate(self, attrs):
        n_fields = len(attrs.keys())
        if n_fields > 1:
            raise ValidationError('Одновременно можно обновлять только одно поле.')
        elif n_fields == 0:
            raise ValidationError(
                'Отсутствует обновляемое поле. Доступные для редактирования поля: '
                'is_benevolent, availability, readiness.'
            )
        return attrs


@bo_api(['POST'])
def update_worker_rating(request):
    ser_params = WorkerUpdateParamsSerializer(data=request.data)
    ser_params.is_valid()
    ser_field = WorkerUpdateFieldsSerializer(data=request.data, partial=True)
    ser_field.is_valid()
    if ser_params.errors or ser_field.errors:
        raise ValidationError(merge_dicts(ser_params.errors, ser_field.errors))
    worker_id = ser_params.validated_data['worker_id']
    field = next(iter(ser_field.validated_data.keys()))
    value = next(iter(ser_field.validated_data.values()))

    services.worker.update_worker_rating(worker_id, field, value)

    return JsonResponse(
        get_worker_rating_detail(worker_id)
    )


class WorkerSerializer(Serializer):
    worker = IntegerField(min_value=1, source='worker_id')


class WorkerOnlineSerializer(WorkerSerializer):
    is_online_tomorrow = BooleanField(source='is_online')


@bo_api(['POST'])
def update_online_status(request):
    serializer = WorkerOnlineSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    try:
        is_online = services.worker.update_online_status(
            author=request.user,
            **serializer.validated_data,
        )
    except services.worker.NoWorkPermit:
        raise ConflictError(
            detail='Работник не может работать завтра (забанен или просрочена МК).'
        )

    return JsonResponse({
        'is_online_tomorrow': is_online
    })


@bo_api(['POST'])
def bind_to_talk_bank(request):
    serializer = WorkerSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    worker_id = serializer.validated_data['worker_id']

    services.paysheet.talk_bank.bind_worker_sync(worker_id)

    worker = Worker.objects.with_talk_bank_bind_status().get(pk=worker_id)

    return JsonResponse(worker.talk_bank_bind_status)
