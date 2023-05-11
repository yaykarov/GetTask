from django.test import SimpleTestCase

from unittest.mock import MagicMock

from the_redhuman_is.services.paysheet.talk_bank import (
    WorkerOperationResult,
    do_bind_worker,
    register_worker_income_async,
)

from the_redhuman_is.async_utils.talk_bank.exceptions import TalkBankExceptionError
from the_redhuman_is.async_utils.talk_bank.talk_bank import SelfemploymentsStatus


_SOME_TEXT_DESCRIPTION = 'some long text description'


def log(func):
    def proxy(self, *args, **kwargs):
        self.actions.append(func.__name__)
        return func(self, *args, **kwargs)
    return proxy


class TestWorkerContext():
    def __init__(self):
        self.actions = []

    @log
    def bank_client_exists(self):
        return True

    @log
    def get_selfemployment_status(self):
        return SelfemploymentsStatus.registered, _SOME_TEXT_DESCRIPTION

    @log
    def create_bank_client(self):
        pass

    @log
    def bind_client(self):
        pass

    @log
    def save_bind_result(self, result: WorkerOperationResult, description: str) -> None:
        pass

    @log
    def register_income(self) -> None:
        pass

    @log
    def make_payment(self):
        pass

    @log
    def cancel_invoice(self):
        pass

    @log
    def save_result(self, result: WorkerOperationResult, description: str):
        pass


class PaysheetSimpleTest(SimpleTestCase):
    def test_payment_ok(self) -> None:
        context = TestWorkerContext()

        status, description = register_worker_income_async(context)

        self.assertEqual(status, WorkerOperationResult.ok)

    def test_client_creation_failed(self) -> None:
        context = TestWorkerContext()
        context.bank_client_exists = MagicMock(return_value=False)

        context.create_bank_client = MagicMock(side_effect=TalkBankExceptionError(_SOME_TEXT_DESCRIPTION))
        status, description = do_bind_worker(context)
        self.assertEqual(status, WorkerOperationResult.client_creation_failed)
        self.assertEqual(description, _SOME_TEXT_DESCRIPTION)

        context.create_bank_client = MagicMock(side_effect=Exception(_SOME_TEXT_DESCRIPTION))
        status, description = do_bind_worker(context)
        self.assertEqual(status, WorkerOperationResult.client_creation_failed)
        self.assertEqual(description, _SOME_TEXT_DESCRIPTION)

    def test_selfemployment_status_exception(self) -> None:
        context = TestWorkerContext()

        context.get_selfemployment_status = MagicMock(side_effect=TalkBankExceptionError(_SOME_TEXT_DESCRIPTION))
        status, description = do_bind_worker(context)
        self.assertEqual(status, WorkerOperationResult.client_status_error)

    def test_failed_statuses(self) -> None:
        context = TestWorkerContext()

        context.get_selfemployment_status = MagicMock(return_value=(SelfemploymentsStatus.unregistered, _SOME_TEXT_DESCRIPTION))
        status, description = do_bind_worker(context)
        self.assertEqual(status, WorkerOperationResult.client_unregistered)

        context.get_selfemployment_status = MagicMock(return_value=(SelfemploymentsStatus.unbound, _SOME_TEXT_DESCRIPTION))
        status, description = do_bind_worker(context)
        self.assertEqual(status, WorkerOperationResult.client_bind_requested)

        status, description = register_worker_income_async(context)
        self.assertEqual(status, WorkerOperationResult.client_unbound)

        context.get_selfemployment_status = MagicMock(return_value=(SelfemploymentsStatus.error, _SOME_TEXT_DESCRIPTION))
        status, description = register_worker_income_async(context)
        self.assertEqual(status, WorkerOperationResult.client_status_error)

    def test_client_bind_error(self) -> None:
        context = TestWorkerContext()

        context.get_selfemployment_status = MagicMock(return_value=(SelfemploymentsStatus.unbound, _SOME_TEXT_DESCRIPTION))
        context.bind_client = MagicMock(side_effect=TalkBankExceptionError(_SOME_TEXT_DESCRIPTION))
        status, description = register_worker_income_async(context)
        self.assertEqual(status, WorkerOperationResult.client_bind_failed)
        self.assertEqual(description, _SOME_TEXT_DESCRIPTION)

    def test_income_registration(self) -> None:
        context = TestWorkerContext()

        context.register_income = MagicMock(side_effect=TalkBankExceptionError(_SOME_TEXT_DESCRIPTION))
        status, description = register_worker_income_async(context)
        self.assertEqual(status, WorkerOperationResult.income_registration_failed)
        self.assertEqual(description, _SOME_TEXT_DESCRIPTION)
