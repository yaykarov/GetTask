from django.contrib.sessions.models import Session
from django.core.management.base import BaseCommand
from django.db import connection, transaction
from django.db.utils import DatabaseError


class Command(BaseCommand):
    help = 'flush all django orm sessions'

    def handle(self, *args, **wargs):
        cursor = connection.cursor()

        try:  # raw sql truncate
            with transaction.atomic():
                cursor.execute(
                    'TRUNCATE TABLE %s' % Session._meta.db_table
                )
        except DatabaseError:  # otherwise via django orm
            with transaction.atomic():
                Session.objects.all.delete()
