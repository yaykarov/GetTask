# -*- coding: utf-8 -*-

from django.conf.urls import url
from django.urls import path

from the_redhuman_is.views import reconciliation


urlpatterns = [
    url(
        r'^unpaid_autocomplete/$',
        reconciliation.UnpaidReconciliationAutocomplete.as_view(),
        name='reconciliation_unpaid_autocomplete'
    ),

    url(
        r'^(?P<pk>\d+)/remove/$',
        reconciliation.remove,
        name='reconciliation_remove'
    ),
    url(r'^list/$', reconciliation.list_recons, name='reconciliation_list'),
    url(
        r'^(?P<pk>\d+)/show/$',
        reconciliation.show,
        name='reconciliation_show'
    ),
    url(
        r'^(?P<pk>\d+)/photos/$',
        reconciliation.photos,
        name='reconciliation_photos'
    ),
    url(
        r'^(?P<pk>\d+)/add_image/$',
        reconciliation.add_image,
        name='reconciliation_add_image'
    ),
    url(
        r'^(?P<pk>\d+)/close/$',
        reconciliation.close,
        name='reconciliation_close'
    ),
    path(
        '<int:pk>/block/',
        reconciliation.block_operations,
        name='reconciliation_block_operations'
    ),
    path(
        '<int:pk>/invoice/set/',
        reconciliation.set_invoice,
        name='reconciliation_set_invoice'
    ),
    path(
        '<int:pk>/extra_documents/',
        reconciliation.extra_documents,
        name='reconciliation_extra_documents'
    )
]
