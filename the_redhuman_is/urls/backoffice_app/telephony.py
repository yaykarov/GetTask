# -*- coding: utf-8 -*-

from django.urls import path

from the_redhuman_is.views import delivery


urlpatterns = [
    path(
        'operators_for_driver/',
        delivery.operators_for_driver,
        name='telephony_operators_for_driver'
    ),
]
