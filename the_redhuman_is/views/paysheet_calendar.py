# -*- coding: utf-8 -*-

import datetime
import xlrd

from django.urls import reverse
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import redirect
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_POST

from the_redhuman_is import forms
from the_redhuman_is import models

from the_redhuman_is.auth import staff_account_required

from the_redhuman_is.views.utils import get_first_last_day
from utils.date_time import days_from_interval
from utils.date_time import date_from_string
from utils.date_time import string_from_date


@staff_account_required
def import_calendar(request):
    return render(
        request,
        'the_redhuman_is/paysheet_calendar/import_calendar.html'
    )


def _accountable_persons(sheet):
    accountable_persons = {}

    # Подотчетные лица
    col_customer = 0
    col_accountable_person = 2
    for row in range(1, sheet.nrows):
        customer = sheet.cell_value(row, col_customer)

        full_name = sheet.cell_value(row, col_accountable_person)
        if full_name:
            last_name, name, patronymic = full_name.strip().split(' ')
            person = models.AccountablePerson.objects.get(
                worker__last_name=last_name,
                worker__name=name,
                worker__patronymic=patronymic
            )

            accountable_persons[customer] = person

    return accountable_persons


def _date(sheet, row, col):
    return datetime.datetime(
        *xlrd.xldate_as_tuple(
            sheet.cell_value(row, col),
            sheet.book.datemode
        )
    ).date()


@require_POST
@staff_account_required
@transaction.atomic
def do_import_calendar(request):
    book = xlrd.open_workbook(
        file_contents=request.FILES['calendar'].read()
    )

    accountable_persons = _accountable_persons(book.sheet_by_index(1))

    errors = []

    paysheet_params = []
    sheet = book.sheet_by_index(0)
    row_date = 1
    for row in range(3, sheet.nrows):
        customer_name = sheet.cell_value(row, 0).strip()
        customer = models.Customer.objects.get(
            cust_name=customer_name
        )
        current_params = None
        first_day = None
        last_day = None

        prepayment_first_day = None

        for col in range(1, sheet.ncols):
            if sheet.cell_type(row, col) == xlrd.XL_CELL_DATE:
                first_day = _date(sheet, row, col)
                last_day = _date(sheet, 1, col)
            else:
                cell_value = sheet.cell_value(row, col)
                if cell_value in ['з/п', 'А']:
                    params = models.PaysheetParams()
                    params.customer = customer
                    params.accountable_person = accountable_persons[
                        customer_name
                    ]
                    params.pay_day = _date(sheet, 1, col)
                    if cell_value == 'з/п':
                        if not first_day or not last_day:
                            errors.append(
                                'В ячейке {}/{} - \'з/п\', но непонятен период оплаты'.format(
                                    _date(sheet, 1, col),
                                    customer_name
                                )
                            )
                            continue
                        params.kind = 'paysheet'
                        params.first_day = first_day
                        params.last_day = last_day
                        prepayment_first_day = last_day + datetime.timedelta(days=1)
                        first_day=None
                        last_day=None
                    elif cell_value == 'А':
                        params.kind = 'prepayment'
                        if not prepayment_first_day:
                            prepayment_first_day = first_day
                        if not prepayment_first_day:
                            errors.append(
                                'В ячейке {}/{} - \'А\','
                                ' но непонятна дата начала периода'.format(
                                    _date(sheet, 1, col),
                                    customer_name
                                )
                            )
                            continue
                        params.first_day = prepayment_first_day
                        params.last_day = _date(sheet, 1, col - 1)
                    else:
                        errors.append(
                            'В ячейке {}/{} - {}, недопустимое значение'.format(
                                _date(sheet, 1, col),
                                customer_name,
                                cell_value
                            )
                        )
                        continue

                    paysheet_params.append(params)

    models.PaysheetParams.objects.all().delete()

    models.PaysheetParams.objects.bulk_create(
        paysheet_params
    )

    return JsonResponse(
        errors,
        safe=False
    )


@staff_account_required
def show_calendar(request):
    first_day, last_day = get_first_last_day(request)

    paysheets = models.Paysheet_v2.objects.filter(
        last_day__gte=first_day,
        last_day__lte=last_day
    )

    prepayments = models.Prepayment.objects.filter(
        last_day__gte=first_day,
        last_day__lte=last_day
    )

    params = models.PaysheetParams.objects.filter(
        (Q(last_day__gte=first_day) & Q(last_day__lte=last_day)) |
        (Q(pay_day__gte=first_day) & Q(pay_day__lte=last_day))
    )

    customers = models.Customer.objects.filter(
        Q(paysheets__in=paysheets) |
        Q(prepayments__in=prepayments) |
        Q(paysheetparams__in=params)
    ).distinct(
    ).order_by(
        'cust_name'
    )

    days = days_from_interval(first_day, last_day)

    grid = dict(
        zip(
            [c.pk for c in customers],
            [(customers[i], [None for k in range(len(days))]) for i in range(len(customers))]
        )
    )

    def _try_add(row, day, value, url):
        day_index = (day - first_day).days
        if day_index < len(row):
            if row[day_index] is not None:
                value = '[...]'
            row[day_index] = (value, url)

    def _details_url(customer_pk, day):
        return request.build_absolute_uri(
            reverse('the_redhuman_is:paysheet_calendar_details')
        ) + '?customer={}&day={}'.format(
            customer_pk,
            string_from_date(day)
        )

    for param in params:
        customer, row = grid[param.customer_id]
        if param.kind == 'paysheet':
            _try_add(
                row,
                param.last_day,
                param.first_day.strftime('%d.%m'),
                _details_url(param.customer_id, param.last_day)
            )
        _try_add(
            row,
            param.pay_day,
            'А' if param.kind == 'prepayment' else 'з/п',
            _details_url(param.customer_id, param.pay_day)
        )

    for paysheet in paysheets:
        customer, row = grid[paysheet.customer_id]
        _try_add(
            row,
            paysheet.last_day,
            paysheet.first_day.strftime('%d.%m'),
            _details_url(paysheet.customer_id, paysheet.last_day)
        )

    for prepayment in prepayments:
        customer, row = grid[prepayment.customer_id]
        _try_add(
            row,
            prepayment.last_day,
            'А',
            _details_url(prepayment.customer_id, prepayment.last_day)
        )

    data = [grid[c.pk] for c in customers]

    return render(
        request,
        'the_redhuman_is/paysheet_calendar/show.html',
        {
            'filter_form': forms.DaysIntervalForm(
                initial={
                    'first_day': first_day,
                    'last_day': last_day
                }
            ),
            'days': days,
            'data': data
        }
    )


@staff_account_required
def details(request):
    customer_pk = request.GET['customer']
    day = date_from_string(request.GET['day'])

    paysheets = models.Paysheet_v2.objects.filter(
        customer__pk=customer_pk,
        last_day=day
    )

    prepayments = models.Prepayment.objects.filter(
        customer__pk=customer_pk,
        last_day=day
    )

    params = models.PaysheetParams.objects.filter(
        Q(last_day=day) |
        Q(pay_day=day),
        customer__pk=customer_pk
    )

    return render(
        request,
        'the_redhuman_is/paysheet_calendar/details.html',
        {
            'paysheets': paysheets,
            'prepayments': prepayments,
            'params': params
        }
    )


def _create_by_params(author, params):
    if params.kind == 'prepayment':
        factory = models.create_prepayment
    else:
        factory = models.create_paysheet
    paysheet = factory(
        author,
        params.accountable_person,
        params.first_day,
        params.last_day,
        params.customer,
        params.location,
    )
    params.delete()
    return paysheet


@require_POST
@staff_account_required
@transaction.atomic
def create_by_params(request, pk):
    params = models.PaysheetParams.objects.get(pk=pk)
    paysheet = _create_by_params(request.user, params)
    if params.kind == 'prepayment':
        template = 'the_redhuman_is:prepayment_show'
    else:
        template = 'the_redhuman_is:paysheet_v2_show'
    return redirect(template, pk=paysheet.pk)


@require_POST
@staff_account_required
def remove_params(request, pk):
    params = models.PaysheetParams.objects.get(pk=pk)
    params.delete()

    return redirect('the_redhuman_is:paysheet_calendar')


@require_POST
@staff_account_required
@transaction.atomic
def create_yesterday_paysheets(request):
    yesterday = timezone.now().date() - datetime.timedelta(days=3)

    params = models.PaysheetParams.objects.filter(
        last_day=yesterday
    )
    for p in params:
        _create_by_params(request.user, p)

    return redirect('the_redhuman_is:paysheet_v2_list')
