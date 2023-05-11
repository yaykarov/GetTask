# -*- coding: utf-8 -*-

import googlemaps


API_KEY = None

try:
    from .googlemaps_local import *
except ImportError:
    pass


_client = None

try:
    _client = googlemaps.Client(key=API_KEY)
except Exception as e:
    print(e)


def geocode(address):
    return _client.geocode(
        address,
        language='ru'
    )
