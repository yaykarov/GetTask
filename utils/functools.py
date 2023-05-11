import decimal
import operator

from distutils.util import strtobool as to_bool

from itertools import (
    filterfalse,
    groupby,
    tee,
)

import re


def nothing(_):
    return _


def strtobool(value):
    if isinstance(value, bool):
        return value

    if not isinstance(value, str):
        return None

    value = value.lower()

    try:
        return bool(to_bool(value))
    except ValueError:
        if value == '-1':
            return False

        if value in ('', 'null', 'none'):
            return None

        raise


def strtodecimal(value):
    if not isinstance(value, str):
        return None

    value = re.sub('\s+', '', value.lower().replace(',', '.'))

    return decimal.Decimal(value)


def partition(pred, iterable):
    """
    Use a predicate to partition entries into false entries and true entries
    https://docs.python.org/dev/library/itertools.html#itertools-recipes
    """
    # partition(is_odd, range(10)) --> 0 2 4 6 8   and  1 3 5 7 9
    t1, t2 = tee(iterable)
    return filterfalse(pred, t1), filter(pred, t2)


def all_equal(iterable):
    """
    Returns True if all the elements are equal to each other
    https://docs.python.org/3/library/itertools.html#itertools-recipes
    """
    g = groupby(iterable)
    return next(g, True) and not next(g, False)


def pairwise(iterable):
    """
    s -> (s0,s1), (s1,s2), (s2, s3), ...
    https://docs.python.org/3/library/itertools.html#itertools-recipes
    """
    a, b = tee(iterable)
    next(b, None)
    return zip(a, b)


def merge_dicts(*args, function=operator.add):
    iterator = iter(args)
    res = next(iterator)
    for arg in iterator:
        for key, value in arg.items():
            try:
                res[key] = function(res[key], arg[key])
            except KeyError:
                res[key] = arg[key]
    return res


class LazyInstance:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        self.instance = None

    def __get__(self, obj, cls):
        if self.instance is None:
            self.instance = cls.objects.get(*self.args, **self.kwargs)

        return self.instance
