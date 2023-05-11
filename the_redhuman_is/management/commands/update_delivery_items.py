# -*- coding: utf-8 -*-

import re

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from django.db import transaction

from the_redhuman_is import models

from utils.date_time import date_from_string


rx = re.compile('^(\d+):(.*)')


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('--first_day', type=date_from_string, required=True)
        parser.add_argument('--last_day', type=date_from_string, required=True)

    @transaction.atomic
    def handle(self, *args, **options):
        first_day = options['first_day']
        last_day = options['last_day']

        user = User.objects.get(username='admin')

        requests = models.DeliveryRequest.objects.filter(
            date__range=(first_day, last_day)
        )

        for request in requests:
            items = request.deliveryitem_set.all()
            if items.count() == 1:
                item = items.get()
                m = rx.match(item.code)
                if m:
                    request.route = m.group(1)
                    request.save(user=user)

                    codes = [c.strip() for c in m.group(2).split(';')]
                    addresses = [a.strip() for a in item.address.split(';')]
                    types = [t.strip() for t in item.shipment_type.split(';')]

                    for i in range(len(codes)):
                        models.DeliveryItem.objects.create(
                            request=request,
                            interval_begin=item.interval_begin,
                            interval_end=item.interval_end,
                            code=codes[i],
                            mass=(item.mass if i == 0 else 0),
                            volume=(item.volume if i == 0 else 0),
                            place_count=(item.place_count if i == 0 else 0),
                            shipment_type=types[i],
                            address=addresses[i]
                        )

                    if hasattr(item, 'normalizedaddress'):
                        item.normalizedaddress.delete()
                    item.delete()
