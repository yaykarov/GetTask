from datetime import datetime

from django import template
from django.contrib.auth.models import Group

register = template.Library()


@register.filter
def get_value_from_dict(dict_data, key):
    return dict_data.get(key)


@register.filter
def get_value(container, key):
    return container[key]


@register.filter
def has_group(user, group_name):
    group = Group.objects.get(name=group_name)
    return group in user.groups.all()


@register.filter
def get_time_delta(date):
    if date:
        delta = datetime.now().date() - date.date()
        return delta.days
    else:
        return '-'


@register.inclusion_tag('yes_no.html')
def yes_no(value):
    return {'value': value}


# Todo: reomve this
@register.filter
def lookup(d, key):
    return d[key]
