# -*- coding: utf-8 -*-

from django.conf.urls import url

from the_redhuman_is.views import expenses


urlpatterns = [
    url(
        r'^index/$',
        expenses.index,
        name='expenses_index'
    ),
    url(
        r'^provider/create/$',
        expenses.create_provider,
        name='expenses_create_provider'
    ),
    url(
        r'^provider/update/$',
        expenses.update_provider,
        name='expenses_update_provider'
    ),
    url(
        r'^provider/detail/$',
        expenses.provider_detail,
        name='expenses_provider_detail'
    ),
    url(
        r'^expense/detail/$',
        expenses.expense_detail,
        name='expenses_expense_detail'
    ),
    url(
        r'^create_expense/$',
        expenses.create_expense,
        name='expenses_create_expense'
    ),
    url(
        r'^actual_expenses/$',
        expenses.actual_expenses,
        name='expenses_actual_expenses'
    ),
    url(
        r'^update/$',
        expenses.update,
        name='expenses_update'
    ),
    url(
        r'^account/$',
        expenses.expense_account,
        name='expenses_account'
    ),
]
