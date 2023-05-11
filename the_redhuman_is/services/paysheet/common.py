from datetime import (
    datetime,
    timedelta,
)

from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.db.models import (
    Case,
    DateField,
    Exists,
    ExpressionWrapper,
    JSONField,
    Max,
    Min,
    OuterRef,
    Q,
    Subquery,
    Value,
    When,
)
from django.db.models.functions import (
    Coalesce,
    JSONObject,
    TruncDate,
)
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from finance.models import Operation
from the_redhuman_is.models.models import WorkerTurnout
from the_redhuman_is.models.paysheet_v2 import (
    PayoutRequest,
    PaysheetRegistry,
    Paysheet_v2Entry,
    Paysheet_v2EntryOperation,
    RegistryNum,
    WorkerReceipt,
    WorkerReceiptRegistryNum,
    create_paysheet,
)
from the_redhuman_is.models.photo import (
    Photo,
    get_photos,
)
from the_redhuman_is.models.turnout_operations import TurnoutOperationToPay
from the_redhuman_is.models.worker import Worker
from the_redhuman_is.tasks import fetch_receipt_image
from utils import date_from_string


@receiver(post_save, sender=WorkerReceipt)
def _worker_request_post_save(sender, instance, created, **kwargs):
    fetch_receipt_image(instance.pk)


def parse_registry_file(registry_file):
    lines = registry_file.read().decode('cp1251').strip().split('\n')

    if len(lines) < 2:
        raise ValueError('В файле должно быть больше 1 строки.')

    rows = []
    for line in lines[1:]:
        rows.append(line.split(';'))

        if rows[0][0] != rows[-1][0]:
            raise ValueError('В файле разные номера реестра, а должны быть одинаковые.')

    registry_num = rows[0][0]

    # last_name, name, patronymic, url, income date
    receipts = [
        (row[3], row[4], row[5], row[15].strip(), date_from_string(row[7]))
        for row in rows
        if row[15].startswith('https://lknpd.nalog.ru/')
    ]

    return receipts, registry_num


def add_registry(paysheet, registry_file, author):
    # Todo: save the file (?)

    receipts, registry_num = parse_registry_file(registry_file)
    # Check if the registry exists
    registry = PaysheetRegistry.objects.get(
        paysheet=paysheet,
        registry_num=registry_num,
    )

    for last_name, name, patronymic, url, income_date in receipts:
        with transaction.atomic():
            worker = Worker.objects.get(
                paysheet_v2_entries__paysheet=paysheet,
                last_name=last_name,
                name=name,
                patronymic=patronymic,
            )

            worker_receipt = WorkerReceipt.objects.create(
                author=author,
                worker=worker,
                url=url,
                date=income_date
            )

            WorkerReceiptRegistryNum.objects.create(
                worker_receipt=worker_receipt,
                registry_num_id=registry_num
            )

    workers_without_receipt = Worker.objects.filter(
        paysheet_v2_entries__paysheet=paysheet,
        workerreceipt__isnull=True
    )

    if workers_without_receipt.exists():
        registry_num = RegistryNum.objects.create()
        PaysheetRegistry.objects.create(
            paysheet=paysheet,
            registry_num=registry_num
        )


def paysheet_receipts(paysheet):
    return WorkerReceipt.objects.annotate(
        has_entry=Exists(
            Paysheet_v2Entry.objects.filter(
                worker=OuterRef('worker'),
                paysheet=paysheet
            )
        )
    ).filter(
        Q(
            workerreceiptregistrynum__registry_num__paysheetregistry__paysheet=paysheet,
            has_entry=True,
        ) |
        Q(
            workerreceiptpaysheetentry__paysheet_entry__paysheet=paysheet
        )
    )


def paysheet_receipt_photos(paysheet):
    receipt_pks = paysheet_receipts(paysheet).values_list('pk')

    return Photo.objects.filter(
        content_type=ContentType.objects.get_for_model(WorkerReceipt),
        object_id__in=receipt_pks
    )


def paysheet_photos(paysheet):
    return get_photos(paysheet).union(paysheet_receipt_photos(paysheet))


def _modify_worker_queryset_for_paysheets(worker_qs, last_day):
    operation_sq = Operation.objects.annotate(
        # not collected into entries
        in_paysheet_initial=Exists(
            Paysheet_v2EntryOperation.objects.filter(
                operation=OuterRef('pk'),
            )
        ),
        # not the closing op of an entry
        in_paysheet_closing=Exists(
            Paysheet_v2Entry.objects.filter(
                operation=OuterRef('pk')
            )
        )
    ).filter(
        # debit or credit ops with this worker's account
        Q(debet=OuterRef('worker_account__account')) |
        Q(credit=OuterRef('worker_account__account')),
        in_paysheet_initial=False,
        in_paysheet_closing=False,
        timepoint__date__gte=OuterRef('last_closed_paysheet_date'),  # not null sentinel value in outer query
        # workers with others' cards are paid in full up to yesterday inclusive
        # even though they have to submit a request in advance
        timepoint__date__lte=last_day,
    ).values(
        'timepoint__date'
    )

    return worker_qs.annotate(
        # worker not in an existing unclosed paysheet
        has_unclosed_paysheet=Exists(
            Paysheet_v2Entry.objects.filter(
                worker=OuterRef('pk'),
                paysheet__is_closed=False
            )
        )
    ).filter(
        has_unclosed_paysheet=False
    ).with_is_selfemployed(
    ).with_cardholder_name(
        upper=True,
    ).with_full_name(
        upper=True
    ).with_worker_type(
    ).annotate(
        last_closed_paysheet_date=Coalesce(
            Subquery(
                Paysheet_v2Entry.objects.filter(
                    worker=OuterRef('pk'),
                    paysheet__is_closed=True,
                ).order_by(
                    '-paysheet__last_day'
                ).values(
                    'paysheet__last_day'
                )[:1]
            ),
            # if no closed paysheets yet
            Value(timezone.make_aware(datetime(1970, 1, 1, 0, 0))),
            output_field=DateField()
        )
    ).annotate(
        first_day=ExpressionWrapper(
            Subquery(
                operation_sq.order_by(
                    'timepoint__date'
                )[:1],
                output_field=DateField()
            ),
            output_field=DateField()
        ),
        last_day=ExpressionWrapper(
            Subquery(
                operation_sq.order_by(
                    '-timepoint__date'
                )[:1],
                output_field=DateField()
            ),
            output_field=DateField()
        )
    ).filter(
        first_day__isnull=False
    )


def _create_paysheets(workers_to_pay, author, accountable_person):
    worker_types = [
        'foreign',
        'selfemployed_own_account',
        'selfemployed_another_account',
    ]
    created_paysheets = []

    for worker_type in worker_types:
        workers_by_type = workers_to_pay.filter(
            worker_type=worker_type
        )
        min_max_dates = workers_by_type.aggregate(
            Min('first_day'),
            Max('last_day'),
        )
        if min_max_dates['first_day__min'] is None:
            continue

        paysheet = create_paysheet(
            author=author,
            accountable_person=accountable_person,
            first_day=min_max_dates['first_day__min'],
            last_day=min_max_dates['last_day__max'],
            customer=None,
            location=None,
            workers=workers_by_type
        )
        created_paysheets.append(paysheet)

    return created_paysheets


def create_paysheets_for_outstanding_requests(author, accountable_person):
    today = timezone.localdate()
    yesterday = today - timedelta(days=1)
    last_monday = yesterday - timedelta(days=yesterday.weekday() % 7)
    with transaction.atomic():
        workers_to_pay = _modify_worker_queryset_for_paysheets(
            Worker.objects.all(
            ).select_for_update(
                of=('self',),
                nowait=True,
            ),
            last_day=yesterday,
        ).annotate(
            request_deadline=Case(
                When(
                    # workers using others' cards are paid "at most" once a week
                    # if they submitted a request before last Tuesday
                    worker_type='selfemployed_another_account',
                    then=Value(last_monday)
                ),
                # selfemployed workers and foreigners are paid "at most" once a day
                # if they submitted a request before today
                default=yesterday,
                output_field=DateField()
            )
        ).annotate(
            has_outstanding_payout_request=Exists(
                PayoutRequest.objects.filter(
                    worker=OuterRef('pk'),
                    paysheet_entry__isnull=True,
                    timestamp__date__lte=OuterRef('request_deadline'),
                )
            )
        ).filter(
            has_outstanding_payout_request=True,
        )

        created_paysheets = _create_paysheets(
            workers_to_pay,
            author,
            accountable_person
        )

        for paysheet in created_paysheets:
            paysheet_entries = list(
                Paysheet_v2Entry.objects.filter(
                    paysheet=paysheet
                ).values(
                    'pk',
                    'worker',
                )
            )
            for entry in paysheet_entries:
                PayoutRequest.objects.filter(
                    worker=entry['worker']
                ).update(
                    paysheet_entry=entry['pk']
                )

        return created_paysheets


def bulk_create_paysheets(author, accountable_person):
    today = timezone.localdate()
    yesterday = today - timedelta(days=1)
    last_week = yesterday - timedelta(days=6)
    with transaction.atomic():
        workers_to_pay = _modify_worker_queryset_for_paysheets(
            Worker.objects.all(
            ).select_for_update(
                of=('self',),
                nowait=True,
            ),
            last_day=yesterday,
        ).annotate(
            has_recent_unpaid_turnouts=Exists(
                WorkerTurnout.objects.filter(
                    worker=OuterRef('pk'),
                    timesheet__sheet_date__gte=last_week,
                    timesheet__sheet_date__lte=yesterday,
                    is_payed=False,
                )
            )
        ).filter(
            has_recent_unpaid_turnouts=True
        )
        created_paysheets = _create_paysheets(
            workers_to_pay,
            author,
            accountable_person
        )
        return created_paysheets


def annotate_with_paysheet_workdays(
        queryset,
        paysheet_id,
        worker,
):
    tzinfo = timezone.get_current_timezone()
    return queryset.annotate(
        paysheet_workdays=Subquery(
            Paysheet_v2EntryOperation.objects.annotate(
                has_turnout_operation_to_pay=Exists(
                    TurnoutOperationToPay.objects.filter(
                        operation=OuterRef('operation'),
                    )
                )
            ).filter(
                entry__paysheet_id=paysheet_id,
                entry__worker=worker,
            ).values(
                'entry__worker'
            ).annotate(
                workday_fields=JSONObject(
                    start=TruncDate(Min('operation__timepoint'), tzinfo=tzinfo),
                    end=TruncDate(Max('operation__timepoint'), tzinfo=tzinfo),
                )
            ).values(
                'workday_fields'
            ),
            output_field=JSONField()
        )
    )


def _iso_to_ru_date(date):
    return '.'.join(reversed(date.split('-')))


def get_service_name(first_day, last_day):
    if first_day == last_day:
        return f'Оплата за погрузку-разгрузку за {_iso_to_ru_date(last_day)}'
    else:
        return (
            f'Оплата за погрузку-разгрузку'
            f' с {_iso_to_ru_date(first_day)} по {_iso_to_ru_date(last_day)}'
        )
