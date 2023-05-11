import re

from django.contrib import auth

from django.db.models import (
    DecimalField,
    IntegerField,
    JSONField,
    OuterRef,
    Subquery,
)
from django.db.models.functions import (
    Coalesce,
    JSONObject,
)

from django.http import (
    HttpResponseForbidden,
    HttpResponseNotFound,
    JsonResponse,
)

import finance
from the_redhuman_is.models.paysheet_v2 import (
    Paysheet_v2,
    WorkerReceipt,
    WorkerReceiptPaysheetEntry,
    WorkerReceiptRegistryNum,
)
from the_redhuman_is.models.worker import WorkerSelfEmploymentData

from the_redhuman_is.services.paysheet import get_service_name

from the_redhuman_is.views.utils import (
    _get_value,
    get_first_last_day,
)

from utils.date_time import string_from_date


_PATH_RX = re.compile('^.*/(.+)/print')


def _serialize_receipt(receipt):

    # Todo: get rid of this
    if receipt['paysheet_workdays'] is None and receipt['paysheet'] == 1376:
        day = '2021-06-26'
        description = get_service_name(day, day)
    else:
        description = get_service_name(
            receipt['paysheet_workdays']['start'],
            receipt['paysheet_workdays']['end']
        )

    return {
        'receipt_url': receipt['url'],
        'receipt_num': _PATH_RX.match(receipt['url']).group(1),
        'receipt_date': string_from_date(receipt['date']),
        'receipt_description': description,
        'receipt_amount': receipt['amount'],
        'last_name': receipt['worker__last_name'],
        'first_name': receipt['worker__name'],
        'patronymic': receipt['worker__patronymic'],
        'tax_code': receipt['wse']['tax_number'],
        'bank_identification_code': receipt['wse']['bank_identification_code'],
        'bank_account': receipt['wse']['bank_account']
    }


def self_employed_receipts(request):
    username = _get_value(request, 'login')
    password = _get_value(request, 'password')
    first_day, last_day = get_first_last_day(request)

    user = auth.authenticate(username=username, password=password)
    if user is None:
        return HttpResponseNotFound()

    receipts = WorkerReceipt.objects.filter(
        date__range=(first_day, last_day)
    ).annotate(
        paysheet=Coalesce(
            Subquery(
                WorkerReceiptPaysheetEntry.objects.filter(
                    worker_receipt=OuterRef('pk'),
                    paysheet_entry__worker=OuterRef('worker')
                ).values(
                    'paysheet_entry__paysheet'
                )
            ),
            Subquery(
                WorkerReceiptRegistryNum.objects.filter(
                    worker_receipt=OuterRef('pk'),
                ).values(
                    'registry_num__paysheetregistry__paysheet'
                )
            ),
            output_field=IntegerField()
        )
    )

    unclosed_paysheets = list(
        Paysheet_v2.objects.filter(
            pk__in=receipts.values('paysheet'),
            is_closed=False,
        ).values_list(
            'pk',
            flat=True
        )
    )
    if unclosed_paysheets:
        return HttpResponseForbidden(
            f'Незакрытые ведомости: {", ".join(str(pk) for pk in unclosed_paysheets)}'
        )

    receipts = receipts.with_paysheet_workdays(
        OuterRef('paysheet'),
    ).annotate(
        amount=Subquery(
            finance.models.Operation.objects.filter(
                paysheet_v2_operation__paysheet=OuterRef('paysheet'),
                paysheet_v2_operation__worker=OuterRef('worker'),
            ).values(
                'amount'
            ),
            output_field=DecimalField()
        ),
        wse=Subquery(
            WorkerSelfEmploymentData.objects.filter(
                worker=OuterRef('worker'),
            ).order_by(
                '-deletion_ts'
            ).annotate(
                data=JSONObject(
                    tax_number='tax_number',
                    bank_account='bank_account',
                    bank_identification_code='bank_identification_code',
                )
            ).values(
                'data'
            )[:1],
            output_field=JSONField()
        )
    ).values(
        'url',
        'date',
        'paysheet_workdays',
        'amount',
        'worker__last_name',
        'worker__name',
        'worker__patronymic',
        'wse',
        'paysheet',
    )

    receipts_with_no_amount = [
        f'{receipt["paysheet"]}/{receipt["worker__last_name"]}'
        for receipt in receipts
        if receipt['amount'] is None
    ]
    if receipts_with_no_amount:
        return HttpResponseForbidden(
            f'Ведомости без суммы: {", ".join(receipts_with_no_amount)}'
        )

    return JsonResponse(
        list(_serialize_receipt(receipt) for receipt in receipts),
        safe=False
    )
