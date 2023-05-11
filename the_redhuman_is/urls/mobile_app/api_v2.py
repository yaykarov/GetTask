# -*- coding: utf-8 -*-

from django.urls import path

from the_redhuman_is.views import (
    delivery,
    delivery_mobile,
)

urlpatterns = [
    # Login
    path(
        'create_one_off_code/',
        delivery.create_one_off_code,
        name='api_v2_create_one_off_code'
    ),
    path(
        'obtain_tokens/',
        delivery.obtain_tokens,
        name='api_v2_obtain_tokens'
    ),

    # Registration
    path(
        'upload_registration_info/',
        delivery.upload_registration_info,
        name='api_v2_upload_registration_info'
    ),

    # Status update (with info about push notifications)
    path(
        'status_update/',
        delivery.status_update,
        name='api_v2_status_update'
    ),
    path(
        'update_online_status/',
        delivery.update_online_status_by_worker,
        name='api_v2_online_status_update'
    ),

    # Requests management & worker info
    path(
        'requests/',
        delivery_mobile.worker_requests,
        name='api_v2_worker_requests'
    ),
    path(
        'unpaid_requests/',
        delivery_mobile.worker_unpaid_requests,
        name='api_v2_worker_unpaid_requests'
    ),
    path(
        'worker_account_info/',
        delivery.worker_account_info,
        name='api_v2_worker_account_info'
    ),
    path(
        'worker_payment_info/',
        delivery.worker_payment_info,
        name='api_v2_worker_payment_info'
    ),
    path(
        'update_worker_payment_info/',
        delivery.update_worker_payment_info,
        name='api_v2_update_worker_payment_info'
    ),
    path(
        'request/worker/add/',
        delivery_mobile.add_confirm_request_worker,
        name='api_v2_add_request_worker'
    ),
    path(
        'request/worker/confirm/',
        delivery_mobile.confirm_request_worker,
        name='api_v2_confirm_request_worker'
    ),
    path(
        'request/item/worker/start/',
        delivery_mobile.item_worker_start,
        name='api_v2_item_worker_start'
    ),
    path(
        'request/item/worker/finish/',
        delivery_mobile.item_worker_finish,
        name='api_v2_item_worker_finish'
    ),
    path(
        'request_payout/',
        delivery.request_payout,
        name='api_v2_request_payout'
    ),

    # Poll answer
    path(
        'answer_poll/',
        delivery_mobile.worker_answer_poll,
        name='api_v2_answer_poll'
    )
]
