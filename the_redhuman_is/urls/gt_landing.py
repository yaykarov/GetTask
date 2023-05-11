# -*- coding: utf-8 -*-

from django.conf.urls import url

from the_redhuman_is.views import delivery


urlpatterns = [
    url(
        r'^calc_request/$',
        delivery.calc,
        name='gt_landing_calc_request'
    ),
    url(
        r'^create_request/$',
        delivery.create_request_from_landing,
        name='gt_landing_create_request'
    ),
]
