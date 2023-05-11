from django.urls import path

from the_redhuman_is.views.customer_api import delivery


urlpatterns = [
    path(
        'request/',
        delivery.list_requests,
        name='gt_customer_api_v1_delivery_request_list'
    ),
    path(
        'request/detail/',
        delivery.request_detail,
        name='gt_customer_api_v1_delivery_request_detail'
    ),
    path(
        'request/create/',
        delivery.create_request,
        name='gt_customer_api_v1_delivery_create_request'
    ),
    path(
        'location/',
        delivery.list_customer_locations,
        name='gt_customer_api_v1_location_list'
    ),
    path(
        'price/',
        delivery.estimate_price,
        name='gt_customer_api_v1_price'
    ),
]
