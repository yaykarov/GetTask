# -*- coding: utf-8 -*-

from django import template

from utils.date_time import dhms
from utils.numbers import separate as do_separate


register = template.Library()


@register.filter
def separate(key):
    return do_separate(key)


@register.filter
def short_interval(interval):
    days, hours, minutes, seconds = dhms(interval)
    hours += 24 * days
    return '{:02d}:{:02d}'.format(hours, minutes)
