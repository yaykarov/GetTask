# -*- coding: utf-8 -*-

import re
import requests

from collections import OrderedDict
from hashlib import md5

PUBLIC_KEY = ''
PRIVATE_KEY = ''

try:
    from .atomic_sms_local import *
except ImportError:
    pass


def _calc_control_sum(params, action):
    tmp = dict(params)
    tmp['version'] = '3.0'
    tmp['action'] = action
    p = OrderedDict(sorted(tmp.items()))
    params = ''
    for k, v in p.items():
        params += str(v)
    params += PRIVATE_KEY
    return md5(params.encode()).hexdigest()


def send_sms(sender, target, message):
    params = {
        'key': PUBLIC_KEY,
        'sender': sender,
        'phone': target,
        'text': message,
        'sms_lifetime': 0,
    }
    params['sum'] = _calc_control_sum(params, 'sendSMS')
    return requests.post('http://api.atompark.com/api/sms/3.0/sendSMS', data=params)
