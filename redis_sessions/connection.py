import redis

from .conf import settings
from .utils import import_by_path


def get_redis_server():
    if settings.SESSION_REDIS_CONNECTION_POOL is not None:
        return redis.StrictRedis(
            connection_pool=import_by_path(
                settings.SESSION_REDIS_CONNECTION_POOL
            )
        )

    if settings.SESSION_REDIS_URL is not None:
        return redis.StrictRedis.from_url(
            settings.SESSION_REDIS_URL
        )

    if settings.SESSION_REDIS_UNIX_DOMAIN_SOCKET_PATH is not None:
        return redis.StrictRedis(
            unix_socket_path=settings.SESSION_REDIS_UNIX_DOMAIN_SOCKET_PATH,
            db=settings.SESSION_REDIS_DB,
            password=settings.SESSION_REDIS_PASSWORD
        )

    return redis.StrictRedis(
        host=settings.SESSION_REDIS_HOST,
        port=settings.SESSION_REDIS_PORT,
        db=settings.SESSION_REDIS_DB,
        password=settings.SESSION_REDIS_PASSWORD
    )


redis_server = get_redis_server()
