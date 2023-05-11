from functools import wraps
from importlib import import_module

from .conf import settings

try:  # Python 2.*
    from django.utils.encoding import force_unicode
except ImportError:  # Python 3.*
    from django.utils.encoding import force_text
    force_unicode = force_text


def add_prefix(key):
    if settings.SESSION_REDIS_PREFIX:
        if not force_unicode(key).startswith(
            '%s:' % settings.SESSION_REDIS_PREFIX
        ):
            return '%s:%s' % (
                settings.SESSION_REDIS_PREFIX,
                key
            )

    return key


def remove_prefix(key):
    if settings.SESSION_REDIS_PREFIX:
        key = str(key)

        if key.startswith(settings.SESSION_REDIS_PREFIX):
            key = key.replace(
                '%s:' % settings.SESSION_REDIS_PREFIX, '', 1
            )

    return key


def prefix(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        args = list(args)
        args[0] = add_prefix(args[0])
        return fn(*args, **kwargs)
    return wrapped


def import_by_path(dotted_path):
    try:
        module_path, class_name = dotted_path.rsplit('.', 1)

        module = import_module(module_path)

        attr = getattr(module, class_name)
    except (ValueError, ImportError, AttributeError):
        raise ImportError('can not import %s' % dotted_path)

    return attr


def total_seconds(dt):
    if hasattr(dt, 'total_seconds'):
        return dt.total_seconds()
    else:
        return (
            (dt.microseconds + (dt.seconds + dt.days * 24 * 3600) * 10 ** 6)
            /
            10 ** 6
        )
