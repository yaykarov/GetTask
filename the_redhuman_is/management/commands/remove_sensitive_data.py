from django.core.management.base import BaseCommand

from the_redhuman_is.regular_migrations import remove_sensitive_data


class Command(BaseCommand):
    def handle(self, *args, **options):
        remove_sensitive_data()
