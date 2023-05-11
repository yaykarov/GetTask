# -*- coding: utf-8 -*-

import datetime
import io
from decimal import Decimal

from django.core.exceptions import ObjectDoesNotExist

from django.core.files import File

from django.db import transaction
from django.db.models import (
    Exists,
    OuterRef,
)

from django.utils import timezone

from doc_templates.doc_factory import delivery_invoice_pdf

from the_redhuman_is.async_utils import smsc_sms

from the_redhuman_is.models.delivery import (
    DeliveryCustomerLegalEntity,
    DeliveryInvoice,
    DeliveryRequestOperator,
    DeliveryWorkerFCMToken,
    ImportProcessedTimestamp,
    ImportVisitTimestamp,
    LEGAL_ENTITY_OPTIONAL_FIELDS,
    RequestsFile,
)

from the_redhuman_is.models.models import (
    CustomerLocation,
    CustomerOrder,
    CustomerRepr,
    TimeSheet,
    WorkerTurnout,
)

from the_redhuman_is.models.worker import WorkerUser

from utils.date_time import (
    as_default_timezone,
    day_month_year,
    string_from_date,
)

from utils.phone import normalized_phone


class ConfirmationRequired(Exception):
    pass


@transaction.atomic
def create_requests_file(author_id, customer_id, data_file):
    requests_file = RequestsFile.objects.create(
        author_id=author_id,
        customer_id=customer_id,
    )
    requests_file.data_file = data_file
    requests_file.save()
    return requests_file


def _deduction_worker(delivery_request):
    try:
        with transaction.atomic():
            operator = DeliveryRequestOperator.objects.get(request=delivery_request)
            return WorkerUser.objects.get(user=operator.operator).worker

    except ObjectDoesNotExist:
        return None


def customer_location(customer, zone):
    try:
        return CustomerLocation.objects.get(
            customer_id=customer,
            locationzonegroup__zone_group__deliveryzone__code=zone
        )
    except CustomerLocation.DoesNotExist:
        return CustomerLocation.objects.filter(
            customer_id=customer
        ).order_by(
            'pk'
        ).first()


MAX_ARRIVAL_DELTA = 300  # meters


@transaction.atomic
def ensure_timesheet(request, worker):
    """
    Возвращает табель, соответствующий этому выходу работника.
    Создает его (и другие необходимые модели, но без выхода),
    если табеля еще нет
    """
    from the_redhuman_is.services.delivery.utils import DeliveryWorkflowError

    date = request.date
    customer = request.customer
    location = request.location
    if not location:
        raise DeliveryWorkflowError(
            f'Для заявки №{request.pk} должен быть установлен объект, но его нет.'
        )

    orders = CustomerOrder.objects.filter(
        on_date=date,
        customer=customer,
        cust_location=location,
    ).annotate(
        has_worker_turnout=Exists(
            WorkerTurnout.objects.filter(
                worker=worker,
                timesheet=OuterRef('timesheet')
            )
        )
    ).filter(
        has_worker_turnout=True
    )

    try:
        order = orders.get()
        created = False
    except CustomerOrder.MultipleObjectsReturned:
        raise ValueError(
            f'Multiple customer orders {tuple(orders.values_list("pk", flat=True))}'
            f' for worker {worker}'
        )
    except CustomerOrder.DoesNotExist:
        order = CustomerOrder.objects.create(
            input_date=date,
            bid_date_time=date,
            on_date=date,
            on_time=datetime.time(hour=0, minute=0),
            bid_turn='День',
            customer=customer,
            cust_location=location,
            number_of_workers=1,
        )
        created = True

    if not created:
        try:
            return order.timesheet
        except TimeSheet.DoesNotExist:
            pass

    timesheet = TimeSheet.objects.create(
        sheet_date=date,
        sheet_turn='День',
        customer=customer,
        cust_location=location,
        customerorder=order,
        foreman=worker,  # Todo?
        customer_repr=CustomerRepr.objects.filter(customer_id=customer).first(),
    )
    order.timesheet = timesheet
    order.save(update_fields=['timesheet'])
    return timesheet


# Mobile App part


@transaction.atomic
def update_fcm_token(user, app_id, token):
    fcm_token = DeliveryWorkerFCMToken.objects.filter(
        user=user,
        app_id=app_id
    ).first()

    if fcm_token:
        fcm_token.token = token
        fcm_token.timestamp = timezone.now()
        fcm_token.save()
    else:
        fcm_token = DeliveryWorkerFCMToken.objects.create(
            user=user,
            app_id=app_id,
            token=token
        )


def last_user_fcm_token(user):
    return DeliveryWorkerFCMToken.objects.filter(
        user=user
    ).order_by(
        'timestamp'
    ).last()


# GT Customer


def delivery_contract_id(legal_entity):
    return legal_entity.pk + 30


def is_legal_entity_completely_filled(legal_entity):
    for key in LEGAL_ENTITY_OPTIONAL_FIELDS:
        if key == 'reason_code':
            is_legal_entity = legal_entity.is_legal_entity
            if is_legal_entity is None:
                return False
            elif is_legal_entity:
                code = legal_entity.reason_code
                if code is None or code == '':
                    return False
        else:
            value = getattr(legal_entity, key)
            if value is None or value == '':
                return False
    return True


@transaction.atomic
def create_delivery_invoice(author, customer, total_amount):
    total_amount = Decimal(total_amount)
    invoice = DeliveryInvoice.objects.create(
        author=author,
        customer=customer,
        amount=total_amount,
    )

    date = as_default_timezone(invoice.timestamp).date()
    day, month, year = day_month_year(date)

    legal_entity = DeliveryCustomerLegalEntity.objects.get(customer=customer)

    amount_without_vat = round(total_amount / Decimal(1.2), 2)
    vat = total_amount - amount_without_vat

    data = delivery_invoice_pdf(
        number=f'{invoice.pk}-GT',
        day=day,
        month=month,
        year=year,
        legal_entity=legal_entity.full_name,
        total_amount='{:.2f}'.format(total_amount),
        amount_without_vat='{:.2f}'.format(amount_without_vat),
        vat='{:.2f}'.format(vat)
    )
    invoice.invoice_file = File(
        io.BytesIO(data),
        name=f'invoice-{string_from_date(date)}.pdf'
    )
    invoice.save()

    return invoice


@transaction.atomic
def update_import_visit_timestamp(customer):
    ImportVisitTimestamp.objects.update_or_create(
        customer=customer,
        defaults={
            'timestamp': timezone.now()
        }
    )


@transaction.atomic
def update_import_processed_timestamp(customer):
    ImportProcessedTimestamp.objects.update_or_create(
        customer=customer,
        defaults={
            'timestamp': timezone.now()
        }
    )


def is_import_updated(customer):
    try:
        visit = ImportVisitTimestamp.objects.get(customer=customer)
        processed = ImportProcessedTimestamp.objects.get(customer=customer)

        return processed.timestamp > visit.timestamp

    except ObjectDoesNotExist:
        return False


# Telegram bot


def send_new_invitation_sms(phone):
    phone = normalized_phone(phone)
    if phone is None:
        raise Exception(f'Can\'t normalize phone {phone}')

    text = 'Установите ГетТаск\nhttps://gettask.ru/app'

    response = smsc_sms.send_sms('GetTask', phone, text)
