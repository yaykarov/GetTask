from django.contrib.sessions.backends.base import CreateError

from . import connection
from .utils import force_unicode, prefix


@prefix
def expire(key):
    return connection.redis_server.ttl(key)


@prefix
def keys(pattern):
    return connection.redis_server.keys(pattern)


@prefix
def get(key):
    value = connection.redis_server.get(key)

    value = force_unicode(value)

    return value


@prefix
def exists(key):
    return connection.redis_server.exists(key)


@prefix
def delete(key):
    return connection.redis_server.delete(key)


@prefix
def save(key, expire, data, must_create):
    expire = int(expire)

    data = force_unicode(data)

    if must_create:
        if connection.redis_server.setnx(key, data):
            connection.redis_server.expire(key, expire)
        else:
            raise CreateError
    else:
        connection.redis_server.setex(key, expire, data)
