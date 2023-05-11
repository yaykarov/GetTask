from django.core.management.base import BaseCommand

from django.db import transaction

from the_redhuman_is import models


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('--name', type=str, required=True)
        parser.add_argument('--code', type=str, required=True)

    @transaction.atomic
    def handle(self, *args, **options):
        zone_name = options['name']
        zone_code = options['code']

        group = models.ZoneGroup.objects.create(
            name=zone_name,
            code=zone_code
        )

        suffixes = [
            ('', ''),
            ('_15', ' до 15 км'),
            ('_30', ' до 30 км'),
            ('_45', ' до 45 км'),
            ('_60', ' до 60 км'),
            ('_60+', ' от 60 км'),
        ]

        for code_suffix, name_suffix in suffixes:
            models.DeliveryZone.objects.create(
                group=group,
                code=f'{zone_code}{code_suffix}',
                name=f'{zone_name}{name_suffix}'
            )

        customer = models.Customer.objects.get(pk=21)
        location = models.CustomerLocation.objects.create(
            customer_id=customer,
            location_name=zone_name,
        )
        print(location.pk)
