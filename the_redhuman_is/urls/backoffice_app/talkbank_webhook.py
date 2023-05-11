from django.urls import path

from the_redhuman_is.views.backoffice_app.talkbank_webhook import on_income_registered


urlpatterns = [
    path('on_income_registered/', on_income_registered, name='talkbank_webhook_on_income_registered'),
]
