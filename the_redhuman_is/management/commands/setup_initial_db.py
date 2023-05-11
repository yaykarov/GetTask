from django.core.management import BaseCommand

from django.db import transaction

from the_redhuman_is import setup


class Command(BaseCommand):
    def handle(self, *args, **options):
        with transaction.atomic():
            setup.applicants.create_standard_statuses()
            setup.cost_types.create_standard_cost_types()
            setup.countries.create_countries()
            setup.finance.create_initial_accounts()
            setup.groups.create_standard_user_groups()
            setup.positions.create_standard_positions()
            setup.services.create_standard_services()
            setup.zone_groups.create_zone_groups()
