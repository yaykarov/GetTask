# -*- coding: utf-8 -*-

from django.conf.urls import include
from django.urls import path

urlpatterns = [
    path('api/v0/', include('the_redhuman_is.urls.mobile_app.api_v0')),
    path('api/v2/', include('the_redhuman_is.urls.mobile_app.api_v2')),
    path('api/v2/', include('the_redhuman_is.urls.mobile_app.partners')),
]
