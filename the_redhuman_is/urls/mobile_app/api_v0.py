# -*- coding: utf-8 -*-

from django.conf.urls import url
from django.urls import path

from the_redhuman_is.views import delivery

urlpatterns = [
    # Login
    url(
        r'^create_one_off_code/$',
        delivery.create_one_off_code,
        name='api_v1_create_one_off_code'
    ),
    url(
        r'^obtain_tokens/$',
        delivery.obtain_tokens,
        name='api_v1_obtain_tokens'
    ),

    # Registration
    url(
        r'^upload_registration_info/$',
        delivery.upload_registration_info,
        name='api_v1_upload_registration_info'
    ),

    # Status update (with info about push notifications)
    url(
        r'^status_update/$',
        delivery.status_update,
        name='api_v1_status_update'
    ),
    path(
        'update_online_status/',
        delivery.update_online_status_by_worker,
        name='api_v0_online_status_update'
    ),

    # Requests management & worker info
    url(
        r'^worker_account_info/',
        delivery.worker_account_info,
        name='api_v1_worker_account_info'
    ),
    url(
        r'^worker_payment_info/',
        delivery.worker_payment_info,
        name='api_v1_worker_payment_info'
    ),
    url(
        r'^update_worker_payment_info/',
        delivery.update_worker_payment_info,
        name='api_v1_update_worker_payment_info'
    ),
    path(
        'request_payout/',
        delivery.request_payout,
        name='api_v1_request_payout'
    )
]
