# -*- coding: utf-8 -*-

from django.conf.urls import url

from the_redhuman_is.views.main_workers import workers_count
from the_redhuman_is.views.main_workers import main_workers_distribution
from the_redhuman_is.views.main_workers import workers_lifetime

from the_redhuman_is.views import efficiency
from the_redhuman_is.views import reports


urlpatterns = [
    url(
        r'^workers_count/$',
        workers_count,
        name='reports_workers_count'
    ),

    # main_workers
    url(
        r'^main_workers_distribution/$',
        main_workers_distribution,
        name='reports_main_workers_distribution'
    ),
    url(
        r'^workers_lifetime/$',
        workers_lifetime,
        name='reports_workers_lifetime'
    ),
    url(
        r'^workers_debtors/$',
        reports.workers_debtors,
        name='workers_debtors'
    ),
    url(
        r'^workers_creditors/$',
        reports.workers_creditors,
        name='workers_creditors'
    ),
    url(
        r'^workers_with_deposits/$',
        reports.workers_with_deposits,
        name='workers_with_deposits'
    ),
    url(
        r'^applicants_cities/$',
        reports.applicants_cities,
        name='report_applicants_cities'
    ),

    # efficiency
    url(
        r'^efficiency/$',
        efficiency.efficiency_report,
        name='report_efficiency'
    ),
    url(
        r'^efficiency/operations/(?P<filter>\S+)/$',
        efficiency.operations_list,
        name='report_efficiency_operations_list'
    ),
    url(
        r'^efficiency/operations_json/(?P<filter>\S+)/$',
        efficiency.operations_list_json,
        name='report_efficiency_operations_list_json'
    ),
]
