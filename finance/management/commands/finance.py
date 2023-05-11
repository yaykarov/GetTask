from datetime import timedelta

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils.timezone import now

from finance.models import Account


class Command(BaseCommand):
    help = 'Update Accounts model'

    def add_arguments(self, parser):
        parser.add_argument(
            '--init',
            action='store_true',
            dest='init',
            help='Init Account full name',
        )

    def handle(self, *args, **options):
        if options['init']:
            self.init_log()

    def init_log(self):
        accounts = Account.objects.filter(parent_id__isnull=True)
        for item in accounts:
            item.save()
