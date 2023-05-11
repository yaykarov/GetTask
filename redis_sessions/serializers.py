from .conf import settings

try:
    import ujson

    class UjsonSerializer(object):
        def dumps(self, obj):
            return ujson.dumps(obj).encode(
                settings.SESSION_REDIS_JSON_ENCODING
            )

        def loads(self, data):
            return ujson.loads(
                data.decode(settings.SESSION_REDIS_JSON_ENCODING)
            )
except ImportError:
    pass
