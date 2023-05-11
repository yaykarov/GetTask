import random
import string

from django.contrib.auth.models import User
from django.core.management import BaseCommand, CommandError

from the_redhuman_is.models import Customer
from the_redhuman_is.tasks import send_email

ALLOWED_CHARACTERS = string.ascii_letters + string.digits
EXCLUDED_CHARACTERS = 'iIlLoO'
ALLOWED_CHARACTERS = ''.join(x for x in ALLOWED_CHARACTERS if x not in EXCLUDED_CHARACTERS)

PASSWORD_LENGTH = 10
TITLE = 'Пароль на GetTask.ru обновлен.'
BODY = 'Добрый день, {}.\n\nВаш пароль на GetTask.ru обновлен.\n\nНовый пароль: {}'


class Command(BaseCommand):
    help = 'Resets passwords for a specified customer'

    def add_arguments(self, parser):
        parser.add_argument('client_id', type=int)

    def handle(self, *args, **options):
        client_id = options['client_id']
        try:
            customer = Customer.objects.get(pk=client_id)
        except Customer.DoesNotExist:
            raise CommandError(f'Customer {client_id} does not exist.')
        users = User.objects.filter(customeraccount__customer=customer, is_active=True)
        for user in users:
            password = ''.join(random.choices(ALLOWED_CHARACTERS, k=PASSWORD_LENGTH))
            user.set_password(password)
            user.save(update_fields=['password'])
            send_email(
                to=user.email,
                subject=TITLE,
                html=BODY.format(user.first_name, password),
            )
