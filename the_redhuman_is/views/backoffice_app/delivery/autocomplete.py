from django.contrib.auth.models import User
from django.db.models import (
    Exists,
    OuterRef,
)

from the_redhuman_is.models.delivery import (
    DeliveryItem,
    DeliveryRequest,
    DeliveryService,
    ZoneGroup,
)
from the_redhuman_is.models.models import (
    Customer,
    CustomerLocation,
)
from the_redhuman_is.models.worker import (
    Worker,
    WorkerTag,
)
from the_redhuman_is.views import delivery
from the_redhuman_is.views.backoffice_app.autocomplete import Select2QuerySetAPIView

from utils.date_time import date_from_string


class DeliveryWorkerAutocomplete(Select2QuerySetAPIView):
    queryset = Worker.objects.select_related('workertag')

    paginate_by = 25

    def get_queryset(self):
        return delivery.delivery_workers(self)

    def get_result_label(self, result):
        try:
            workertag = f' [{result.workertag.tag}]'
        except WorkerTag.DoesNotExist:
            workertag = ''

        distance = getattr(result, 'distance', None)
        if distance is not None and round(distance) <= delivery.DISTANCE_LIMIT:
            distance = f' {round(distance)} км'
        else:
            distance = ' - км'

        return f'{result}{workertag}{distance}'


class DeliveryCustomerAutocomplete(Select2QuerySetAPIView):
    queryset = Customer.objects.filter(is_actual=True)
    ordering = 'cust_name'
    model_field_name = 'cust_name'

    def get_queryset(self):
        customers = super(DeliveryCustomerAutocomplete, self).get_queryset()

        first_day = date_from_string(self.forwarded.get('first_day'))
        last_day = date_from_string(self.forwarded.get('last_day'))

        if first_day or last_day:
            requests_qs = DeliveryRequest.objects.filter(customer=OuterRef('pk'))
            if first_day:
                requests_qs = requests_qs.exclude(
                    date__lt=first_day
                )
            if last_day:
                requests_qs = requests_qs.exclude(
                    date__gt=last_day
                )

            customers = customers.annotate(
                requests_exist=Exists(requests_qs)
            ).filter(
                requests_exist=True
            )

        return customers


class OperatorAutocomplete(Select2QuerySetAPIView):
    queryset = User.objects.all()

    def get_queryset(self):
        return delivery.operators(self).order_by(
            'first_name',
            'username'
        )

    def get_result_label(self, result):
        return result.first_name or result.username


class DeliveryRequestAutocomplete(Select2QuerySetAPIView):
    queryset = DeliveryRequest.objects.all()

    def get_queryset(self):
        return delivery.delivery_requests_qs(self)

    def get_result_label(self, result):
        if result.route:
            return f'{result.route} ({result.pk})'
        else:
            return f'{result.pk}'


class LocationAutocomplete(Select2QuerySetAPIView):
    queryset = CustomerLocation.objects.all()

    def get_queryset(self):
        return delivery.locations_qs(self)

    def get_result_label(self, result):
        return result.location_name


class ServiceAutocomplete(Select2QuerySetAPIView):
    queryset = DeliveryService.objects.all()

    def get_queryset(self):
        return delivery.services_qs(self)

    def get_result_label(self, result):
        return result.operator_service_name


class DeliveryItemAutocomplete(Select2QuerySetAPIView):
    queryset = DeliveryItem.objects.select_related('request')

    def get_queryset(self):
        return delivery.delivery_items_qs(self)


class DeliveryZoneAutocomplete(Select2QuerySetAPIView):
    queryset = ZoneGroup.objects.all()
    ordering = 'name'

    def get_queryset(self):
        zones = super(DeliveryZoneAutocomplete, self).get_queryset()
        first_day = date_from_string(self.forwarded.get('first_day'))
        last_day = date_from_string(self.forwarded.get('last_day'))

        if first_day or last_day:
            requests_qs = DeliveryRequest.objects.filter(
                location__locationzonegroup__zone_group=OuterRef('pk')
            )
            if first_day:
                requests_qs = requests_qs.exclude(
                    date__lt=first_day
                )
            if last_day:
                requests_qs = requests_qs.exclude(
                    date__gt=last_day
                )

            zones = zones.annotate(
                requests_exist=Exists(requests_qs)
            ).filter(
                requests_exist=True
            )

        return zones
