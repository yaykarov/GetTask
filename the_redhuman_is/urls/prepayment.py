# -*- coding: utf-8 -*-

from django.conf.urls import url

from the_redhuman_is.views import prepayment


urlpatterns = [
    url(r'^create/$', prepayment.create, name='prepayment_create'),
    url(r'^(?P<pk>\d+)/add_image/$', prepayment.add_image, name='prepayment_add_image'),
    url(
        r'^(?P<pk>\d+)/add_workers/$',
        prepayment.add_workers,
        name='prepayment_add_workers'
    ),
    url(r'^(?P<pk>\d+)/close/$', prepayment.close, name='prepayment_close'),
    url(r'^(?P<pk>\d+)/remove/$', prepayment.remove, name='prepayment_remove'),
    url(r'^(?P<pk>\d+)/save/$', prepayment.save, name='prepayment_save'),
    url(r'^(?P<pk>\d+)/show/$', prepayment.show, name='prepayment_show'),
    url(
        r'^(?P<prepayment>\d+)/delete_worker/(?P<worker>\d+)/$',
        prepayment.delete_worker,
        name='prepayment_delete_worker'
    ),
    url(
        r'^(?P<pk>\d+)/set_accountable_person/$',
        prepayment.set_accountable_person,
        name='prepayment_set_accountable_person'
    ),
]
