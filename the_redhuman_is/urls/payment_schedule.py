# -*- coding: utf-8 -*-

from django.conf.urls import url

from the_redhuman_is.views import payment_schedule


urlpatterns = [
    url(
        r'^$',
        payment_schedule.index,
        name='payment_schedule_index'
    ),
    url(
        r'^schedule/$',
        payment_schedule.schedule,
        name='payment_schedule_schedule'
    ),
    url(
        r'^operations/$',
        payment_schedule.operations,
        name='payment_schedule_operations'
    ),
    url(
        r'^day_operations/$',
        payment_schedule.day_operations,
        name='payment_schedule_day_operations'
    ),
    url(
        r'^create_operation/$',
        payment_schedule.create_planned_operation,
        name='payment_schedule_create_operation'
    ),
    url(
        r'^delete_operation/$',
        payment_schedule.delete_planned_operation,
        name='payment_schedule_delete_operation'
    )
]
