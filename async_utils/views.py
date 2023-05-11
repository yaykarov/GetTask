# -*- coding: utf-8 -*-

from django.shortcuts import render
from django.http import HttpResponse

from . import customer_orders
from . import uiscom_missed_calls

def make_customer_orders_report(request):
    customer_orders.make_customer_orders_telegram_report()
    return HttpResponse('ok')


def import_uiscom_missed_calls(request):
    uiscom_missed_calls.import_uiscom_missed_calls()
    return HttpResponse('ok')

