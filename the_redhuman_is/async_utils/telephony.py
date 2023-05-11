import json
from datetime import (
    datetime,
    time,
    timedelta,
)

from django.utils import timezone

from voximplant.apiclient import (
    VoximplantAPI,
    VoximplantException
)


CREDENTIALS_FILENAME = None
ACCOUNT_ID = None
API_KEY = None

try:
    from .telephony_local import *
except ImportError:
    pass


api = None
try:
    api = VoximplantAPI(CREDENTIALS_FILENAME)
except (FileNotFoundError, TypeError):
    pass

MAIN_RULE_ID = 7353

URL_SUFFIX = ''
if ACCOUNT_ID is not None and API_KEY is not None:
    URL_SUFFIX = f'&api_key={API_KEY}&account_id={ACCOUNT_ID}'


def start_call(username, display_name, phones):
    data = {
        'make_call': {
            'from': username,
            'to': phones,
            'display_name': display_name
        }
    }
    try:
        res = api.start_scenarios(MAIN_RULE_ID, script_custom_data=json.dumps(data))
    except VoximplantException as e:
        print('Telephony error: {}'.format(e.message))


def _do_get_history(from_timepoint, to_timepoint):
    COUNT = 50
    offset = 0
    result = []

    has_more = True
    while has_more:
        chunk = api.get_call_history(
            from_timepoint,
            to_timepoint,
            with_calls=True,
            offset=offset,
            count=COUNT,
            with_total_count=False, # this is faster somehow (~10%)
        )
        result.extend(chunk['result'])
        offset += COUNT
        has_more = len(chunk['result']) == COUNT

    return result


# 'out_click_to_call', 'out_manual', 'inc', 'unknown'
def _call_info(history_item):
    call_type = 'unknown'

    calls = history_item['calls']
    if history_item.get('custom_data') is None:
        for call in calls:
            if call['incoming']:
                number_type = call['remote_number_type'].lower()
                if number_type == 'user':
                    call_type = 'out_manual'
                elif number_type == 'pstn':
                    call_type = 'inc'
    else:
        call_type = 'out_click_to_call'

    users = []
    phones = []
    user_successful = False
    phone_successful = False
    duration = 0
    record_urls = []

    for call in calls:
        number_type = call['remote_number_type'].lower()
        number = call['remote_number']
        call_successful = call['successful']
        call_record_url = call.get('record_url')
        if call_record_url:
            record_urls.append(call_record_url + URL_SUFFIX)

        if number_type == 'user':
            if call_successful:
                user_successful = True
                users = [number]
            elif not user_successful:
                users.append(number)
        elif number_type == 'pstn':
            if call_successful:
                phone_successful = True
                duration = call['duration']
                phones = [number]
            elif not phone_successful:
                phones.append(number)
        else:
            # ignore for now
            print(f'Unknown number type {number_type}')

    successful = user_successful and phone_successful

    return {
        'start_time': timezone.localtime(history_item['start_date']),
        'call_type': call_type,
        'users': users,
        'phones': phones,
        'successful': successful,
        'duration': duration,
        'total_duration': history_item['duration'],
        'record_urls': record_urls,
    }


def get_call_history(first_day, last_day):
    from_timepoint = timezone.make_aware(
        datetime.combine(
            first_day,
            time()
        )
    )
    to_timepoint = timezone.make_aware(
        datetime.combine(
            last_day + timedelta(days=1),
            time()
        )
    )

    history = _do_get_history(from_timepoint, to_timepoint)
    return [_call_info(item) for item in history]
