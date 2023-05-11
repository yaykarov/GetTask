# -*- coding: utf-8 -*-

from django.conf.urls import url

from the_redhuman_is.views.customer_specific import itella

urlpatterns = [
    url(
        r'^$',
        itella.management_page,
        name='itella_management_page'
    ),

    url(
        r'^save_k2k_sheet/$',
        itella.save_k2k_sheet,
        name='itella_save_k2k_sheet'
    ),
    url(
        r'^k2k_sheets_list/$',
        itella.k2k_sheets_list,
        name='itella_k2k_sheets_list'
    ),
    url(
        r'^k2k_sheet_report/(?P<pk>\d+)/$',
        itella.k2k_sheet_report,
        name='itella_k2k_sheet_report'
    ),
    url(
        r'^save_k2k_aliases/$',
        itella.save_k2k_aliases,
        name='itella_save_k2k_aliases'
    )
]
