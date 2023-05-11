from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.http import HttpResponseNotFound
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import PermissionDenied

from rest_framework.fields import (
    BooleanField,
    CharField,
    DateField,
    DecimalField,
    IntegerField,
    TimeField,
)
from rest_framework.serializers import Serializer

import utils
from the_redhuman_is.models.models import CustomerLocation
from the_redhuman_is.models import turnout_calculators
from the_redhuman_is.services.delivery import (
    actions,
    retrieve,
    tariffs,
)
from the_redhuman_is.services.delivery.utils import (
    get_user_customer_location,
    normalize_driver_name,
)
from the_redhuman_is.views.customer_api.auth import customer_api
from the_redhuman_is.views.utils import (
    APIJsonResponse,
    content_response,
)
from utils.serializers import (
    GeopositionListField,
    PhoneListField,
)


class DeliveryItemCreateSerializer(Serializer):
    interval_begin = TimeField()
    interval_end = TimeField()
    code = CharField()
    mass = DecimalField(min_value=0, max_digits=10, decimal_places=3)
    volume = DecimalField(min_value=0, max_digits=10, decimal_places=3)
    max_size = DecimalField(min_value=0, max_digits=10, decimal_places=3, allow_null=True)
    place_count = IntegerField(min_value=0)
    shipment_type = CharField()
    address = CharField()
    has_elevator = BooleanField(allow_null=True)
    floor = IntegerField(allow_null=True)
    carrying_distance = IntegerField(allow_null=True)
    workers_required = IntegerField(min_value=1, default=1)


class DeliveryRequestCreateSerializer(Serializer):
    request = IntegerField(min_value=1, source='request_id', allow_null=True, default=None)
    location = IntegerField(min_value=1, source='location_id', allow_null=True, default=None)
    date = DateField(
        input_formats=[utils.date_time.DATE_FORMAT],
        validators=[MinValueValidator(retrieve.CUSTOMER_REQUEST_MIN_DATE)]
    )
    driver_name = CharField(allow_blank=True, default='')
    driver_phones = PhoneListField(allow_empty=True)
    items = DeliveryItemCreateSerializer(many=True, allow_empty=False)
    merge = BooleanField(default=True)

    def validate_driver_name(self, value):
        return normalize_driver_name(value)

    def validate_driver_phones(self, value):
        return sorted(value)

    def validate_date(self, value):
        if value < timezone.now().date():
            raise ValidationError('Нельзя создать заявку за прошедшую дату.')
        return value

    def validate_location(self, value):
        if value is None and 'customer' in self.context:
            locations = list(
                CustomerLocation.objects.filter(
                    customer_id=self.context['customer']
                ).values_list('pk', flat=True)[:2]
            )
            if len(locations) == 1:
                return locations[0]
        return value


@customer_api(['POST'])
def create_request(request):
    user_customer, _ = get_user_customer_location(request.user)
    serializer = DeliveryRequestCreateSerializer(
        data=request.data,
        context={'customer': user_customer}
    )
    serializer.is_valid(raise_exception=True)

    request_id = actions.create_delivery_request(
        user=request.user,
        customer_id=user_customer,
        notify_dispatchers=True,
        **serializer.validated_data
    ).pk
    return APIJsonResponse(
        retrieve.get_delivery_request_detail_for_customer(request_id, request.user, api=True),
        status=status.HTTP_201_CREATED
    )


@customer_api(['GET'])
def list_requests(request):
    requests = retrieve.get_delivery_request_list_for_customer_api(
        request.user,
        request.GET,
    )
    return APIJsonResponse({
        'results': requests
    })


class RequestDetailQuerySerializer(Serializer):
    pk = IntegerField(source='request_id', min_value=1)


@customer_api(['GET'])
def request_detail(request):
    serializer = RequestDetailQuerySerializer(data=request.GET)
    serializer.is_valid(raise_exception=True)
    return APIJsonResponse(
        retrieve.get_delivery_request_detail_for_customer(
            user=request.user,
            api=True,
            **serializer.validated_data
        )
    )


@customer_api(['GET'])
def list_customer_locations(request):
    return APIJsonResponse({
        'results': retrieve.get_location_list_for_customer_api(request.user)
    })


class PhotoQuerySerializer(Serializer):
    request = IntegerField(source='request_id', min_value=1)
    photo = IntegerField(source='photo_id', min_value=1)


@customer_api(['GET'])
def request_photo(request):
    serializer = PhotoQuerySerializer(data=request.GET)
    serializer.is_valid(raise_exception=True)
    photo = retrieve.get_photo_for_customer(
        user=request.user,
        **serializer.validated_data
    )
    if photo:
        return content_response(photo.image)
    else:
        return HttpResponseNotFound()


class PriceQuerySerializer(Serializer):
    num_workers = IntegerField(min_value=1)
    hours = DecimalField(max_digits=3, decimal_places=2, min_value=1, max_value=8)
    date = DateField(
        input_formats=[utils.date_time.DATE_FORMAT],
        validators=[
            MinValueValidator(timezone.localdate),
        ]
    )
    time = TimeField(source='timepoint')
    geolocation = GeopositionListField(allow_empty=False, source='coordinates')


@customer_api(['POST'])
def estimate_price(request):
    serializer = PriceQuerySerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    user_customer, _ = get_user_customer_location(request.user)

    try:
        price = tariffs.estimate_request_price_for_customer(
            customer_id=user_customer,
            **serializer.validated_data
        )

    except tariffs.OutOfBounds as e:
        raise PermissionDenied(
            detail='Услуга не оказывается.',
            code='no_service'
        ) from e

    except (tariffs.AutotarificationError, turnout_calculators.PricingError) as e:
        raise PermissionDenied(
            detail='Ошибка тарификации.',
            code='pricing_error'
        ) from e

    return APIJsonResponse({
        'price': price
    })
