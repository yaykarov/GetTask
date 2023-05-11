from dal_select2.views import Select2QuerySetView
from django.http import JsonResponse
from django.utils import timezone
from rest_framework.fields import IntegerField, DateField
from rest_framework.serializers import Serializer
from rest_framework.views import APIView

from the_redhuman_is.models import Worker
from the_redhuman_is.services.delivery import retrieve
from the_redhuman_is.services.delivery.utils import ObjectNotFoundError
from the_redhuman_is.views import delivery
from the_redhuman_is.views.backoffice_app.auth import bo_api
from utils import date_time


class MapRequestAutocomplete(Select2QuerySetView, APIView):
    def get_queryset(self):
        zone_id = self.forwarded.get('zone')

        delivery_requests, _, _ = retrieve.get_requests_on_map_querysets(
            timezone.localdate(),
            self.request.user,
            zone_id,
        )

        if self.q:
            delivery_requests = delivery_requests.filter_by_text(self.q)

        return delivery_requests.order_by(
            'pk'
        ).values(
            'pk',
            'driver_name',
        )

    def get_result_value(self, result):
        return str(result['pk'])

    def get_result_label(self, result):
        return f"{result['pk']} {result['driver_name']}"


class MapWorkerAutocomplete(Select2QuerySetView, APIView):
    def get_queryset(self):
        zone_id = self.forwarded.get('zone')

        _, workers, _ = retrieve.get_requests_on_map_querysets(
            timezone.localdate(),
            self.request.user,
            zone_id,
        )

        if self.q:
            workers = workers.filter_by_text(self.q)

        return workers.order_by(
            'full_name'
        ).values(
            'pk',
            'full_name',
        )

    def get_result_value(self, result):
        return str(result['pk'])

    def get_result_label(self, result):
        return result['full_name']


class ZoneSerializer(Serializer):
    zone = IntegerField(min_value=1, source='zone_id', allow_null=True, default=None)


@bo_api(['GET'])
def requests_on_map(request):
    serializer = ZoneSerializer(data=request.GET)
    serializer.is_valid(raise_exception=True)
    return JsonResponse(
        retrieve.get_requests_on_map(
            user=request.user,
            date=timezone.localdate(),
            **serializer.validated_data
        )
    )


class WorkerMapDataSerializer(Serializer):
    worker = IntegerField(min_value=1, source='worker_id')
    date = DateField(input_formats=[date_time.DATE_FORMAT])


@bo_api(['GET'])
def worker_map_data(request):
    serializer = WorkerMapDataSerializer(data=request.GET)
    serializer.is_valid(raise_exception=True)
    worker_id = serializer.validated_data['worker_id']
    try:
        worker = Worker.objects.get(pk=worker_id)
    except Worker.DoesNotExist:
        raise ObjectNotFoundError(f'Работник {worker_id} не найден.')
    return JsonResponse(
        delivery.worker_on_map_link(worker, serializer.validated_data['date'])
    )
