# -*- coding: utf-8 -*-

from django.conf.urls import url

from the_redhuman_is.views.customer_specific import kari

urlpatterns = [
    url(
        r'^$',
        kari.management_page,
        name='kari_management_page'
    ),
    url(
        r'^import_performance_file/$',
        kari.import_performance_file,
        name='kari_import_performance_file'
    ),
    url(
        r'^performance_files/$',
        kari.performance_files,
        name='kari_performance_files'
    ),
]
