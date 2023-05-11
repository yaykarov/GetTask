import rest_framework_filters as filters
from django.contrib.postgres.aggregates import ArrayAgg
from django.contrib.postgres.fields import ArrayField
from django.db.models import (
    DecimalField,
    Exists,
    JSONField,
    OuterRef,
    Subquery,
    Sum,
)
from django.db.models.functions import (
    Coalesce,
    JSONObject,
)
from django.http import JsonResponse

from the_redhuman_is.models.delivery import (
    DeliveryItem,
    DeliveryRequest,
    ItemWorker,
    LocationZoneGroup,
    RequestWorker,
    RequestWorkerTurnout,
)
from the_redhuman_is.models.models import CustomerLocation
from the_redhuman_is.views.backoffice_app.analytics.auth import analytics_api
from utils.filter import FilterSet
from utils.numbers import ZERO_OO


def _get_zone_annotation(outerref):
    return LocationZoneGroup.objects.filter(
        location=OuterRef(outerref)
    ).annotate(
        zone_fields=JSONObject(
            name='zone_group__name',
            code='zone_group__code',
        )
    ).order_by(
        'zone_group'
    ).values(
        'zone_fields'
    )[:1]


def _get_request_queryset():
    return DeliveryRequest.objects.all(
    ).annotate(
        workers=Coalesce(
            Subquery(
                RequestWorker.objects.with_full_name(
                ).annotate(
                    has_items=Exists(
                        ItemWorker.objects.filter(
                            requestworker=OuterRef('pk'),
                            itemworkerrejection__isnull=True,
                        )
                    ),
                ).filter(
                    request=OuterRef('pk'),
                    workerrejection__isnull=True,
                    has_items=True,
                ).annotate(
                    worker_fields=JSONObject(
                        id='worker_id',
                        full_name='full_name',
                    )
                ).values(
                    'request'
                ).annotate(
                    workers_list=ArrayAgg(
                        'worker_fields',
                        ordering=('worker_id',)
                    )
                ).values(
                    'workers_list'
                ),
                output_field=ArrayField(JSONField())
            ),
            []
        ),
        items=Coalesce(
            Subquery(
                DeliveryItem.objects.filter(
                    request=OuterRef('pk')
                ).annotate(
                    item_fields=JSONObject(
                        id='id',
                        code='code',
                        address='address',
                    )
                ).values(
                    'request'
                ).annotate(
                    items_list=ArrayAgg(
                        'item_fields',
                        ordering=('id',)
                    )
                ).values(
                    'items_list'
                ),
                output_field=ArrayField(JSONField())
            ),
            []
        ),
        zone=Subquery(
            _get_zone_annotation('location'),
            output_field=JSONField()
        )
    ).values(
        'pk',
        'date',
        'customer',
        'customer__cust_name',
        'driver_name',
        'status',
        'route',
        'workers',
        'items',
        'zone',
    )


class DeliveryRequestBaseFilter(FilterSet):
    first_day = filters.DateFilter(field_name='date', lookup_expr='gte', required=True)
    last_day = filters.DateFilter(field_name='date', lookup_expr='lte', required=True)

    class Meta:
        model = DeliveryRequest
        fields = []


def get_delivery_request_list(filter_args):
    requests = list(
        DeliveryRequestBaseFilter(
            filter_args,
            queryset=_get_request_queryset()
        ).qs
    )
    for request in requests:
        request['customer'] = {
            'id': request['customer'],
            'name': request.pop('customer__cust_name'),
        }

    return {
        'requests': requests
    }


@analytics_api(['GET'])
def list_requests(request):
    return JsonResponse(
        get_delivery_request_list(request.GET)
    )


class TurnoutFilter(FilterSet):
    first_day = filters.DateFilter(
        field_name='requestworker__request__date', lookup_expr='gte', required=True
    )
    last_day = filters.DateFilter(
        field_name='requestworker__request__date', lookup_expr='lte', required=True
    )

    class Meta:
        model = RequestWorkerTurnout
        fields = []


def get_hours_list(filter_args):
    return list(
        TurnoutFilter(
            filter_args,
            RequestWorkerTurnout.objects.filter(
                requestworker__request__status__in=DeliveryRequest.SUCCESS_STATUSES,
            )
        ).qs.values(
            'requestworker__request__location',
            'requestworker__request__date',
        ).annotate(
            hours_worked=Coalesce(
                Sum(
                    'workerturnout__hours_worked',
                    output_field=DecimalField()
                ),
                ZERO_OO,
            ),
        ).values(
            'requestworker__request__location',
            'requestworker__request__date',
            'hours_worked',
        ).order_by(
            'requestworker__request__date',
            'requestworker__request__customer',
            'requestworker__request__location',
        )
    )


@analytics_api(['GET'])
def hours_summary(request):
    hours = get_hours_list(request.GET)

    locations = {
        row['pk']: row
        for row in CustomerLocation.objects.filter(
            pk__in={row['requestworker__request__location'] for row in hours}
        ).annotate(
            zone=Subquery(
                _get_zone_annotation('pk'),
                output_field=JSONField()
            )
        ).values(
            'pk',
            'zone',
            'customer_id',
            'customer_id__cust_name',
        )
    }

    def _serialize_hours_row(row):
        location = locations[row['requestworker__request__location']]
        return {
            'zone': location['zone'],
            'date': row['requestworker__request__date'],
            'hours': row['hours_worked'],
            'customer': {
                'id': location['customer_id'],
                'name': location['customer_id__cust_name']
            }
        }

    return JsonResponse(
        {
            'hours_summary': [_serialize_hours_row(row) for row in hours]
        }
    )
