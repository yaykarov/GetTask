# -*- coding: utf-8 -*-

import datetime
import requests

from urllib.parse import urlencode, quote_plus


LOGIN = 'login'
PASSWORD = 'password'

try:
    from .uiscom_local import *
except ImportError:
    pass


def _get_session_key():
    url = 'https://api.comagic.ru/api/login/?login={}&password={}'.format(
        LOGIN,
        PASSWORD
    )

    result = requests.get(url)
    return result.json()['data']['session_key']


def _logout(session_key):
    url = 'http://api.comagic.ru/api/logout/?session_key={}'.format(session_key)
    result = requests.get(url)
    return result.json()['success']


def _get_missed_calls(session_key, date_from, date_till):
    FORMAT = '%Y-%m-%d %H:%M:%S'
    url = 'https://api.comagic.ru/api/v1/call/?session_key={}&date_from={}&date_till={}'.format(
        session_key,
        quote_plus(date_from.strftime(FORMAT)),
        quote_plus(date_till.strftime(FORMAT))
    )
    result = requests.get(url)
    missed_calls = []
    for call in result.json()['data']:
        if call['status'] == 'lost':
            missed_calls.append((call['numa'], call['numb'], call['call_date']))

    return missed_calls


def get_missed_calls(date_from, date_till):
    key = _get_session_key()
    missed_calls = _get_missed_calls(key, date_from, date_till)
    _logout(key)
    return missed_calls

