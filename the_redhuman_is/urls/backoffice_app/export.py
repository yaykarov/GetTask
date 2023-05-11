# -*- coding: utf-8 -*-

from django.urls import path

from the_redhuman_is.views.backoffice_app import export


urlpatterns = [
    path(
        'self_employed_receipts/',
        export.self_employed_receipts,
        name='export_self_employed_receipts'
    ),
]
