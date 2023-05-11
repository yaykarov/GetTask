from django.urls import path

from the_redhuman_is.views.customer_api import auth

urlpatterns = [
    path(
        'token/',
        auth.get_token,
        name='gt_customer_api_v1_auth_token'
    ),
]
