# -*- coding: utf-8 -*-

from django.conf.urls import url

from the_redhuman_is.views import claims


urlpatterns = [
    url(
        r'^turnout_autocomplete/$',
        claims.WorkerTurnoutAutocomplete.as_view(),
        name='claims_worker_turnout_autocomplete'
    ),
    url(
        r'^create/$',
        claims.create,
        name='claims_create_claim'
    ),
    url(
        r'^list/$',
        claims.claim_list,
        name='claims_list'
    ),
    url(
        r'^photos/(?P<pk>\d+)/$',
        claims.photos,
        name='claims_photos'
    ),
]
