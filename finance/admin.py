# -*- coding: utf-8 -*-

from django.contrib import admin

from finance import models

from the_redhuman_is.admin import _register

class AccountAdmin(admin.ModelAdmin):
    search_fields = ['full_name']
    raw_id_fields = ['parent']

class OperationAdmin(admin.ModelAdmin):
    search_fields = ['comment', 'debet__full_name', 'credit__full_name']
    raw_id_fields = ['debet', 'credit']


admin.site.register(models.Account, AccountAdmin)
admin.site.register(models.Operation, OperationAdmin)
_register(models.IntervalPayment, ['operation'])
