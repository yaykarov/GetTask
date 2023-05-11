# -*- coding: utf-8 -*-

import time

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from the_redhuman_is import models

from utils.date_time import date_from_string

from the_redhuman_is.tasks import normalize_address


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('--first_day', type=date_from_string, required=True)
        parser.add_argument('--last_day', type=date_from_string, required=True)
        parser.add_argument('--request_pk', type=int, required=False)

    def handle(self, *args, **options):
        first_day = options['first_day']
        last_day = options['last_day']
        request_pk = options.get('request_pk')

        user = User.objects.get(username='admin')

        requests = models.DeliveryRequest.objects.filter(
            date__range=(first_day, last_day)
        )
        if request_pk:
            requests = requests.filter(pk=request_pk)

        for request in requests:
            for item in request.deliveryitem_set.filter(normalizedaddress__isnull=True):
                normalize_address(item.pk, 0, user)
                # dadata.ru: Максимальная частота запросов — 10 в секунду.
                # dirty and easy way
                time.sleep(0.15)
