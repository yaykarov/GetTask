# -*- coding: utf-8 -*-

from django.conf.urls import url

from doc_templates.views import test

app_name = 'doc_templates'

urlpatterns = [
    url(r'^test/$', test, name='test')
]
