from dal_select2.views import Select2QuerySetView
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import MinValueValidator
from django.http import (
    HttpResponseNotFound,
    JsonResponse,
)
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.fields import (
    BooleanField,
    CharField,
    DateField,
    DecimalField,
    IntegerField,
    TimeField,
    FileField,
)
from rest_framework.serializers import Serializer
from rest_framework.views import APIView

from the_redhuman_is.auth import IsCustomer
from the_redhuman_is.models.delivery import DeliveryRequest
from the_redhuman_is.models.models import get_user_location
from the_redhuman_is.models.reconciliation import Reconciliation
from the_redhuman_is.services.delivery import (
    actions,
    retrieve,
)
from the_redhuman_is.services.delivery.utils import (
    normalize_driver_name,
    normalize_driver_phones,
)
from the_redhuman_is.views import delivery
from the_redhuman_is.views.backoffice_app.delivery import main_workplace
from the_redhuman_is.views.gt_customer_account import account_api
from the_redhuman_is.views.utils import (
    _get_value,
    content_response,
)
from utils import date_time
from utils.functools import merge_dicts


@account_api(['GET'])
def list_requests(request):
    return JsonResponse(
        retrieve.get_delivery_request_list_for_customer(request.user, request.GET)
    )


class RequestDetailQuerySerializer(Serializer):
    id = IntegerField(source='request_id', min_value=1)


@account_api(['GET'])
def request_detail(request):
    serializer = RequestDetailQuerySerializer(data=request.GET)
    serializer.is_valid(raise_exception=True)
    return JsonResponse({
        'data': retrieve.get_delivery_request_detail_for_customer(
            user=request.user,
            **serializer.validated_data
        )
    })


@account_api(['GET'])
def report_details(request):
    customer = request.user.customeraccount.customer
    recn_pk = _get_value(request, 'pk')

    try:
        reconciliations = Reconciliation.objects.filter(
            customer=customer
        )
        if get_user_location(request.user) is not None:
            reconciliations = reconciliations.filter(
                location__locationaccount__user=request.user
            )
        reconciliation = reconciliations.get(pk=recn_pk)

        return delivery.interval_report_response(
            reconciliation.first_day,
            reconciliation.last_day,
            customer,
            reconciliation.location,
        )

    except Reconciliation.DoesNotExist:
        return HttpResponseNotFound()


class PhotoQuerySerializer(Serializer):
    request = IntegerField(source='request_id', min_value=1)
    photo = IntegerField(source='photo_id', min_value=1)


@account_api(['GET'])
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


class DeliveryItemCreateSerializer(main_workplace.DeliveryItemCreateSerializer):
    workers_required = IntegerField(min_value=1, default=1)


class DeliveryRequestCreateSerializer(Serializer):
    request = IntegerField(min_value=0, source='request_id', allow_null=True, default=None)
    location = IntegerField(min_value=0, source='location_id', allow_null=True, default=None)
    date = DateField(
        input_formats=[date_time.DATE_FORMAT],
        validators=[MinValueValidator(retrieve.CUSTOMER_REQUEST_MIN_DATE)]
    )
    driver_name = CharField(allow_blank=True, default='')
    driver_phones = CharField(allow_blank=True, default='')
    items = DeliveryItemCreateSerializer(many=True, allow_empty=False)
    merge = BooleanField(default=True)

    def validate_driver_name(self, value):
        return normalize_driver_name(value)

    def validate_driver_phones(self, value):
        return normalize_driver_phones(value)


@account_api(['POST'])
def create_request(request):
    customer_id = request.user.customeraccount.customer_id
    serializer = DeliveryRequestCreateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    delivery_request = actions.create_delivery_request(
        user=request.user,
        customer_id=customer_id,
        notify_dispatchers=True,
        **serializer.validated_data
    )
    return JsonResponse({
        'data': retrieve.get_delivery_request_detail_for_customer(
            request_id=delivery_request.pk,
            user=request.user,
        )
    })


class DeliveryRequestUpdateSerializer(Serializer):
    request = IntegerField(min_value=1, source='request_id')
    date = DateField(input_formats=[date_time.DATE_FORMAT])
    driver_name = CharField()
    driver_phones = CharField()
    customer_confirmation = BooleanField()
    status = CharField()
    customer_comment = CharField()

    def validate_driver_name(self, value):
        return normalize_driver_name(value)

    def validate_driver_phones(self, value):
        return normalize_driver_phones(value)

    def validate(self, attrs):
        if 'request_id' not in attrs:
            raise ValidationError('Номер заявки является обязательным полем.')
        n_fields = len(attrs.keys() - {'request_id'})
        if n_fields > 1:
            raise ValidationError('Одновременно можно обновлять только одно поле.')
        elif n_fields == 0:
            raise ValidationError(
                'Отсутствует обновляемое поле. Доступные для редактирования поля: '
                'date, driver_name, driver_phones, customer_confirmation, '
                'status.'
            )
        return attrs

    def validate_status(self, value):
        if value not in (DeliveryRequest.CANCELLED, DeliveryRequest.CANCELLED_WITH_PAYMENT):
            raise ValidationError(
                'Вручную можно установить только статусы "Отмена" и "Отмена с оплатой".'
            )
        return value


@account_api(['POST'])
def update_request(request):
    serializer = DeliveryRequestUpdateSerializer(data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    request_id = serializer.validated_data.pop('request_id')
    field = next(iter(serializer.validated_data.keys()))
    value = next(iter(serializer.validated_data.values()))
    actions.update_delivery_request(
        request_id,
        field,
        value,
        request.user,
        force_commit=True
    )
    return JsonResponse(
        {
            'data': retrieve.get_delivery_request_detail_for_customer(
                request_id,
                user=request.user,
            ),
        }
    )


class DeliveryItemAddSerializer(DeliveryItemCreateSerializer):
    # + fields from Item
    request = IntegerField(min_value=1, source='request_id')


@account_api(['POST'])
def create_delivery_item(request):
    serializer = DeliveryItemAddSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    actions.create_delivery_item(
        user=request.user,
        notify_dispatchers=True,
        **serializer.validated_data
    )
    return JsonResponse(
        {
            'data': retrieve.get_delivery_request_detail_for_customer(
                request_id=serializer.validated_data['request_id'],
                user=request.user,
            ),
            'messages': [],
            'confirmation_required': False,
        }
    )


class DeliveryItemUpdateParamsSerializer(Serializer):
    request = IntegerField(min_value=1, source='request_id')
    item = IntegerField(min_value=1, source='item_id')


class DeliveryItemUpdateFieldsSerializer(Serializer):
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
    workers_required = IntegerField(min_value=1)
    first = BooleanField()

    def validate(self, attrs):
        n_fields = len(attrs.keys())
        if n_fields > 1:
            if len(attrs.keys() & {'interval_begin, interval_end'}) == 2:
                attrs = {'time_interval': (attrs['interval_begin'], attrs['interval_end'])}
            else:
                raise ValidationError(
                    'Одновременно можно обновлять только одно поле'
                    ' или пару interval_begin, interval_end.'
                )
        elif n_fields == 0:
            raise ValidationError(
                'Отсутствует обновляемое поле. Доступные для редактирования поля: '
                'interval_begin, interval_end, code, mass, volume, max_size, place_count, '
                'shipment_type, address, has_elevator, floor, carrying_distance, '
                'workers_required, first.'
            )
        return attrs


@account_api(['POST'])
def update_item(request):
    ser_params = DeliveryItemUpdateParamsSerializer(data=request.data)
    ser_params.is_valid()
    ser_field = DeliveryItemUpdateFieldsSerializer(data=request.data, partial=True)
    ser_field.is_valid()
    if ser_params.errors or ser_field.errors:
        raise ValidationError(merge_dicts(ser_params.errors, ser_field.errors))
    field = next(iter(ser_field.validated_data.keys()))
    value = next(iter(ser_field.validated_data.values()))
    _, messages, confirmation_required = actions.update_delivery_item(
        field=field,
        value=value,
        user=request.user,
        **ser_params.validated_data
    )
    return JsonResponse(
        {
            'data': retrieve.get_delivery_request_detail_for_customer(
                ser_params.validated_data['request_id'],
                user=request.user,
            ),
        }
    )


class LocationSerializer(Serializer):
    location = IntegerField(min_value=1, source='location_id', allow_null=True, default=None)


@account_api(['GET'])
def requests_on_map(request):
    serializer = LocationSerializer(data=request.GET)
    serializer.is_valid(raise_exception=True)
    return JsonResponse(
        retrieve.get_requests_on_map(
            date=timezone.localdate(),
            user=request.user,
            **serializer.validated_data
        )
    )


class MapRequestAutocomplete(Select2QuerySetView, APIView):

    permission_classes = [IsCustomer]

    def get_queryset(self):
        location_id = self.forwarded.get('location')

        delivery_requests, _, _ = retrieve.get_requests_on_map_querysets(
            timezone.localdate(),
            self.request.user,
            location_id=location_id,
        )

        request_type = self.forwarded.get('request_type')
        if request_type == 'expiring_only':
            delivery_requests = delivery_requests.filter(is_expiring=True)
        elif request_type == 'assignment_delay_only':
            delivery_requests = delivery_requests.filter(is_worker_assignment_delayed=True)

        if self.q:
            delivery_requests = delivery_requests.filter_by_text(
                self.q,
                mode='customer_autocomplete'
            )

        return delivery_requests.order_by(
            'pk',
        ).values(
            'pk',
            'driver_name',
            'items',
        )

    def get_result_value(self, result):
        return str(result['pk'])

    @staticmethod
    def _get_driver_short_name(driver_name):
        if not driver_name:
            return 'Без имени'
        components = driver_name.split(' ')
        name = components[0]
        try:
            name += f' {components[1][0]}.'
            name += f' {components[2][0]}.'
        except IndexError:
            pass
        return name

    def get_result_label(self, result):
        name = self._get_driver_short_name(result['driver_name'])
        code = '<br/>'.join([item['code'] for item in result['items']])
        return f"{result['pk']} {name}<br/>{code}"


class DeliveryRequestImportSerializer(Serializer):
    requests = FileField(source='xlsx_file')


@account_api(['POST'])
def import_requests(request):
    serializer = DeliveryRequestImportSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    try:
        actions.import_requests(
            customer_id=request.user.customeraccount.customer_id,
            user=request.user,
            notify_dispatchers=True,
            **serializer.validated_data
        )
    except DjangoValidationError as ex:
        if ex.code == 'bad_file':
            raise ValidationError({
                'requests': ex.messages
            })
        else:
            raise
    return JsonResponse({})
