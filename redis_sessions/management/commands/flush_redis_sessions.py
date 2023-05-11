from binascii import Error

from django.core.management.base import BaseCommand

from ... import backend
from ...session import SessionStore


class Command(BaseCommand):
    help = 'flush all redis sessions'

    def handle(self, *args, **kwargs):
        session_keys = backend.keys('*')

        for session_key in session_keys:
            session_data = backend.get(session_key)

            if session_data is not None:
                try:
                    SessionStore().decode(session_data)
                    backend.delete(session_key)
                except (Error, TypeError):
                    continue
