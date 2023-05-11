from django.contrib.sessions.models import Session
from django.core.management.base import BaseCommand
from django.utils import timezone

from ... import backend
from ...utils import total_seconds


class Command(BaseCommand):
    help = 'copy django orm sessions to redis'

    def handle(self, *args, **kwargs):
        sessions = Session.objects.filter(expire_date__gt=timezone.now())
        count = sessions.count()
        counter = 1

        self.stdout.write('sessions to copy %d\n' % count)

        for session in sessions:
            self.stdout.write('processing %d of %d\n' % (counter, count))

            expire_in = session.expire_date - timezone.now()
            expire_in = round(total_seconds(expire_in))

            if expire_in < 0:
                continue

            backend.delete(session.session_key)

            backend.save(
                session.session_key,
                expire_in,
                session.session_data,
                False
            )

            counter += 1
