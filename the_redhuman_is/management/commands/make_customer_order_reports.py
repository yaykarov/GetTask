from django.core.management.base import BaseCommand

from async_utils import customer_orders


class Command(BaseCommand):
    def handle(self, *args, **options):
        customer_orders.make_customer_orders_telegram_report()
