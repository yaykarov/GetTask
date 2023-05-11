import datetime

from django.core.management.base import BaseCommand

from django.core.exceptions import ObjectDoesNotExist

from django.utils import timezone

from the_redhuman_is import models
from the_redhuman_is.models.delivery import DeliveryService

from the_redhuman_is.views.gt_customer_account import _create_single_turnout_calculator

from utils.date_time import date_from_string


# Todo: merge with the_redhuman_is.views.gt_customer_account._setup_service
def _setup_service(
        first_day,
        customer,
        service,
        customer_rate,
        worker_rate,
        delivery_service_params):

    customer_service = models.create_customer_service(customer, service)

    amount_calculator = models.AmountCalculator.objects.create(
        customer_calculator=_create_single_turnout_calculator(customer_rate),
        foreman_calculator=_create_single_turnout_calculator(worker_rate),
        worker_calculator=_create_single_turnout_calculator(worker_rate)
    )
    models.ServiceCalculator.objects.create(
        customer_service=customer_service,
        calculator=amount_calculator,
        first_day=first_day,
    )

    for zone, customer_name, operator_name, hours, mass, is_for_united in delivery_service_params:
        delivery_service = models.DeliveryService.objects.create(
            is_for_united_request=is_for_united,
            min_mass=mass,
            zone=zone,
            service=customer_service,
            customer_service_name=customer_name,
            operator_service_name=operator_name,
            hours=hours
        )


_DEFAULT_TARIFFS = {
    'type1': (2, 315, 355, 380),
    'type2': (2, 305, 350, 370),
    'type3': (2, 280, 320, 360),
    'type4': (2, 300, 330, 360),
    'type5': (3, 280, 330, 360),
}


_ZONES_TYPES = {
    'type1': ['adler'],
    'type2': ['sochi'],
    'type3': ['voronezh'],
    'type4': ['arkhangelsk', 'krasnodar', 'kursk', 'nn', 'petrozavodsk', 'ryazan', 'samara', 'severodvinsk', 'ulyanovsk', 'ufa'],
    'type5': ['msk', 'spb']
}


def _parse_arguments(options):
    location = models.CustomerLocation.objects.get(pk=options['location_pk'])
    zone = options['zone']

    if options['rate_4'] is not None:
        rate_4 = options['rate_4'] * 1.2
        rate_7 = options['rate_7'] * 1.2
        rate_inf = options['rate_inf'] * 1.2
        first_day = options['first_day']
        min_hours = options['min_hours']
    else:
        for tariff, zones in _ZONES_TYPES.items():
            if zone in zones:
                first_day = timezone.now().date() - datetime.timedelta(days=10)
                min_hours, rate_inf, rate_7, rate_4 = _DEFAULT_TARIFFS[tariff]
                break
        else:
            raise Exception('Zone {} is unknown'.format(zone))

    return location, zone, rate_4, rate_7, rate_inf, first_day, min_hours


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('--location_pk', type=int, required=True)
        parser.add_argument('--zone', type=str, required=True)
        parser.add_argument('--rate_4', type=int, required=False)
        parser.add_argument('--rate_7', type=int, required=False)
        parser.add_argument('--rate_inf', type=int, required=False)
        parser.add_argument('--first_day', type=date_from_string, required=False)
        parser.add_argument('--min_hours', type=int, required=False)

    def handle(self, *args, **options):
        (
            location,
            zone,
            rate_4,
            rate_7,
            rate_inf,
            first_day,
            min_hours
        ) = _parse_arguments(options)

        customer = location.customer_id
        name = location.location_name

        service, _ = models.Service.objects.get_or_create(name=name)

        try:
            customer_service = models.CustomerService.objects.get(
                customer=customer,
                service=service
            )

        except ObjectDoesNotExist:
            customer_service = models.create_customer_service(customer, service)

        models.LocationZoneGroup.objects.get_or_create(
            location=location,
            zone_group=models.ZoneGroup.objects.get(name=name)
        )

        delivery_services_to_create = (
            ('',     ''),
            ('_15',  ' до 15 км'),
            ('_30',  ' до 30 км'),
            ('_45',  ' до 45 км'),
            ('_60',  ' до 60 км'),
            ('_60+', ' от 60 км'),
        )

        for zone_suffix, name_suffix in delivery_services_to_create:
            travel_hours = DeliveryService.TRAVEL_HOURS[zone_suffix[1:]]
            models.DeliveryService.objects.create(
                zone=zone + zone_suffix,
                service=customer_service,
                customer_service_name=name,
                operator_service_name=name + name_suffix,
                travel_hours=travel_hours,
                hours=min_hours + travel_hours,
            )

        customer_calculator = models.SingleTurnoutCalculator.objects.create(
            parameter_1='hours',
            parameter_2='hours'
        )
        customer_calculator.intervals.add(
            models.CalculatorInterval.objects.create(
                begin=0,
                b=0,
                k=rate_4
            )
        )
        customer_calculator.intervals.add(
            models.CalculatorInterval.objects.create(
                begin=4.0001,
                b=0,
                k=rate_7
            )
        )
        customer_calculator.intervals.add(
            models.CalculatorInterval.objects.create(
                begin=7.0001,
                b=0,
                k=rate_inf
            )
        )
        customer_calculator.save()

        amount_calculator = models.AmountCalculator.objects.create(
            customer_calculator=customer_calculator,
            foreman_calculator=models.SingleTurnoutCalculator.objects.create(
                parameter_1='hours',
                parameter_2='tariffs_01_04_21'
            ),
            worker_calculator=models.SingleTurnoutCalculator.objects.create(
                parameter_1='hours',
                parameter_2='tariffs_01_04_21'
            ),
        )

        models.ServiceCalculator.objects.create(
            customer_service=customer_service,
            calculator=amount_calculator,
            first_day=first_day
        )
