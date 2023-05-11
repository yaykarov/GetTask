import re

from django.core.exceptions import ValidationError

_HAS_DIGIT = re.compile('.*\d.*')
_WRONG_PHONE_RX = re.compile('8(\d{10})')


def normalized_phone(phone, strict=False):
    if not phone:
        return None
    m = _HAS_DIGIT.match(phone)
    if not m and not strict:
        return phone
    phone = re.sub('\D', '', phone)
    if not phone:
        return None
    m = _WRONG_PHONE_RX.match(phone)
    if m:
        phone = '7' + m.group(1)
    if phone and len(phone) < 11 and phone[0] != '7':
        phone = '7' + phone
    return phone


class PhonePrefixLengthValidator:
    PHONE_LENGTHS = {
        '7': 11,  # Россия, Казахстан
        '996': 12,  # Киргизия
        '998': 12,  # Узбекистан
        '380': 12,  # Украина
        '375': 12,  # Белоруссия
        '992': 12,  # Таджикистан
        '374': 11,  # Армения
        '373': 11,  # Молдавия
        '995': 12,  # Грузия
        '993': 11,  # Туркмения
    }
    messages = {
        'length_mismatch': 'Для этой страны номер телефона должен содержать %(length)s цифр.',
        'unknown_code': 'Неизвестный код страны.',
    }

    def __call__(self, value):
        for prefix, length in self.PHONE_LENGTHS.items():
            if value.startswith(prefix):
                if len(value) == length:
                    return value
                else:
                    raise ValidationError(
                        self.messages['length_mismatch'],
                        code='length_mismatch',
                        params={'length': length}
                    )
        raise ValidationError(self.messages['unknown_code'], code='unknown_code')


def extract_phones(phones):
    result = []

    if phones is None:
        return result

    # Todo: some exceptions?
    phones = re.sub(',\s+', ',', phones)
    phones = re.sub('\s+,', ',', phones)
    phones = re.sub('\s*\(', '', phones)
    phones = re.sub('\)\s*', '', phones)

    splitted = phones.split(',')

    if len(splitted) == 1:
        phones = re.sub('\D', '', phones)
        while len(phones) >= 11:
            result.append(normalized_phone(phones[:11]))
            phones = phones[11:]
    else:
        for phone in splitted:
            if phone:
                result.append(normalized_phone(phone))

    return result


_RUS_PHONE_RX = re.compile('^7\d{10}')


def is_it_russian_phone(text):
    if text:
        m = _RUS_PHONE_RX.match(text)
        if m:
            return True
    return False


def format_phone(phone):
    return '+' + normalized_phone(phone)


def format_phones(phones):
    return ', '.join([format_phone(phone) for phone in extract_phones(phones)])
