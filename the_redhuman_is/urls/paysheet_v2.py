# -*- coding: utf-8 -*-

from django.conf.urls import url
from django.urls import path

from the_redhuman_is.views import paysheet_v2
from the_redhuman_is.views import paysheet_calendar


urlpatterns = [
    url(r'^list/$', paysheet_v2.list_paysheets, name='paysheet_v2_list'),
    url(r'^do_create/$', paysheet_v2.do_create, name='paysheet_v2_do_create'),
    path(
        'create_requested/',
        paysheet_v2.create_paysheets_for_outstanding_requests,
        name='paysheet_create_requested'
    ),
    path(
        'bulk_create_paysheets/',
        paysheet_v2.bulk_create_paysheets,
        name='paysheet_bulk_create_paysheets'
    ),
    url(
        r'^(?P<pk>\d+)/remove/$',
        paysheet_v2.remove,
        name='paysheet_v2_remove'
    ),
    url(
        r'^(?P<pk>\d+)/toggle_lock/$',
        paysheet_v2.toggle_lock,
        name='paysheet_v2_toggle_lock'
    ),
    url(
        r'^(?P<pk>\d+)/remove_workers/$',
        paysheet_v2.remove_workers,
        name='paysheet_v2_remove_workers'
    ),
    url(
        r'^(?P<pk>\d+)/reset_workers/$',
        paysheet_v2.reset_workers,
        name='paysheet_v2_reset_workers'
    ),
    url(
        r'^(?P<pk>\d+)/add_remainders/$',
        paysheet_v2.add_remainders,
        name='paysheet_v2_add_remainders'
    ),
    url(
        r'^(?P<pk>\d+)/save_receipts/$',
        paysheet_v2.save_receipts,
        name='paysheet_v2_save_receipts'
    ),
    url(
        r'^(?P<pk>\d+)/recreate/$',
        paysheet_v2.recreate,
        name='paysheet_v2_recreate'
    ),
    url(
        r'^(?P<paysheet_pk>\d+)/remove_operation/(?P<operation_pk>\d+)/$',
        paysheet_v2.remove_operation,
        name='paysheet_v2_remove_operation'
    ),
    url(
        r'^(?P<pk>\d+)/set_accountable_person/$',
        paysheet_v2.set_accountable_person,
        name='paysheet_v2_set_accountable_person'
    ),
    url(r'^(?P<pk>\d+)/show/$', paysheet_v2.show, name='paysheet_v2_show'),
    path('<int:pk>/download/', paysheet_v2.download_paysheet, name='paysheet_v2_download'),
    path('<int:pk>/email/', paysheet_v2.email_paysheet, name='paysheet_v2_email'),
    path(
        '<int:pk>/make_payments_with_talk_bank/',
        paysheet_v2.make_payments_with_talk_bank,
        name='paysheet_v2_make_payments_with_talk_bank'),
    url(
        r'^(?P<paysheet_pk>\d+)/day_details/(?P<worker_pk>\d+)/(?P<date>[\d.]+)/$',
        paysheet_v2.day_details,
        name='paysheet_v2_day_details'
    ),
    url(
        r'^(?P<pk>\d+)/add_image/$',
        paysheet_v2.add_image,
        name='paysheet_v2_add_image'
    ),
    url(
        r'^(?P<pk>\d+)/add_registry/$',
        paysheet_v2.add_registry,
        name='paysheet_v2_add_registry'
    ),
    url(
        r'^(?P<pk>\d+)/receipts/$',
        paysheet_v2.paysheet_receipts,
        name='paysheet_v2_paysheet_receipts'
    ),
    path(
        '<int:pk>/talk_bank_payment_report/',
        paysheet_v2.talk_bank_payment_report,
        name='paysheet_v2_talk_bank_payment_report'
    ),
    url(
        r'^(?P<pk>\d+)/update_amounts/$',
        paysheet_v2.update_amounts,
        name='paysheet_v2_update_amounts'
    ),
    url(
        r'^(?P<pk>\d+)/close/$',
        paysheet_v2.close,
        name='paysheet_v2_close'
    ),
    url(
        r'^worker_autocomplete/$',
        paysheet_v2.WorkerAutocomplete.as_view(),
        name='paysheet_v2_worker_autocomplete'
    ),
    url(
        r'^paysheet_autocomplete/$',
        paysheet_v2.paysheet_autocomplete,
        name='paysheet_v2_paysheet_autocomplete'
    ),

    # Calendar
    url(
        r'^import_calendar/$',
        paysheet_calendar.import_calendar,
        name='paysheet_import_calendar'
    ),
    url(
        r'^do_import_calendar/$',
        paysheet_calendar.do_import_calendar,
        name='paysheet_do_import_calendar'
    ),
    url(
        r'^calendar/$',
        paysheet_calendar.show_calendar,
        name='paysheet_calendar'
    ),
    url(
        r'^calendar_details/$',
        paysheet_calendar.details,
        name='paysheet_calendar_details'
    ),
    url(
        r'^paysheet_params/(?P<pk>\d+)/create/$',
        paysheet_calendar.create_by_params,
        name='paysheet_create_by_params'
    ),
    url(
        r'^paysheet_params/(?P<pk>\d+)/remove/$',
        paysheet_calendar.remove_params,
        name='paysheet_calendar_remove_params'
    ),
    url(
        r'^create_yesterday_paysheets/$',
        paysheet_calendar.create_yesterday_paysheets,
        name='paysheet_create_yesterday_paysheets'
    ),
]
