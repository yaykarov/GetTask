import os

from appconf import AppConf
from django.conf import settings  # noqa


class SessionRedisConf(AppConf):
    HOST = '127.0.0.1'

    PORT = 6379

    DB = 0

    PREFIX = 'django_sessions'

    PASSWORD = None

    UNIX_DOMAIN_SOCKET_PATH = None

    URL = None

    CONNECTION_POOL = None

    JSON_ENCODING = 'latin-1'

    ENV_URLS = (
        'REDISCLOUD_URL',
        'REDISTOGO_URL',
        'OPENREDIS_URL',
        'REDISGREEN_URL',
        'MYREDIS_URL',
    )

    def configure(self):
        if self.configured_data['URL'] is None:
            for url in self.configured_data['ENV_URLS']:
                redis_env_url = os.environ.get(url)
                if redis_env_url:
                    self.configured_data['URL'] = redis_env_url
                    break

        return self.configured_data

    class Meta:
        prefix = 'session_redis'
