# -*- coding: utf-8 -*-

from django.conf.urls import include
from django.conf.urls import url


urlpatterns = [
    url(
        r'^itella/',
        include('the_redhuman_is.urls.customer_specific.itella')
    ),
    url(
        r'^kuehne_nagel/',
        include('the_redhuman_is.urls.customer_specific.kuehne_nagel')
    ),
    url(
        r'^kari/',
        include('the_redhuman_is.urls.customer_specific.kari')
    ),
    url(
        r'^vkusvill/',
        include('the_redhuman_is.urls.customer_specific.vkusvill')
    ),
]
