from django.urls import path

from the_redhuman_is.views.backoffice_app.rocketchat_webhook import on_new_message


urlpatterns = [
    path(
        'on_new_message/',
        on_new_message,
        name='rocketchat_webhook_on_new_message'
    ),
]
