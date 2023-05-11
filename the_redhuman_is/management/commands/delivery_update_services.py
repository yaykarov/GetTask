# -*- coding: utf-8 -*-

from django.core.management.base import BaseCommand

from the_redhuman_is import models
from the_redhuman_is.services.delivery.tariffs import try_to_update_tariff

from utils.date_time import date_from_string


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('--first_day', type=date_from_string, required=True)
        parser.add_argument('--last_day', type=date_from_string, required=True)

    def handle(self, *args, **options):
        first_day = options['first_day']
        last_day = options['last_day']

        requests = models.DeliveryRequest.objects.filter(
            date__range=(first_day, last_day)
        )
        for request in requests:
            try_to_update_tariff(request, request.author)
