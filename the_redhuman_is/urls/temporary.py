# -*- coding: utf-8 -*-

from django.conf.urls import url

from the_redhuman_is.views.temporary_reports import deposit_for_all_workers
from the_redhuman_is.views.temporary_reports import fix_deposits
from the_redhuman_is.views.temporary_reports import oldi_hostel

from the_redhuman_is.views.temporary import paysheet_details_for_worker

from the_redhuman_is.views import temporary
from the_redhuman_is.views import temporary_reports

urlpatterns = [
    url(
        r'^oldi_hostel/$',
        oldi_hostel,
        name='oldi_hostel'
    ),
    url(
        r'^deposit_for_all_workers/',
        deposit_for_all_workers,
        name='deposit_for_all_workers'
    ),
    url(
        r'^fix_deposits/',
        fix_deposits,
        name='fix_deposits'
    ),
    url(
        r'^paysheet_details_for_worker/',
        paysheet_details_for_worker,
        name='paysheet_details_for_worker'
    ),
    url(
        r'^fix_missed_calls/',
        temporary.fix_missed_calls,
        name='fix_missed_calls'
    ),
    url(
        r'^fix_prepayment_date/',
        temporary.fix_prepayment_date,
        name='fix_prepayment_date'
    ),
    url(
        r'^fix_future_operation/',
        temporary.fix_future_operation,
        name='fix_future_operation'
    ),
    url(
        r'^block_paysheet_operations/',
        temporary.block_paysheet_operations,
        name='block_paysheet_operations'
    ),

    url(
        r'^oldi_workers/',
        temporary_reports.oldi_workers,
        name='oldi_workers'
    ),
]
