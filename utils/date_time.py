# -*- coding: utf-8 -*-
import datetime
import logging
import pytz
import re
import time


TIME_FORMAT = '%H:%M'
DATE_FORMAT = '%d.%m.%Y'
POSTGRES_JSON_DATETIME_FORMAT = '%Y-%m-%dT%H:%M:%S.%f%z'
POSTGRES_JSON_TIME_FORMAT = '%H:%M:%S'


def as_default_timezone(timepoint):
    return timepoint.astimezone(pytz.timezone('Europe/Moscow'))


def get_today_date():
    return datetime.datetime.combine(datetime.date.today(), datetime.time(0, tzinfo=pytz.utc))


def get_tomorrow_date():
    return get_today_date() + datetime.timedelta(days=1)


# [] - inclusive
def first_last_day_from_month(year, month):
    first_day = datetime.date(day=1, month=month, year=year)
    if month == 12:
        last_day = datetime.date(day=31, month=month, year=year)
    else:
        last_day = datetime.date(
            day=1, month=month + 1, year=year
        ) - datetime.timedelta(days=1)

    return first_day, last_day


# [] - inclusive
def months(first_day, last_day):
    count = (last_day.year - first_day.year) * 12 + last_day.month - first_day.month + 1

    months = []
    for m in range(count):
        year = first_day.year + int((first_day.month + m - 1) / 12)
        month = ((first_day.month + m - 1) % 12) + 1

        months.append((year, month))

    return months


def split_by_months(first_day, last_day):
    _months = months(first_day, last_day)
    if len(_months) == 1:
        return [(first_day, last_day)]

    intervals = []

    # first month
    year, month = _months[0]
    _, m_last_day = first_last_day_from_month(year, month)
    intervals.append((first_day, m_last_day))

    full_months = _months[1:-1]
    for year, month in full_months:
        m_first_day, m_last_day = first_last_day_from_month(year, month)
        intervals.append((m_first_day, m_last_day))

    # last month
    year, month = _months[-1]
    m_first_day, _ = first_last_day_from_month(year, month)
    intervals.append((m_first_day, last_day))

    return intervals


def date_from_string(date):
    if not date:
        return None
    return datetime.datetime.strptime(date, DATE_FORMAT).date()


def date_time_from_string(date):
    if not date:
        return None
    return datetime.datetime.combine(date_from_string(date), datetime.time(0, tzinfo=pytz.utc))


def string_from_date(date):
    if not date:
        return None
    return date.strftime(format=DATE_FORMAT)


def dhms(interval):
    hours, remainder = divmod(interval.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return interval.days, hours, minutes, seconds


def time_interval_format(interval, nbsp=False):
    text = ''
    days, hours, minutes, seconds = dhms(interval)
    if days != 0:
        text += '{} д '.format(days)
    text += '{:02d}:{:02d}'.format(hours, minutes)

    if nbsp:
        text = re.sub('\s', '&nbsp;', text)

    return text


def days_from_interval(first_day, last_day):
    return [
        first_day + datetime.timedelta(days=d) for d in range(0, (last_day-first_day).days + 1)
    ]


def day_month_year(date):
    months_names = [
        'января',
        'февраля',
        'марта',
        'апреля',
        'мая',
        'июня',
        'июля',
        'августа',
        'сентября',
        'октября',
        'ноября',
        'декабря',
    ]
    month = months_names[date.month - 1]

    if date.day < 10:
        day = f'0{date.day}'
    else:
        day = str(date.day)

    return day, month, str(date.year)


def postgres_str_to_datetime(datetime_string: str) -> datetime:
    return datetime.datetime.strptime(datetime_string, POSTGRES_JSON_DATETIME_FORMAT)


def str_to_time(string):
    return datetime.datetime.strptime(string, POSTGRES_JSON_TIME_FORMAT).time()


class UTCFormatter(logging.Formatter):
    converter = time.gmtime
    default_msec_format = '%s.%03d'

    @classmethod
    def format_time(cls, epoch_ts):
        ts = cls.converter(epoch_ts)
        t = time.strftime(cls.default_time_format, ts)
        s = cls.default_msec_format % (t, (epoch_ts - int(epoch_ts)) * 1000)
        return s
