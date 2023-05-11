from django.core.management.base import BaseCommand

from finance import models


class Command(BaseCommand):
    def handle(self, *args, **options):
        accounts = models.Account.objects.filter(closed=True)
        for account in accounts:
            saldo = account.turnover_saldo()
            if saldo != 0:
                print('<{}> {}: {}'.format(account.pk, account, saldo))

