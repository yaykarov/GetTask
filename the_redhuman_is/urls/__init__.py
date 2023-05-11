# -*- coding: utf-8 -*-

from django.conf.urls import include
from django.conf.urls import url
from django.urls import path

app_name = 'the_redhuman_is'
urlpatterns = [
    url(
        r'^autocharge/',
        include('the_redhuman_is.urls.autocharge')
    ),
    url(
        r'^customer_specific/',
        include('the_redhuman_is.urls.customer_specific')
    ),
    url(r'^claims/', include('the_redhuman_is.urls.claims')),
    url(r'^contracts/', include('the_redhuman_is.urls.contracts')),
    url(r'^delivery/', include('the_redhuman_is.urls.delivery')),
    url(r'^expenses/', include('the_redhuman_is.urls.expenses')),
    url(r'^fine_utils/', include('the_redhuman_is.urls.fine_utils')),
    url(r'^gt_landing/', include('the_redhuman_is.urls.gt_landing')),
    url(r'^hostel/', include('the_redhuman_is.urls.hostel')),
    url(r'^payment_schedule/', include('the_redhuman_is.urls.payment_schedule')),
    url(r'^paysheet_v2/', include('the_redhuman_is.urls.paysheet_v2')),
    url(r'^photo-load/', include('the_redhuman_is.urls.photo_load')),
    url(r'^prepayment/', include('the_redhuman_is.urls.prepayment')),
    url(r'^reconciliation/', include('the_redhuman_is.urls.reconciliation')),
    url(r'^reports/', include('the_redhuman_is.urls.reports')),
    url(r'^staff/', include('the_redhuman_is.urls.staff')),
    url(r'^temporary/', include('the_redhuman_is.urls.temporary')),

    # mobile app api
    url(r'^m/', include('the_redhuman_is.urls.mobile_app')),

    # new 'experimental' backoffice app api
    url(r'^bo/', include('the_redhuman_is.urls.backoffice_app')),

    # customer api
    path('gt/customer/api/v1/', include('the_redhuman_is.urls.customer_api')),

    # GetTask customer account
    url(r'^gt/customer/', include('the_redhuman_is.urls.gt_customer_account')),

    # legacy urls
    url(r'^', include('the_redhuman_is.urls.urls')),
]
