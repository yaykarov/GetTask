# -*- coding: utf-8 -*-

from django.conf.urls import url

from the_redhuman_is.views import fine_utils


urlpatterns = [
    url(
        r'^import_fines/$',
        fine_utils.import_fines,
        name='fine_utils_import_fines'
    ),
    url(
        r'^do_import_fines/$',
        fine_utils.do_import_fines,
        name='fine_utils_do_import_fines'
    ),
    url(
        r'^operations_pack_list/$',
        fine_utils.operations_pack_list,
        name='fine_utils_operations_pack_list'
    ),
    url(
        r'^rollback_operations_pack/(?P<pk>\d+)/$',
        fine_utils.rollback_operations_pack,
        name='fine_utils_rollback_operations_pack'
    ),
]
