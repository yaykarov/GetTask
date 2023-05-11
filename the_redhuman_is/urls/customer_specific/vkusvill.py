# -*- coding: utf-8 -*-

from django.conf.urls import url

from the_redhuman_is.views.customer_specific import vkusvill


urlpatterns = [
    url(
        r'^$',
        vkusvill.management_page,
        name='vkusvill_management_page'
    ),

    url(
        r'^performance_file_report/(?P<pk>\d+)/$',
        vkusvill.performance_file_report,
        name='vkusvill_performance_file_report'
    ),
    url(
        r'^save_and_check_performance_file/$',
        vkusvill.save_and_check_performance_file,
        name='vkusvill_save_and_check_performance_file'
    ),
    url(
        r'^import_performance_file/(?P<pk>\d+)/$',
        vkusvill.import_performance_file,
        name='vkusvill_import_performance_file'
    ),

    url(
        r'^errors_file_report/(?P<pk>\d+)/$',
        vkusvill.errors_file_report,
        name='vkusvill_errors_file_report'
    ),
    url(
        r'^errors_files_list/$',
        vkusvill.errors_files_list,
        name='vkusvill_errors_files_list'
    ),
    url(
        r'^save_and_check_errors_file/$',
        vkusvill.save_and_check_errors_file,
        name='vkusvill_save_and_check_errors_file'
    ),
    url(
        r'^import_errors_file/(?P<pk>\d+)/$',
        vkusvill.import_errors_file,
        name='vkusvill_import_errors_file'
    ),

    url(
        r'^performance_report/$',
        vkusvill.performance_report,
        name='vkusvill_performance_report'
    ),

    url(
        r'^test_report_1/$',
        vkusvill.test_report_1,
        name='vkusvill_test_report_1'
    ),
    url(
        r'^rename_vegetables/$',
        vkusvill.rename_vegetables,
        name='rename_vegetables'
    ),
    url(
        r'^rename_codes/$',
        vkusvill.rename_codes,
        name='rename_codes'
    ),
    url(
        r'^make_ugai_transform/$',
        vkusvill.make_ugai_transform,
        name="vkusvill_make_ugai_transform"
    ),

    url(
        r'^temporary_fines/$',
        vkusvill.temporary_fines,
        name="vkusvill_temporary_fines"
    )
]
