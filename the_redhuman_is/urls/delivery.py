# -*- coding: utf-8 -*-

from django.conf.urls import url
from django.urls import path

from the_redhuman_is.views import delivery


urlpatterns = [
    # Todo: remove this url/view, it is deprecated
    path(
        '<int:pk>/extra_photos/',
        delivery.delivery_request_extra_photos,
        name='delivery_delivery_request_extra_photos'
    ),

    url(
        r'^location_autocomplete/$',
        delivery.LocationAutocomplete.as_view(),
        name='delivery_location_autocomplete'
    ),
    url(
        r'^service_autocomplete/$',
        delivery.ServiceAutocomplete.as_view(),
        name='delivery_service_autocomplete'
    ),
    url(
        r'^route_autocomplete/$',
        delivery.DeliveryRequestAutocomplete.as_view(),
        name='delivery_route_autocomplete'
    ),
    url(
        r'^item_autocomplete/$',
        delivery.DeliveryItemAutocomplete.as_view(),
        name='delivery_item_autocomplete'
    ),
    url(
        r'^worker_autocomplete/$',
        delivery.DeliveryWorkerAutocomplete.as_view(),
        name='delivery_worker_autocomplete'
    ),
    url(
        r'^request_operator_autocomplete/$',
        delivery.DeliveryRequestOperatorAutocomplete.as_view(),
        name='delivery_request_operator_autocomplete'
    ),
    path(
        'delivery_zone_autocomplete/',
        delivery.DeliveryZoneAutocomplete.as_view(),
        name='delivery_zone_autocomplete'
    ),
    path(
        'delivery_operator_autocomplete/',
        delivery.DeliveryOperatorAutocomplete.as_view(),
        name='delivery_operator_autocomplete'
    ),
    path(
        'workers_to_connect_to_mts',
        delivery.workers_to_connect_to_mts,
        name='delivery_workers_to_connect_to_mts'
    ),
    path(
        'other/',
        delivery.other,
        name='delivery_other'
    ),
    path(
        'call_list_csv/',
        delivery.worker_call_list_csv,
        name='delivery_call_list_csv'
    ),

    # Reports

    url(
        r'^turnouts_report/$',
        delivery.turnouts_report,
        name='delivery_turnouts_report'
    ),
    url(
        r'^turnouts_period_report/$',
        delivery.turnouts_period_report,
        name='delivery_turnouts_period_report'
    ),
    url(
        r'^requests_count/$',
        delivery.requests_count_report,
        name='delivery_requests_count_report'
    ),
    url(
        r'^requests_count_data/$',
        delivery.requests_count_report_data,
        name='delivery_requests_count_report_data'
    ),
    url(
        r'^imports_report/$',
        delivery.imports_report,
        name='delivery_imports_report'
    ),
    url(
        r'^imports_report_data/$',
        delivery.imports_report_data,
        name='delivery_imports_report_data'
    ),
    url(
        r'^requests_file/$',
        delivery.requests_file,
        name='delivery_requests_file'
    ),
    url(
        r'^cities_report/$',
        delivery.cities_report,
        name='delivery_cities_report'
    ),
    url(
        r'^new_customers_report/$',
        delivery.new_customers_report,
        name='delivery_new_customers_report'
    ),
    url(
        r'^new_customers_report_data/$',
        delivery.new_customers_report_data,
        name='delivery_new_customers_report_data'
    ),
    path(
        'online_status_report/',
        delivery.online_status_report,
        name='delivery_online_status_report'
    ),
    url(
        r'^confirm_legal_entity/$',
        delivery.confirm_legal_entity,
        name='delivery_confirm_legal_entity'
    ),
]
