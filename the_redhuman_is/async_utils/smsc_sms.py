import requests
from urllib.parse import urlencode

API_URL = 'https://smsc.ru/sys/send.php'

LOGIN = 'login'
PASSWORD = 'password'

try:
    from .smsc_sms_local import *
except ImportError:
    pass


def send_sms(sender, target, message, sms_id=None):
    params = {
        'login': LOGIN,
        'psw': PASSWORD,
        'phones': '+' + target,
        'mes': message,
        'charset': 'utf-8'
    }
    if sms_id is not None:
        params['id'] = sms_id

    request_url = API_URL + "?" + urlencode(params)
    return requests.get(request_url)
