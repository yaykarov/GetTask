# -*- coding: utf-8 -*-

from django.conf.urls import url

from the_redhuman_is.views import hostel


urlpatterns = [
    url(r'^list/$', hostel.list, name='hostel_list'),
    url(r'^set_bonus/$', hostel.set_bonus, name='hostel_set_bonus'),
    url(
        r'^set_bonus_last_day/$',
        hostel.set_bonus_last_day,
        name='hostel_set_bonus_last_day'
    ),
    url(
        r'^update_all_hostel_bonuses/$',
        hostel.update_all_hostel_bonuses,
        name='update_all_hostel_bonuses'
    ),

    url(
        r'expenses_report/',
        hostel.expenses_report,
        name='hostel_expenses_report'
    )
]
