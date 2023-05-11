from functools import wraps

from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
)
from rest_framework.fields import CharField
from rest_framework.serializers import Serializer
from rest_framework_simplejwt.tokens import RefreshToken

from the_redhuman_is.auth import IsCustomer


def customer_api(http_methods, atomic=False):
    def decorator(view_func):

        @api_view(http_methods)
        @permission_classes([IsCustomer])
        def proxy(*args, **kwargs):
            if atomic:
                with transaction.atomic():
                    return view_func(*args, **kwargs)
            else:
                return view_func(*args, **kwargs)

        return wraps(view_func)(proxy)

    return decorator


class AuthSerializer(Serializer):
    email = CharField()
    password = CharField()


@csrf_exempt
@api_view(['POST'])
@authentication_classes([])
@permission_classes([])
def get_token(request):
    serializer = AuthSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    email = serializer.validated_data['email']
    password = serializer.validated_data['password']
    try:
        user = User.objects.get(
            customeraccount__isnull=False,
            email=email
        )
    except User.DoesNotExist:
        User().set_password(password)
        raise PermissionDenied('Неверные учетные данные.')
    else:
        if not (user.check_password(password) and user.is_active):
            raise PermissionDenied('Неверные учетные данные.')

    refresh = RefreshToken.for_user(user)
    return JsonResponse(
        {
            'access_token': str(refresh.access_token),
        }
    )
