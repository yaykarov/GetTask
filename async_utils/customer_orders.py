# -*- coding: utf-8 -*-
# Todo: remove this file, it is deprecated

import pytz

from email.headerregistry import Address

from django.template.loader import render_to_string
from django.utils import timezone

from the_redhuman_is import models

from telegram_bot.utils import send_message_to_group

from . import email


def customer_orders_report(timepoint=timezone.now()):
    orders = models.CustomerOrder.objects.filter(timesheet__isnull=True)
    return render_to_string(
        'customer_orders_report.html',
        {
            'orders': orders,
            'timepoint': timepoint
        }
    )


def make_customer_orders_report():
    now = timezone.now().astimezone(pytz.timezone('Europe/Moscow'))

    subject = 'Отчет по заявкам без табеля на {}'.format(now.strftime('%H:%M %d.%m.%y'))
    html = customer_orders_report(now)
    addresses = [
        Address('', 'zallexx', 'yandex.ru'),
        Address('', 'a.iakimenko', 'redhuman.ru'),
    ]

    for to in addresses:
        email.send_email(to, subject, html)


def _minutes(interval):
    return round(interval.seconds / 60) + interval.days * 24 * 60


def _send_message(message):
    send_message_to_group(message, 'Операционисты')


def _send_order_soft_notification(order):
    message = 'Через {} мин. начинается смена "{}". Не забудьте завести табель до начала смены!'.format(
        _minutes(order.time_before_workshift()),
        order.description()
    )
    _send_message(message)
    models.CustomerOrderSoftNotification.objects.create(customer_order=order)


def _send_order_hard_notification(order):
    message = 'Смена "{}" началась {} мин. назад. Необходимо срочно внести табель!'.format(
        order.description(),
        _minutes(-order.time_before_workshift())
    )
    _send_message(message)
    models.CustomerOrderHardNotification.objects.create(customer_order=order)


def _send_timesheet_soft_notification(timesheet):
    message = 'Закончилась смена "{}". Не забудьте закрыть табель.'.format(
        timesheet.customerorder.description()
    )
    _send_message(message)
    models.TimesheetSoftNotification.objects.create(timesheet=timesheet)


def make_customer_orders_telegram_report():
#    for order in models.orders_for_soft_notification():
#        _send_order_soft_notification(order)

    for order in models.orders_for_hard_notification():
        _send_order_hard_notification(order)

#    for timesheet in models.timesheets_for_notification():
#        _send_timesheet_soft_notification(timesheet)

