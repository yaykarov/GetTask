import decimal
import functools
import math
import re


ZERO_OO = decimal.Decimal('0.00')


def get_decimal(value):
    try:
        value = decimal.Decimal(value.replace(',', '.'))
    except decimal.InvalidOperation as e:
        value = 0

    return value


def get_int(value):
    try:
        value = int(value)
    except Exception as e:
        value = None

    return value


def separate(key):
    try:
        if isinstance(key, int):
            integer = str(key)
            decimal_num = ""
        elif isinstance(key, float):
            key = "{:.1f}".format(key)
            integer = key[:-2]
            decimal_num = key[-1:]
        elif key is None:
            return '0,00'
        else:
            rx = re.compile("^([\d-]+)[,.]?(\d*)$")
            m = rx.match(str(key))
            if m:
                integer = m.group(1)
                decimal_num = m.group(2)
            else:
                integer = key
                decimal_num = ""
        result = re.sub(r"\B(?=(?:\d{3})+$)", "\u202F", integer)
        if decimal_num:
            result += ("," + decimal_num)
        return result
    except Exception as e:
        pass
    return key


def _lcm_pair(a, b):
    return abs(a * b) // math.gcd(a, b)


def lcm(*args):
    return functools.reduce(_lcm_pair, args)
