from django.core.management.base import BaseCommand

from async_utils import uiscom_missed_calls


class Command(BaseCommand):
    def handle(self, *args, **options):
        uiscom_missed_calls.import_uiscom_missed_calls()
