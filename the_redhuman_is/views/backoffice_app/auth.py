from django.contrib.auth import (
    authenticate,
    login as auth_login,
)
from django.core.exceptions import PermissionDenied

from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
)
from rest_framework.fields import CharField
from rest_framework.serializers import Serializer
from rest_framework_simplejwt.tokens import RefreshToken


class AuthSerializer(Serializer):
    username = CharField()
    password = CharField()


@csrf_exempt
@api_view(['POST'])
@authentication_classes([])
@permission_classes([])
def login(request):
    serializer = AuthSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    username = serializer.validated_data['username']
    password = serializer.validated_data['password']
    user = authenticate(request, username=username, password=password)

    if user is None or not user.is_active:
        raise PermissionDenied('Неверные учетные данные.')

    auth_login(request, user)
    refresh = RefreshToken.for_user(user)
    return JsonResponse(
        {
            'access_token': str(refresh.access_token),
            'refresh_token': str(refresh)
        }
    )


def bo_api(http_methods, atomic=False):
    def decorator(view_func):

        @api_view(http_methods)
        def proxy(*args, **kwargs):
            if atomic:
                with transaction.atomic():
                    return view_func(*args, **kwargs)
            else:
                return view_func(*args, **kwargs)

        return proxy

    return decorator
