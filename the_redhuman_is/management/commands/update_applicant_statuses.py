from django.core.management.base import BaseCommand

from async_utils import applicant_status


class Command(BaseCommand):
    def handle(self, *args, **options):
        applicant_status.update_status('приглашен на оформление')

