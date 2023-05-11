# -*- coding: utf-8 -*-

from django.conf.urls import url
from django.urls import path

from the_redhuman_is.views import staff


urlpatterns = [
    path(
        'worker_passport_autocomplete',
        staff.PassportAutocomplete.as_view(),
        name='staff_worker_passport_autocomplete'
    ),

    url(
        r'^workers_list/$',
        staff.workers_list,
        name='staff_workers_list'
    ),
    url(
        r'^workers_list_details/$',
        staff.workers_list_details,
        name='staff_workers_list_details'
    ),

    url(
        r'^contracts_list/$',
        staff.contracts_list,
        name='staff_contracts_list'
    ),
    url(
        r'^contracts_list_details/$',
        staff.contracts_list_details,
        name='staff_contracts_list_details'
    ),
    url(
        r'^change_contracts/$',
        staff.change_contracts,
        name='staff_change_contracts'
    ),
    url(
        r'^download_notifications/$',
        staff.download_notifications,
        name='staff_download_notifications'
    ),

    path(
        'worker/<int:worker_pk>/documents/',
        staff.worker_document_photos,
        name='staff_worker_documents'
    ),
    path(
        'worker_documents/photos_data/',
        staff.worker_documents_photos_data,
        name='staff_worker_documents_photos_data'
    ),
    path(
        'worker_documents/update_photo/',
        staff.update_worker_document_photo,
        name='staff_worker_documents_update_photo'
    ),
]
