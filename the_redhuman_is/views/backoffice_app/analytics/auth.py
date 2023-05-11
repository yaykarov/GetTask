from django.contrib.auth.models import (
    AnonymousUser,
    User,
)
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from rest_framework import status
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
)
from rest_framework.fields import CharField
from rest_framework.serializers import Serializer


ANALYTICS_GROUP = 'Аналитика'


class AuthSerializer(Serializer):
    login = CharField()
    password = CharField()


def _authenticate(login, password):
    try:
        allowed_users = User.objects.filter(
            Q(is_superuser=True) |
            Q(groups__name=ANALYTICS_GROUP)
        ).distinct(
            'pk'
        )
        user = allowed_users.get(username=login)
    except User.DoesNotExist:
        User().set_password(password)
    else:
        if user.check_password(password) and user.is_active:
            return user
    return AnonymousUser()


def analytics_api(http_methods, atomic=False):
    def decorator(view_func):
        def _view_func_with_check(request, *args, **kwargs):
            serializer = AuthSerializer(data=request.GET)
            serializer.is_valid(raise_exception=True)
            user = _authenticate(**serializer.validated_data)
            if not user.is_authenticated:
                return JsonResponse(data={}, status=status.HTTP_401_UNAUTHORIZED)
            request.user = user
            return view_func(request, *args, **kwargs)

        @api_view(http_methods)
        @authentication_classes([])
        @permission_classes([])
        def proxy(*args, **kwargs):
            if atomic:
                with transaction.atomic():
                    return _view_func_with_check(*args, **kwargs)
            else:
                return _view_func_with_check(*args, **kwargs)

        return proxy
    return decorator
