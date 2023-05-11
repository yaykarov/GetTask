from typing import cast

from django.http import (
    HttpResponse,
    JsonResponse,
)
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.fields import (
    BooleanField,
    CharField,
    ImageField,
    IntegerField,
)

from rest_framework.serializers import Serializer

from the_redhuman_is.services.delivery import (
    actions,
    retrieve,
)
from the_redhuman_is.services.delivery.actions import (
    SuspiciousLocation,
    WorkerPermissionDenied,
)
from the_redhuman_is.services.poll import try_register_answer
from the_redhuman_is.views.delivery import mobile_api


class RequestSerializer(Serializer):
    request = IntegerField(min_value=0, source='request_id')


@mobile_api
def add_confirm_request_worker(request):
    worker_id = cast(int, request.user.workeruser.worker_id)
    serializer = RequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    try:
        actions.add_request_worker(
            worker_id=worker_id,
            user=request.user,
            **serializer.validated_data,
        )
    except WorkerPermissionDenied as ex:
        return JsonResponse(
            {'error': ex.args[0]},
            status_code=status.HTTP_403_FORBIDDEN
        )
    actions.confirm_request_worker(
        worker_id=worker_id,
        user=request.user,
        **serializer.validated_data,
    )
    request_id = serializer.validated_data['request_id']
    return JsonResponse(
        retrieve.get_delivery_request_detail_for_worker(
            request_id,
            worker_id,
            request.location,
        )
    )


@mobile_api
def confirm_request_worker(request):
    worker_id = cast(int, request.user.workeruser.worker_id)
    serializer = RequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    actions.confirm_request_worker(
        worker_id=worker_id,
        user=request.user,
        **serializer.validated_data
    )
    request_id = serializer.validated_data['request_id']
    return JsonResponse(
        retrieve.get_delivery_request_detail_for_worker(
            request_id,
            worker_id,
            request.location,
        )
    )


class ItemStartFinishSerializer(RequestSerializer):
    item = IntegerField(min_value=0, source='item_id')
    image = ImageField()


class ItemStartSerializer(ItemStartFinishSerializer):
    force_commit = BooleanField(default=True)


@mobile_api
def item_worker_start(request):
    worker_id = cast(int, request.user.workeruser.worker_id)
    serializer = ItemStartSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    try:
        actions.log_itemworker_start(
            user=request.user,
            worker_id=worker_id,
            location=request.location,
            **serializer.validated_data
        )
    except SuspiciousLocation as exc:
        raise ValidationError(
            detail={
                'error': 'suspicious_location',
                'distance': exc.args[0]
            }
        )
    request_id = serializer.validated_data['request_id']
    return JsonResponse(
        retrieve.get_delivery_request_detail_for_worker(
            request_id,
            worker_id,
            request.location,
        )
    )


@mobile_api
def item_worker_finish(request):
    worker_id = cast(int, request.user.workeruser.worker_id)
    serializer = ItemStartFinishSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    actions.log_itemworker_finish(
        user=request.user,
        worker_id=worker_id,
        location=request.location,
        **serializer.validated_data
    )
    request_id = serializer.validated_data['request_id']
    return JsonResponse(
        retrieve.get_delivery_request_detail_for_worker(
            request_id,
            worker_id,
            request.location,
        )
    )


@mobile_api
def worker_requests(request):
    worker_id = cast(int, request.user.workeruser.worker_id)
    return JsonResponse(
        retrieve.get_delivery_request_list_for_worker(
            worker_id,
            request.location,
        )
    )


@mobile_api
def worker_unpaid_requests(request):
    worker_id = cast(int, request.user.workeruser.worker_id)
    return JsonResponse(
        retrieve.get_unpaid_requests_for_worker(worker_id)
    )


class PollAnswerSerializer(Serializer):
    question_code = CharField()
    answer = CharField()


@mobile_api
def worker_answer_poll(request):
    worker_id = cast(int, request.user.workeruser.worker_id)
    serializer = PollAnswerSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    question_code = serializer.validated_data['question_code']
    answer = serializer.validated_data['answer']

    try_register_answer(worker_id, question_code, answer)

    return HttpResponse('')
