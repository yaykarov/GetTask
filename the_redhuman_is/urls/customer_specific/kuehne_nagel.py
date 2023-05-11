# -*- coding: utf-8 -*-

from django.conf.urls import url

from the_redhuman_is.views.customer_specific import kuehne_nagel

urlpatterns = [
    url(
        r'^management_page/',
        kuehne_nagel.management_page,
        name='kuehne_nagel_management_page'
    ),

    url(
        r'^save_kn_sheet/$',
        kuehne_nagel.save_kn_sheet,
        name='kuehne_nagel_save_kn_sheet'
    ),
    url(
        r'^kn_sheets_list/$',
        kuehne_nagel.kn_sheets_list,
        name='kuehne_nagel_sheets_list'
    ),
    url(
        r'^kn_sheet_report/(?P<pk>\d+)/$',
        kuehne_nagel.kn_sheet_report,
        name='kuehne_nagel_kn_sheet_report'
    )

]
