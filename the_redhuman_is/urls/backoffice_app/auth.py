from django.urls import path

from the_redhuman_is.views.backoffice_app import auth

urlpatterns = [
    # Login
    path(
        'login/',
        auth.login,
        name='backoffice_auth_login'
    ),
]
