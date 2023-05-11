# -*- coding: utf-8 -*-

from django.contrib import admin

from import1c import models

from the_redhuman_is.admin import _register


_register(models.AccountMapping, ['account'])
admin.site.register(models.Import)
_register(models.ImportedNode, ['operation'])
