# -*- coding: utf-8 -*-

from django.conf.urls import url

from the_redhuman_is.views import autocharge


urlpatterns = [
    url(r'^settings/$', autocharge.settings, name='autocharge_settings'),
    url(
        r'^settings/(?P<pk>[0-9]+)/$',
        autocharge.specific_setting,
        name='autocharge_specific_setting'
    ),
    url(r'^calculator_form/$', autocharge.calculator_form, name='autocharge_calculator_form'),
    url(
        r'^position_calculator_form/$',
        autocharge.position_calculator_form,
        name='autocharge_position_calculator_form'
    ),
    url(
        r'^calculator_subform/$',
        autocharge.calculator_subform,
        name='autocharge_calculator_subform'
    ),
    url(
        r'^position_calculator_subform/$',
        autocharge.position_calculator_subform,
        name='autocharge_position_calculator_subform'
    ),
    url(
        r'^save_settings/$',
        autocharge.save_settings,
        name='autocharge_save_settings'
    ),
    url(
        r'^save_position_calculator/$',
        autocharge.save_position_calculator,
        name='autocharge_save_position_calculator'
    ),
    url(
        r'^service_calculator_autocomplete/$',
        autocharge.service_calculator_autocomplete,
        name='autocharge_service_calculator_autocomplete'
    ),
    url(
        r'^position_calculator_autocomplete/$',
        autocharge.position_calculator_autocomplete,
        name='autocharge_position_calculator_autocomplete'
    ),
]
