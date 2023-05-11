import datetime
import enum
import hashlib
import hmac
import json
from dataclasses import (
    dataclass,
)
from decimal import (
    Decimal,
)
from http import (
    HTTPStatus,
)
from typing import (
    Dict,
    List,
    Optional,
    Tuple,
    Union,
)

import requests

from .exceptions import (  # noqa: WPS300
    AccessDeniedError,
    BadRequestError,
    ClientAlreadyExistsError,
    ClientWithSuchPhoneAlreadyExistsError,
    ForbiddenError,
    InternalServerError,
    TalkBankExceptionError,
)

# Debug logging
import logging
from http.client import HTTPConnection


TB_BASE_URL = ''
TB_PARTNER_ID = ''
TB_PARTNER_TOKEN = ''


try:
    from .talk_bank_local import *
except ImportError:
    pass


CLIENT_ID = 'client_id'
DESCRIPTION = 'description'
ERRORS = 'errors'
DEFAULT_EXCEPTION_MESSAGE = 'Something went wrong.'


@dataclass
class TransferResult(object):
    """Transfer result.

    https://talkbank.atlassian.net/wiki/spaces/BAAS/pages/1221427222
    /payment+to+account+status
    """

    completed: bool
    status: str
    order_slug: str
    talk_bank_commission: Decimal
    beneficiary_partner_commission: Decimal


@dataclass
class Service(object):
    """Service.

    https://talkbank.atlassian.net/wiki/spaces/BAAS/pages/1221230612
    /selfemployments+register+income
    """

    name: str
    amount: Decimal
    quantity: int

    def as_dict(self) -> Dict[str, Union[str, float, int]]:
        """Convert instance to dict."""
        return {
            'Name': self.name,
            'Amount': float(self.amount.quantize(Decimal('0.00'))),
            'Quantity': self.quantity,
        }


class CancelReceiptReason(enum.Enum):
    """Reason for cancellation of the receipt."""

    registration_mistake = 'REGISTRATION_MISTAKE'
    refund = 'REFUND'


class SelfemploymentsStatus(enum.Enum):
    registered = 'registered'
    unregistered = 'unregistered'
    unbound = 'unbound'
    error = 'error'
    unknown = 'unknown'


@dataclass
class EventSubscription:
    id: int
    url: str
    event: str


@dataclass
class SubscriptionStatus:
    enabled: list[EventSubscription]
    available: list[str]


class TalkBankClient(object):  # noqa: WPS214
    """Talk bank client.

    https://talkbank.atlassian.net/wiki/spaces/BAAS/pages
    """

    def __init__(self, base_url: str, partner_id: str, partner_token: str):
        self.base_url = base_url
        self.partner_id = partner_id
        self.partner_token = partner_token

        self.api_dict = {
            'create_client': '/api/v1/clients',
            'get_selfemployment_status': '/api/v1/selfemployments/{client_id}',
            'bind_client': '/api/v1/selfemployments/{client_id}/bind',
            'register_income': '/api/v1/selfemployments/{client_id}/receipt-async',
            'transfer': '/api/v1/account/transfer',
            'get_transfer_status': '/api/v1/account/transfer/{order_slug}',
            'cancel_receipt': '/api/v1/selfemployments/{client_id}/receipt',
            'event_subscriptions': '/api/v1/event-subscriptions',
            'delete_event_subscription': '/api/v1/event-subscriptions/{subscription_id}'
        }

   # https://stackoverflow.com/questions/16337511/log-all-requests-from-the-python-requests-module
    def enable_logging(self):
        HTTPConnection.debuglevel = 2

        logging.basicConfig()
        logging.getLogger().setLevel(logging.DEBUG)
        requests_log = logging.getLogger('requests.packages.urllib3')
        requests_log.setLevel(logging.DEBUG)
        requests_log.propagate = True

    def create_client_with_simple_identification(  # noqa: WPS211
        self,
        client_id: str,
        first_name: str,
        middle_name: str,
        last_name: str,
        birth_day: str, # date (yyyy-mm-dd)
        gender: int,
        secret_word: str,
        phone: str,
        document_serial: str,
        document_number: str,
        document_date: str,
        inn: Optional[str] = None,
        snils: Optional[str] = None,
    ) -> str:
        """Create client with simple identification.

        The spending limit is 200 thousand rubles per month,
        the maximum balance is 60 thousand rubles.

        https://talkbank.atlassian.net/wiki/spaces/BAAS/pages/619413590
        /client+store
        """
        document = {
            'serial': document_serial,
            'number': document_number,
            'date': document_date,
        }
        person = {
            'first_name': first_name,
            'middle_name': middle_name,
            'last_name': last_name,
            'secret_word': secret_word,
            'phone': phone,
            'birth_day': birth_day,
            'gender': gender,
            'document': document,
        }
        if inn:
            person['inn'] = inn
        if snils:
            person['snils'] = snils
        body = {
            CLIENT_ID: client_id,
            'person': person,
        }
        api_name = 'create_client'
        json_body = json.dumps(body)
        headers = self._get_headers(api_name, 'POST', json_body)
        url = self.get_full_url(api_name)
        response = requests.post(url, data=json_body, headers=headers)
        response_dict = response.json()
        self._raise_exception(
            response.status_code,
            response_dict.get(DESCRIPTION, DEFAULT_EXCEPTION_MESSAGE),
            response_dict.get(ERRORS),
        )
        return response_dict[CLIENT_ID]

    def create_client_without_identification(self, client_id: str, phone: str) -> str:
        """Create client without identification.

        The spending limit is 40 thousand rubles per month,
        the maximum balance is 15 thousand rubles.

        https://talkbank.atlassian.net/wiki/spaces/BAAS/pages/619413590
        /client+store
        """
        body = {
            CLIENT_ID: client_id,
            'person': {
                'phone': phone,
            },
        }
        json_body = json.dumps(body)
        api_name = 'create_client'
        headers = self._get_headers(api_name, 'POST', json_body)
        url = self.get_full_url(api_name)
        response = requests.post(url, data=json_body, headers=headers)
        response_dict = response.json()
        self._raise_exception(
            response.status_code,
            response_dict.get(DESCRIPTION, DEFAULT_EXCEPTION_MESSAGE),
            response_dict.get(ERRORS),
        )
        return response_dict[CLIENT_ID]

    def get_selfemployment_status(self, client_id: str) -> Tuple['SelfemploymentsStatus', str]:
        """Get status selfempoyement.

        Statuses:
        registered - client has registered
        unregistered - client has not registered
        unbound - client is registered, but unbind from the Talkback system

        https://talkbank.atlassian.net/wiki/spaces/BAAS/pages/625344749
        /selfemployments+status
        """
        body = ''
        api_name = 'get_selfemployment_status'
        api_url_parameters = {CLIENT_ID: client_id}
        headers = self._get_headers(api_name, 'GET', body, api_url_parameters)
        url = self.get_full_url(api_name, client_id=client_id)
        response = requests.get(url, headers=headers)
        response_dict = response.json()
        print(response_dict)
        description = response_dict.get(DESCRIPTION, DEFAULT_EXCEPTION_MESSAGE)
        self._raise_exception(
            response.status_code,
            description,
            response_dict.get(ERRORS),
        )
        return SelfemploymentsStatus(response_dict.get('status', 'error')), description

    def bind_client(self, client_id: str, raise_exception: bool = False) -> bool:
        """Bind client to the Talkback system.

        Return True if the operation was successful else False.

        https://talkbank.atlassian.net/wiki/spaces/BAAS/pages/1221427254
        /Talkbank+selfemployments+bind
        """
        body = ''
        api_name = 'bind_client'
        api_url_parameters = {CLIENT_ID: client_id}
        headers = self._get_headers(api_name, 'POST', body, api_url_parameters)
        url = self.get_full_url(api_name, client_id=client_id)
        response = requests.post(url, headers=headers)
        response_dict = response.json()
        status = response_dict['status']
        if raise_exception:
            self._raise_exception(
                response.status_code,
                response_dict.get(DESCRIPTION, DEFAULT_EXCEPTION_MESSAGE),
                response_dict.get(ERRORS),
                status,
            )
        return status == 'success'

    def register_income_from_individual(  # noqa: WPS211
        self,
        client_id: str,
        operation_time: str,
        services: List['Service'],
        total_amount: Decimal,
        request_time: Optional[str] = None,
        geo_info: Optional[Tuple[Decimal, Decimal]] = None,
        operation_unique_id: Optional[str] = None,
    ) -> str:
        """Register selfemployments income from individual.

        Return tuple of the receipt ID and the link to receipt.

        https://talkfinancetech.atlassian.net/wiki/spaces/BAAS/pages/3081772/2.0+selfemployments+add+receipt+async
        """
        body = {
            'OperationTime': operation_time,
            'Services': list(map(lambda service: service.as_dict(), services)),
            'TotalAmount': total_amount,
            'IncomeType': 'FROM_INDIVIDUAL',
        }
        if request_time:
            body['request_time'] = request_time
        if geo_info:
            body['geo_info'] = geo_info
        if operation_unique_id:
            body['operation_unique_id'] = operation_unique_id
        json_body = json.dumps(body)
        return self._register_income(client_id, json_body)

    def register_income_from_legal_entity(  # noqa: WPS211
        self,
        client_id: str,
        operation_time: str,
        services: List['Service'],
        total_amount: Decimal,
        customer_inn: str,
        customer_organization: str,
        request_time: Optional[str] = None,
        geo_info: Optional[Tuple[Decimal, Decimal]] = None,
        operation_unique_id: Optional[str] = None,
    ) -> str:
        """Register selfemployments income from legal entity.

        Return tuple of the receipt ID and the link to receipt.

        https://talkbank.atlassian.net/wiki/spaces/BAAS/pages/1221230612
        /selfemployments+register+income
        """
        body = {
            'OperationTime': operation_time,
            'Services': list(map(lambda service: service.as_dict(), services)),
            'TotalAmount': float(total_amount.quantize(Decimal('0.00'))),
            'IncomeType': 'FROM_LEGAL_ENTITY',
            'CustomerInn': customer_inn,
            'CustomerOrganization': customer_organization,
        }
        if request_time:
            body['request_time'] = request_time
        if geo_info:
            body['geo_info'] = geo_info
        if operation_unique_id:
            body['operation_unique_id'] = operation_unique_id
        json_body = json.dumps(body)
        return self._register_income(client_id, json_body)

    def register_income_from_foreign_agency(  # noqa: WPS211
        self,
        client_id: str,
        operation_time: str,
        services: List['Service'],
        total_amount: Decimal,
        customer_organization: str,
        request_time: Optional[str] = None,
        geo_info: Optional[Tuple[Decimal, Decimal]] = None,
        operation_unique_id: Optional[str] = None,
    ) -> str:
        """Register selfemployments income from foreign agency.

        https://talkfinancetech.atlassian.net/wiki/spaces/BAAS/pages/3081772/2.0+selfemployments+add+receipt+async
        """
        body = {
            'OperationTime': operation_time,
            'Services': list(map(lambda service: service.as_dict(), services)),
            'TotalAmount': total_amount,
            'IncomeType': "FROM_FOREIGN_AGENCY",
            'CustomerOrganization': customer_organization,
        }
        if request_time:
            body['request_time'] = request_time
        if geo_info:
            body['geo_info'] = geo_info
        if operation_unique_id:
            body['operation_unique_id'] = operation_unique_id
        json_body = json.dumps(body)
        return self._register_income(client_id, json_body)

    def cancel_receipt(
        self, client_id: str, receipt_id: str, reason: 'CancelReceiptReason',
    ) -> None:
        """Cancel receipt.

        https://talkbank.atlassian.net/wiki/spaces/BAAS/pages/1404567563
        /selfemployments+cancel+receipt
        """
        body = {
            'ReceiptId': receipt_id,
            'Reason': reason.value,
        }
        api_name = 'cancel_receipt'
        api_url_parameters = {CLIENT_ID: client_id}
        json_body = json.dumps(body)
        headers = self._get_headers(
            api_name, 'DELETE', json_body, api_url_parameters,
        )
        url = self.get_full_url(api_name, **api_url_parameters)
        response = requests.delete(url, data=json_body, headers=headers)
        response_dict = response.json()
        status = response_dict.get('status', 'error')
        self._raise_exception(
            response.status_code,
            response_dict.get(DESCRIPTION, DEFAULT_EXCEPTION_MESSAGE),
            response_dict.get(ERRORS),
            status,
        )

    def transfer(  # noqa: WPS211
        self,
        amount: Decimal,
        account: str,
        bik: str,
        name: str,
        inn: str,
        description: Optional[str] = None,
        order_slug: Optional[str] = None,
        receipt_id: Optional[str] = None,
        beneficiary_id: Optional[str] = None,
    ) -> 'TransferResult':
        """Pay to client account.

        https://talkbank.atlassian.net/wiki/spaces/BAAS/pages/1221099580
        /payment+to+account
        """
        kopecks = int(amount.quantize(Decimal('0.00')) * 100)
        body = {
            'amount': kopecks,
            'account': account,
            'bik': bik,
            'name': name,
            'inn': inn,
        }
        if description:
            body[DESCRIPTION] = description
        if order_slug:
            body['order_slug'] = order_slug
        if receipt_id:
            body['receipt_id'] = receipt_id
        if beneficiary_id:
            body['beneficiary_id'] = beneficiary_id
        api_name = 'transfer'
        json_body = json.dumps(body)
        headers = self._get_headers(api_name, 'POST', json_body)
        url = self.get_full_url(api_name)
        response = requests.post(url, data=json_body, headers=headers)
        response_dict = response.json()
        self._raise_exception(
            response.status_code,
            response_dict.get(DESCRIPTION, DEFAULT_EXCEPTION_MESSAGE),
            response_dict.get(ERRORS),
        )
        response_dict['talk_bank_commission'] = self._kopecks_to_rubs(
            response_dict['talkbank_commission'],
        )
        response_dict.pop('talkbank_commission')
        response_dict['beneficiary_partner_commission'] = (
            self._kopecks_to_rubs(
                response_dict['beneficiary_partner_commission'],
            )
        )
        return TransferResult(**response_dict)

    def get_transfer_status(self, order_slug) -> 'TransferResult':
        """Return status of payment to client account.

        https://talkbank.atlassian.net/wiki/spaces/BAAS/pages/1221427222
        /payment+to+account+status
        """
        body = ''
        api_name = 'get_transfer_status'
        api_url_parameters = {'order_slug': order_slug}
        headers = self._get_headers(api_name, 'GET', body, api_url_parameters)
        url = self.get_full_url(api_name, order_slug=order_slug)
        response = requests.get(url, headers=headers)
        response_dict = response.json()
        self._raise_exception(
            response.status_code,
            response_dict.get(DESCRIPTION, DEFAULT_EXCEPTION_MESSAGE),
            response_dict.get(ERRORS),
        )
        response_dict['talk_bank_commission'] = self._kopecks_to_rubs(
            response_dict['talkbank_commission'],
        )
        response_dict.pop('talkbank_commission')
        response_dict['beneficiary_partner_commission'] = (
            self._kopecks_to_rubs(
                response_dict['beneficiary_partner_commission'],
            )
        )
        return TransferResult(**response_dict)

    def get_event_subscriptions(self) -> SubscriptionStatus:
        body = ''
        api_name = 'event_subscriptions'
        headers = self._get_headers(api_name, 'GET', body)
        url = self.get_full_url(api_name)
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        return SubscriptionStatus(
            enabled=[EventSubscription(**params) for params in data['enabled']], available=data['available']
        )

    def subscribe_for_events(self, url: str, events: list[str]) -> SubscriptionStatus:
        body = {
            'url': url,
            'events': events,
        }
        json_body = json.dumps(body)
        api_name = 'event_subscriptions'
        headers = self._get_headers(api_name, 'POST', json_body)
        url = self.get_full_url(api_name)
        response = requests.post(url, headers=headers, data=json_body)
        response.raise_for_status()
        data = response.json()
        return SubscriptionStatus(
            enabled=[EventSubscription(**params) for params in data['enabled']], available=data['available']
        )

    def delete_subscription(self, subscription_id: int) -> SubscriptionStatus:
        api_name = 'delete_event_subscription'
        headers = self._get_headers(api_name, 'DELETE', '', api_url_parameters={'subscription_id': str(subscription_id)})
        url = self.get_full_url(api_name, subscription_id=str(subscription_id))
        response = requests.delete(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        return SubscriptionStatus(
            enabled=[EventSubscription(**params) for params in data['enabled']], available=data['available']
        )

    def create_value_for_authorization_header(
        self, method: str, api_url: str, request_date_time: str, body: str,
    ) -> str:
        """Create value for authorization header.

        https://talkbank.atlassian.net/wiki/spaces/BAAS/pages/616726625
        """
        method = str(method).upper()
        request_path, _, query_string = api_url.partition('?')

        result_list = []
        result_list.append(method)
        result_list.append(request_path)

        items = query_string.split('&')  # noqa: WPS110
        items.sort()
        sorted_query_string = '&'.join(items)
        result_list.append(sorted_query_string)

        result_list.append(f"date:{request_date_time}")

        hash_body = self.get_hash_sha256(body)
        result_list.append(f"tb-content-sha256:{hash_body}")
        result_list.append(hash_body)
        result_string = '\n'.join(result_list)
        signature = self.create_sha256_signature(result_string)
        return f"TB1-HMAC-SHA256 {self.partner_id}:{signature}"

    def create_sha256_signature(self, message: str) -> str:
        """Return HMAC in hex form using SHA-256 hash algorithm.

        https://talkbank.atlassian.net/wiki/spaces/BAAS/pages/616726625
        """
        message = message.encode()
        new_hmac = hmac.new(
            self.partner_token.encode(), message, hashlib.sha256,
        )
        return new_hmac.hexdigest()

    def get_hash_sha256(self, text: str) -> str:
        """Return hash in hex form using SHA-256 hash algorithm."""
        sha256 = hashlib.sha256()
        sha256.update(text.encode())
        return sha256.hexdigest()

    def get_full_url(self, api_name: str, **kwargs) -> str:
        """Return url consisting of the base url and api url."""
        api_url = self._get_api_url(api_name, **kwargs)
        return f'{self.base_url}{api_url}'

    def _get_api_url(self, api_name: str, **kwargs) -> str:
        return self.api_dict.get(api_name).format(**kwargs)

    def _get_headers(
        self,
        api_name: str,
        http_method: str,
        body: str,
        api_url_parameters: Optional[Dict[str, str]] = None,
    ) -> Dict[str, str]:
        if api_url_parameters is None:
            api_url_parameters = {}
        api_url = self._get_api_url(api_name, **api_url_parameters)
        hash_body = self.get_hash_sha256(body)
        now_rfc7231 = datetime.datetime.utcnow().strftime(
            "%a, %d %b %Y %X GMT",
        )
        authorization = self.create_value_for_authorization_header(
            http_method, api_url, now_rfc7231, body,
        )
        return {
            'Content-Type': 'application/json',
            'TB-Content-SHA256': hash_body,
            'Date': now_rfc7231,
            'Authorization': authorization,
        }

    def _register_income(self, client_id: str, json_body: str) -> str:
        """Register selfemployments income.

        https://talkfinancetech.atlassian.net/wiki/spaces/BAAS/pages/3081772/2.0+selfemployments+add+receipt+async
        """
        api_name = 'register_income'
        api_url_parameters = {CLIENT_ID: client_id}
        headers = self._get_headers(
            api_name, 'POST', json_body, api_url_parameters,
        )
        url = self.get_full_url(api_name, client_id=client_id)
        response = requests.post(url, data=json_body, headers=headers)
        response_dict = response.json()
        print(response_dict)
        status = response_dict.get('status', 'error')
        if response.status_code != HTTPStatus.OK or status == 'error':
            raise TalkBankExceptionError(
                response_dict.get(DESCRIPTION, DEFAULT_EXCEPTION_MESSAGE),
                status_code=response.status_code,
                errors=response_dict.get(ERRORS),
            )
        data = response_dict['data']  # noqa: WPS 110
        return data['Id']

    def _kopecks_to_rubs(self, kopecks: Union[int, None]) -> Decimal:
        if kopecks is None:
            return Decimal('0.00')
        return Decimal(str(kopecks / 100))

    def _raise_exception(
        self,
        status_code: int,
        message: str,
        errors: List[str],
        status: str = 'success',
    ) -> None:

        def _raise(ExceptionClass):
            raise ExceptionClass(message, status_code, errors)

        if status_code == HTTPStatus.OK:
            if status == 'error':
                _raise(TalkBankExceptionError)

        if status_code == HTTPStatus.BAD_REQUEST:
            _raise(BadRequestError)

        elif status_code == HTTPStatus.FORBIDDEN:
            if message == 'Access Denied.':
                _raise(AccessDeniedError)
            else:
                _raise(ForbiddenError)

        elif status_code == HTTPStatus.UNPROCESSABLE_ENTITY:
            if len(errors) == 1:
                if errors[0][-20:] == 'phone already exists':
                    _raise(ClientWithSuchPhoneAlreadyExistsError)
                elif errors[0][-14:] == 'already exists':
                    _raise(ClientAlreadyExistsError)

            _raise(TalkBankExceptionError)

        elif status_code == HTTPStatus.INTERNAL_SERVER_ERROR:
            _raise(InternalServerError)


def create_talk_bank_client():
    return TalkBankClient(TB_BASE_URL, TB_PARTNER_ID, TB_PARTNER_TOKEN)

