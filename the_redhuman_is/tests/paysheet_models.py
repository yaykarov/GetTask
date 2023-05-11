from django.test import TestCase

from the_redhuman_is.models import (
    Country,
    Position,
    TalkBankClient,
    Worker,
)


def dummy_worker():
    country = Country.objects.create(name='РФ')
    position = Position.objects.create(name='грузчик')
    worker = Worker.objects.create(
        last_name='',
        name='',
        position=position,
        citizenship=country,
    )

    return worker


class PaysheetTest(TestCase):
    def test_worker_talkbank_empty_client_id(self):
        worker = dummy_worker()

        worker = Worker.objects.all(
        ).with_talk_bank_client_id(
        ).filter(
            pk=worker.pk
        ).get()

        self.assertEqual(worker.talk_bank_client_id, None)

    def test_worker_talkbank_client_id(self):
        worker = dummy_worker()

        client_id = 'some client id'
        TalkBankClient.objects.create(worker=worker, client_id=client_id)

        worker = Worker.objects.all(
        ).with_talk_bank_client_id(
        ).filter(
            pk=worker.pk
        ).get()

        self.assertEqual(worker.talk_bank_client_id, client_id)
