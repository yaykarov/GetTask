from django.core.management.base import BaseCommand

from the_redhuman_is.services.worker import update_reliability


class Command(BaseCommand):
    def handle(self, *args, **options):
        update_reliability()
