# -*- coding: utf-8 -*-

import json
import requests


TIMEOUT_SEC = 10

API_KEY = None
SECRET_KEY = None

try:
    from .dadata_local import *
except ImportError:
    pass

session = requests.Session()
session.headers.update(
    {
        'Content-type': 'application/json',
        'Accept': 'application/json',
        'Authorization': f'Token {API_KEY}', 
        'X-Secret': SECRET_KEY,
    }
)


def clean_address(address):
    url = 'https://cleaner.dadata.ru/api/v1/clean/address'
    response = session.post(
        url,
        data=json.dumps([address]),
        timeout=TIMEOUT_SEC
    )
    response.raise_for_status()

    return response.json()
