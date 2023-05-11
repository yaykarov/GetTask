# -*- coding: utf-8 -*-

import datetime
import decimal
import json
import os

from django.core.exceptions import (
    ObjectDoesNotExist,
    PermissionDenied,
    ValidationError,
)

from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType

from django.db import transaction

from django.db.models import (
    CharField,
    Count,
    IntegerField,
    OuterRef,
    Q,
    Subquery,
    Sum,
    TextField,
    Value,
)

from django.db.models.functions import (
    Cast,
    Coalesce
)

from django.http import (
    HttpResponse,
    HttpResponseBadRequest,
    JsonResponse,
)
from django.views.decorators.csrf import csrf_exempt

from django.urls import reverse

from django.utils import timezone
from django.views.decorators.http import (
    require_GET,
    require_POST,
)

from rest_framework import status
from rest_framework.views import APIView
from rest_framework.decorators import (
    api_view,
    permission_classes,
)

from rest_framework_simplejwt.tokens import RefreshToken

from dal.autocomplete import Select2QuerySetView

from doc_templates.doc_factory import delivery_contract_response_pdf

from the_redhuman_is import models
from the_redhuman_is.auth import IsCustomer
from the_redhuman_is.models import get_user_location
from the_redhuman_is.models.delivery import (
    DailyReconciliationNotification,
    DeliveryRequest,
    RequestWorkerTurnout,
)
from the_redhuman_is.models.reconciliation import ReconciliationInvoice
from the_redhuman_is.services import confirm_daily_reconciliation
from the_redhuman_is.tasks import send_email
from the_redhuman_is.views.customer_api import auth

from utils.date_time import (
    date_from_string,
    day_month_year,
    string_from_date,
)
from utils.numbers import separate

from the_redhuman_is.services.delivery_requests import (
    create_delivery_invoice,
    delivery_contract_id,
    is_import_updated,
    is_legal_entity_completely_filled,
    update_import_visit_timestamp,
)

from the_redhuman_is.views.utils import (
    _get_value,
    content_response,
    exception_to_json_error,
    get_first_last_day,
)

from the_redhuman_is.views.delivery import (
    _get_size,
    _serialize_requests_file,
    requests_file_response,
)


class DeliveryRequestAutocomplete(Select2QuerySetView, APIView):
    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return DeliveryRequest.objects.none()

        date = date_from_string(self.forwarded.get('date'))

        delivery_requests = DeliveryRequest.objects.filter(
            customer__customeraccount__user=user,
            date=date,
        ).order_by('pk')
        if get_user_location(user) is not None:
            delivery_requests = delivery_requests.filter(location__locationaccount__user=user)

        if self.q:
            delivery_requests = delivery_requests.annotate(
                pk_str=Cast('pk', CharField())
            ).filter(
                Q(route__icontains=self.q) |
                Q(pk_str__icontains=self.q)
            )

        return delivery_requests

    def get_result_label(self, result):
        if result.route:
            return f'{result.route} ({result.pk})'
        else:
            return f'{result.pk}'


class DeliveryItemAutocomplete(Select2QuerySetView, APIView):
    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return models.DeliveryItem.objects.none()

        delivery_requests = DeliveryRequest.objects.filter(
            customer__customeraccount__user=user
        )
        if get_user_location(user) is not None:
            delivery_requests = delivery_requests.filter(location__locationaccount__user=user)
        delivery_request = delivery_requests.get(pk=self.forwarded.get('request'))
        delivery_items = models.DeliveryItem.objects.filter(
            request__date=delivery_request.date,
            request__customer=delivery_request.customer,
            request__driver_name=delivery_request.driver_name,
            request__driver_phones=delivery_request.driver_phones,
        ).exclude(
            request=delivery_request
        ).order_by('pk')

        if self.q:
            delivery_items = delivery_items.filter(
                Q(code__icontains=self.q) |
                Q(address__icontains=self.q)
            )

        return delivery_items

    def get_result_label(self, result):
        return '{} {}'.format(result.code, result.address)


class LocationAutocomplete(Select2QuerySetView, APIView):
    paginate_by = None

    def get_queryset(self):
        try:
            customer = _get_customer(self.request)

        except ObjectDoesNotExist:
            return models.CustomerLocation.objects.none()

        else:
            locations = customer.customerlocation_set.all().order_by('location_name')
            if get_user_location(self.request.user) is not None:
                locations = locations.filter(locationaccount__user=self.request.user)

            if self.q:
                locations = locations.filter(location_name__icontains=self.q)

            first_day = self.forwarded.get('first_day')
            last_day = self.forwarded.get('last_day')

            if first_day and last_day:
                first_day = date_from_string(first_day)
                last_day = date_from_string(last_day)

                locations = locations.annotate(
                    count=Coalesce(
                        Subquery(
                            DeliveryRequest.objects.filter(
                                customer=customer,
                                date__range=(first_day, last_day),
                                location=OuterRef('pk')
                            ).values(
                                'location'
                            ).annotate(
                                count=Count('pk')
                            ).values(
                                'count'
                            ),
                            output_field=IntegerField()
                        ),
                        Value(0)
                    )
                )

            return locations

    def get_result_label(self, result):
        if hasattr(result, 'count'):
            return f'{result.location_name} {result.count}'
        else:
            return result.location_name


# Serialization utils


def _serialize_object(target, fields):
    return {field: getattr(target, field) for field in fields}


def _serialize_reconciliation(recn):
    photos = models.get_photos(recn)
    scan_prefix = reverse('the_redhuman_is:gt_customer_report_scan')
    location = '-'
    if recn.location:
        location = recn.location.location_name

    try:
        invoice_date = string_from_date(recn.invoice.date)
        invoice_number = recn.invoice.number

    except ReconciliationInvoice.DoesNotExist:
        invoice_date = '-'
        invoice_number = '-'

    return {
        'pk': recn.pk,
        'number': recn.pk,
        'creation_date': string_from_date(recn.timestamp.date()),
        'account_date': invoice_date, # Todo: rename field accound_date -> invoice_date
        'account_number': invoice_number, # Todo: rename field account_number -> invoice_number
        'location': location,
        'first_day': string_from_date(recn.first_day),
        'last_day': string_from_date(recn.last_day),
        'amount': recn.sum_total,  # Todo: format?
        'scans': [scan_prefix + '?pk={}'.format(photo.pk) for photo in photos],
        'deadline': string_from_date(recn.last_day + datetime.timedelta(days=14)),  # Todo
        'status': getattr(recn, 'status')
    }


def _serialize_contact_person(person):
    return {
        'pk': person.pk,
        'full_name': person.repr_name,
        'email': person.email,
        'phone': person.tel_number,
        'position': person.position
    }


# View-functions


def _get_customer(request):
    return models.Customer.objects.get(customeraccount__user=request.user)


def _create_single_turnout_calculator(hour_rate):
    calculator = models.SingleTurnoutCalculator.objects.create(
        parameter_1='hours',
        parameter_2='hours'
    )

    if isinstance(hour_rate, list):
        for begin, rate in hour_rate:
            calculator.intervals.add(
                models.CalculatorInterval.objects.create(
                    begin=begin,
                    b=0,
                    k=rate
                )
            )
    else:
        calculator.intervals.add(
            models.CalculatorInterval.objects.create(
                begin=0,
                b=0,
                k=hour_rate
            )
        )

    calculator.save()

    return calculator


# Todo: GT-297
# Todo: move this to some other place? models?
def _setup_service(
        service_pk,
        customer,
        customer_rate,
        worker_rate,
        delivery_service_params):

    service = models.Service.objects.get(pk=service_pk)
    customer_service = models.create_customer_service(customer, service)

    amount_calculator = models.AmountCalculator.objects.create(
        customer_calculator=_create_single_turnout_calculator(customer_rate),
        foreman_calculator=_create_single_turnout_calculator(worker_rate),
        worker_calculator=_create_single_turnout_calculator(worker_rate)
    )
    models.ServiceCalculator.objects.create(
        customer_service=customer_service,
        calculator=amount_calculator,
        first_day=timezone.now() - datetime.timedelta(days=1),
    )

    for zone, customer_name, operator_name, hours, is_for_united in delivery_service_params:
        delivery_service = models.DeliveryService.objects.create(
            is_for_united_request=is_for_united,
            zone=zone,
            service=customer_service,
            customer_service_name=customer_name,
            operator_service_name=operator_name,
            travel_hours=hours-4, # Todo: fix this
            hours=hours
        )


def _setup_services_and_calculators(customer):
    SERVICES = [
        (
            37, # Москва до 500 кг
            '305.08',
            '87.5',
            [
                ('msk', 'Москва', 'Москва до 500кг', 4, False),
                ('msk', 'Москва', 'Москва ночь до 500кг', 5, False),
            ]
        ),
        (
            38, # Москва от 520 кг
            '305.08',
            '125',
            [
                ('msk_520', 'Москва', 'Москва от 520кг', 4, False),
                ('msk_520', 'Москва', 'Москва ночь от 520кг', 5, False),
            ]
        ),
        (
            39, # МО до 17.1км
            '305.08',
            '140',
            [
                ('mo_17', 'МО', 'МО до 17.1км', 5, False),
                ('mo_17', 'МО', 'МО ночь до 17.1км', 6, False),
            ]
        ),
        (
            40, # МО 17.1-31км
            '305.08',
            '166.67',
            [
                ('mo_31', 'МО', 'МО 17.1-31км', 6, False),
                ('mo_31', 'МО', 'МО ночь 17.1-31км', 7, False),
            ]
        ),
        (
            41, # МО 31-43км
            '305.08',
            '142.86',
            [
                ('mo_43', 'МО', 'МО 31-43км', 7, False),
                ('mo_43', 'МО', 'МО ночь 31-43км', 8, False),
            ]
        ),
        (
            42, # МО более 43км,
            '305.08',
            '125',
            [
                ('mo_43+', 'МО', 'МО более 43км', 8, False),
                ('mo_43+', 'МО', 'МО ночь более 43км', 9, False),
            ]
        ),
        (
            43, # серийная доставка
            '305.08',
            '165',
            [
                ('msk', 'Москва', 'Москва до 500кг', 4, True),
                ('msk', 'Москва', 'Москва ночь до 500кг', 5, True),
                ('msk_520', 'Москва', 'Москва от 520кг', 4, True),
                ('msk_520', 'Москва', 'Москва ночь от 520кг', 5, True),
                ('mo_17', 'МО', 'МО до 17.1км', 5, True),
                ('mo_17', 'МО', 'МО ночь до 17.1км', 6, True),
                ('mo_31', 'МО', 'МО ночь 17.1-31км', 7, True),
                ('mo_43', 'МО', 'МО 31-43км', 7, True),
                ('mo_43', 'МО', 'МО ночь 31-43км', 8, True),
                ('mo_43+', 'МО', 'МО более 43км', 7, True),
                ('mo_43+', 'МО', 'МО ночь более 43км', 8, True),
            ]
        ),
        (
            44, # серийная доставка МО 17-31
            '305.08',
            [(0, '166.67'), (7, '165.0')],
            [
                ('mo_31', 'МО', 'МО 17.1-31км', 6, True),
            ]
        )
    ]

    for service_pk, customer_rate, worker_rate, params in SERVICES:
        _setup_service(service_pk, customer, customer_rate, worker_rate, params)


def _setup_new_gt_customer(user, organization_name, phone):
    customer = models.Customer.objects.create(
        cust_name=organization_name
    )
    models.create_customer_operating_accounts(customer)
    location = models.CustomerLocation.objects.create(
        customer_id=customer,
        location_name='GetTask {}'.format(user.pk)
    )

    # Todo: GT-1060
#    _setup_services_and_calculators(customer)

    models.CustomerAccount.objects.create(
        customer=customer,
        user=user,
    )

    models.CustomerRepr.objects.create(
        customer_id=customer,
        repr_name=user.first_name,
        tel_number=phone,
        email=user.email,
        main=True
    )

    legal_entity = models.LegalEntity.objects.get(pk=17)
    models.CustomerLegalEntity.objects.create(
        customer=customer,
        legal_entity=legal_entity,
        first_day=timezone.now() - datetime.timedelta(days=1),
    )

    legal_entity = models.DeliveryCustomerLegalEntity.objects.create(
        customer=customer,
        full_name=organization_name,
        email=user.email,
        phone=phone,
    )

    _send_new_user_email(legal_entity)


# Todo: move host to some *local* file
_BASE_HOST = 'https://lk.gettask.ru'


def _signup_mail_body(email, key):
    return (
        'Здравствуйте!<br><br>'
        'Спасибо за регистрацию в сервисе <a href="https://gettask.ru">GetTask.ru</a>.<br><br>'
        'Ваш логин: {}.<br><br>'
        'Остался последний шаг: перейдите по <a href="{}/finish_registration/{}">ссылке</a>, '
        'чтобы активировать личный кабинет'.format(email, _BASE_HOST, key)
    )


def _is_password_too_simple(password):
    if len(password) < 8:
        return True

    has_upper = False
    has_digit = False

    for c in password:
        if c.isupper():
            has_upper = True
        if c.isdigit():
            has_digit = True

    return (not has_upper) or (not has_digit)


def _password_too_simple_response():
    return JsonResponse(
        data={
            'message': 'Слишком простой пароль. Пароль должен быть не короче 8 символов'
                ' и содержать по крайней мере 1 цифру и 1 заглавную букву.'
        },
        status=400
    )


@csrf_exempt
@transaction.atomic
def signup(request):
    params = json.loads(request.body)
    full_name = params.get('full_name')
    organization_name = params.get('organization_name')
    phone = params.get('phone')
    email = params.get('email')
    password = params.get('password')

    completely_filled = True
    for field in (full_name, organization_name, phone, email, password):
        if field is None or field == '':
            completely_filled = False
            break

    if not completely_filled:
        return JsonResponse(
            data={
                'message': 'Для регистрации необходимы все поля: '
                    'Ваше имя, название организации, почта, телефон и пароль'
            },
            status=400
        )

    if _is_password_too_simple(password):
        return _password_too_simple_response()

    email_exists = False
    if User.objects.filter(email=email).exists():
        email_exists = True
    if models.UserRegistrationInfo.objects.filter(email=email).exists():
        email_exists = True

    if email_exists:
        return JsonResponse(
            data={'message': 'Пользователь с почтой "{}" уже существует.'.format(email)},
            status=409,
        )

    reg_info = models.start_registration(
        full_name,
        organization_name,
        phone,
        email,
        password,
    )

    send_email(
        email,
        'Регистрация на GetTask.ru',
        _signup_mail_body(email, reg_info.key),
        'gt_noreply'
    )

    return JsonResponse({})


@csrf_exempt
@transaction.atomic
def finish_registration(request):
    key = _get_value(request, 'uid')

    try:
        user, organization_name, phone = models.finish_registration(key, 'gettask')
        _setup_new_gt_customer(user, organization_name, phone)

        refresh = RefreshToken.for_user(user)
        return JsonResponse({'access_token': str(refresh.access_token)})

    except ObjectDoesNotExist:
        return JsonResponse(data={}, status=404)

    except Exception as e:
        print(str(e))
        return JsonResponse(data={}, status=500)


obtain_token = auth.get_token


def _update_password_mail_body(email, full_name, key):
    return (
        'Здравствуйте, {}!<br><br>'
        'Поступил запрос на смену пароля.'
        '<br><br>'
        'Ваш логин: {}.'
        '<br><br>'
        'Чтобы изменить пароль, пройдите по <a href="{}/update_password/{}">ссылке</a>.'
        '<br><br>'
        'Если вы не отправляли запрос, и пароль менять вам не нужно, просто '
        'игнорируйте это письмо.'.format(full_name, email, _BASE_HOST, key)
    )


@csrf_exempt
@exception_to_json_error(500)
def reset_password(request):
    email = _get_value(request, 'email')

    try:
        user = User.objects.get(
            customeraccount__isnull=False,
            email=email
        )

    except ObjectDoesNotExist:
        return JsonResponse(
            data={'message': 'Пользователь с почтой "{}" не найден.'.format(email)},
            status=404
        )

    reset_psw_request = models.request_password_reset(user)

    send_email(
        user.email,
        'Смена пароля на GetTask.ru',
        _update_password_mail_body(email, user.first_name, reset_psw_request.key),
        'gt_noreply'
    )

    return JsonResponse({})


@csrf_exempt
@exception_to_json_error(500)
def update_password(request):
    key = _get_value(request, 'uid')
    password = _get_value(request, 'password')

    if _is_password_too_simple(password):
        return _password_too_simple_response()

    try:
        user = models.update_password(key, password)

        send_email(
            user.email,
            'Смена пароля на GetTask.ru',
            'Здравствуйте, {}!<br><br>Ваш логин: {}.<br>Пароль был успешно обновлен.'.format(
                user.first_name,
                user.email
            ),
            'gt_noreply'
        )

        return JsonResponse({})

    except ObjectDoesNotExist:
        raise PermissionDenied('Пароль не обновлен, т.к. ссылка для обновления некорректная.')


def account_api(http_methods, atomic=False):
    def decorator(view_func):

        @api_view(http_methods)
        @permission_classes([IsCustomer])
        def proxy(*args, **kwargs):
            if atomic:
                with transaction.atomic():
                    return view_func(*args, **kwargs)
            else:
                return view_func(*args, **kwargs)

        return proxy

    return decorator


def _registration_status(customer):
    legal_entity = models.DeliveryCustomerLegalEntity.objects.filter(customer=customer)

    if legal_entity.exists():
        legal_entity = legal_entity.get()
        if is_legal_entity_completely_filled(legal_entity):
            if legal_entity.registration_confirmed:
                return 'completed'
            elif models.get_photos(legal_entity).exists():
                return 'confirmation_required'
            else:
                return 'scan_required'

    return 'info_required'


# Todo: set reasonable value
_MIN_BALANCE = 1000


@account_api(['GET'])
def account_info(request):
    user = request.user
    customer = _get_customer(request)

    operating_accounts = models.CustomerOperatingAccounts.objects.get(customer=customer)
    main_account = operating_accounts.account_62_root

    reg_status = _registration_status(customer)
    saldo = main_account.turnover_saldo()
    balance = -1 * saldo if saldo != 0 else decimal.Decimal(0.0)

    allow_requests_creation = False
    legal_entity = models.DeliveryCustomerLegalEntity.objects.filter(customer=customer).first()
    if legal_entity is not None:
        allow_requests_creation = (
            legal_entity.postpayment_allowed or
            (reg_status == 'completed' and balance > _MIN_BALANCE)
        )

    unpaid_requests = DeliveryRequest.objects.all(
    # Todo: vvv this is not the fastest way to check if request is paid
    # Todo: maybe is should be done somehow using _merge logic, which
    # is deleted in this commit : )
    ).with_is_paid_by_customer(
    ).with_in_payment_by_customer(
    ).filter(
        status__in=DeliveryRequest.SUCCESS_STATUSES,
        is_paid_by_customer=False,
        customer=customer,
    )

    new_reports_qs = models.Reconciliation.objects.filter(
        customer=customer,
    ).with_status(
    ).filter(
        status_='new'
    )
    customer_locations = customer.customerlocation_set.all()

    if get_user_location(user) is not None:
        unpaid_requests = unpaid_requests.filter(location__locationaccount__user=user)
        new_reports_qs = new_reports_qs.filter(location__locationaccount__user=user)
        customer_locations = customer_locations.filter(locationaccount__user=user)

    unpaid_requests = list(
        unpaid_requests.values_list(
            'pk',
            'in_payment_by_customer',
            named=True
        )
    )

    unpaid_requests_total = len(unpaid_requests)
    unpaid_requests_in_payment = sum(
        1
        for request in unpaid_requests
        if request.in_payment_by_customer
    )
    unpaid_requests_active = unpaid_requests_total - unpaid_requests_in_payment

    unpaid_requests_sum = RequestWorkerTurnout.objects.filter(
        requestworker__request__in=[request.pk for request in unpaid_requests]
    ).aggregate(
        Sum('workerturnout__turnoutcustomeroperation__operation__amount')
    )['workerturnout__turnoutcustomeroperation__operation__amount__sum']

    new_reports_count = new_reports_qs.count()

    return JsonResponse(
        {
            'full_name': user.first_name,
            'email': user.email,
            'balance': {
                'text': separate(balance),
                'highlight': balance <= 0
            },
            'allow_requests_creation': allow_requests_creation,
            'unpaid_requests_sum': separate(unpaid_requests_sum),
            'unpaid_requests_total': separate(unpaid_requests_total),
            'unpaid_requests_in_payment': separate(unpaid_requests_in_payment),
            'unpaid_requests_active': separate(unpaid_requests_active),
            'registration_status': reg_status,
            'imports_updated': is_import_updated(customer),
            'new_reports_count': new_reports_count,
            'show_locations_filter': customer_locations.count() > 1
        }
    )


@account_api(['POST'])
def update_legal_entity_info(request):
    customer = _get_customer(request)
    # Todo: some errors if wrong fields format

    legal_entity = models.DeliveryCustomerLegalEntity.objects.filter(customer=customer)

    is_legal_entity_param = _get_value(request, 'is_legal_entity')
    if is_legal_entity_param in [None, '-1']:
        is_legal_entity = None
    else:
        is_legal_entity = is_legal_entity_param not in ['0', 'false']
    if legal_entity.exists():
        legal_entity = legal_entity.get()

        if legal_entity.registration_confirmed:
            raise Exception('Редактирование запрещено, т.к. регистрация уже подтверждена.')

        if models.get_photos(legal_entity).exists():
            raise Exception('Редактирование запрещено, т.к. уже прикреплены сканы договора.')

        legal_entity.timestamp = timezone.now()
        legal_entity.is_legal_entity = is_legal_entity
        legal_entity.full_name = _get_value(request, 'full_name')
        legal_entity.ceo = _get_value(request, 'ceo')
        legal_entity.email = _get_value(request, 'email')
        legal_entity.phone = _get_value(request, 'phone')
        legal_entity.legal_address = _get_value(request, 'legal_address')
        legal_entity.mail_address = _get_value(request, 'mail_address')
        legal_entity.tax_number = _get_value(request, 'tax_number')
        legal_entity.reason_code = _get_value(request, 'reason_code')
        legal_entity.bank_name = _get_value(request, 'bank_name')
        legal_entity.bank_identification_code = _get_value(request, 'bank_identification_code')
        legal_entity.bank_account = _get_value(request, 'bank_account')
        legal_entity.correspondent_account = _get_value(request, 'correspondent_account')

        legal_entity.save()

    else:
        legal_entity = models.DeliveryCustomerLegalEntity.objects.create(
            customer=customer,
            is_legal_entity=is_legal_entity,
            full_name=_get_value(request, 'full_name'),
            ceo=_get_value(request, 'ceo'),
            email=_get_value(request, 'email'),
            phone=_get_value(request, 'phone'),
            legal_address=_get_value(request, 'legal_address'),
            mail_address=_get_value(request, 'mail_address'),
            tax_number=_get_value(request, 'tax_number'),
            reason_code=_get_value(request, 'reason_code'),
            bank_name=_get_value(request, 'bank_name'),
            bank_identification_code=_get_value(request, 'bank_identification_code'),
            bank_account=_get_value(request, 'bank_account'),
            correspondent_account=_get_value(request, 'correspondent_account'),
        )

    return JsonResponse(_serialize_object(legal_entity, models.LEGAL_ENTITY_OPTIONAL_FIELDS))


@account_api(['GET'])
def legal_entity_info(request):
    try:
        legal_entity = models.DeliveryCustomerLegalEntity.objects.get(
            customer__customeraccount__user=request.user
        )

        return JsonResponse(
            _serialize_object(legal_entity, models.LEGAL_ENTITY_OPTIONAL_FIELDS)
        )

    except ObjectDoesNotExist:
        return JsonResponse(data={}, status=404)


@account_api(['POST'])
def add_contact_person(request):
    customer = _get_customer(request)
    customer_repr = models.CustomerRepr.objects.create(
        customer_id=customer,
        repr_name=_get_value(request, 'full_name'),
        email=_get_value(request, 'email'),
        tel_number=_get_value(request, 'phone'),
        position=_get_value(request, 'position')
    )

    return JsonResponse(_serialize_contact_person(customer_repr))


@account_api(['POST'])
def update_contact_person(request):
    customer = _get_customer(request)
    customer_repr = models.CustomerRepr.objects.get(
        pk=_get_value(request, 'pk'),
        customer_id=customer
    )

    field = _get_value(request, 'field')
    value = _get_value(request, 'value')

    if field == 'full_name':
        customer_repr.repr_name = value
    elif field == 'email':
        customer_repr.email = value
    elif field == 'phone':
        customer_repr.tel_number = value
    elif field == 'position':
        customer_repr.position = value
    else:
        raise Exception('Unknown field "{}".'.format(field))

    customer_repr.save()

    return JsonResponse(_serialize_contact_person(customer_repr))


@account_api(['GET'])
def contact_persons(request):
    customer = _get_customer(request)
    persons = models.CustomerRepr.objects.filter(customer_id=customer)
    return JsonResponse([_serialize_contact_person(p) for p in persons], safe=False)


@account_api(['GET'])
def get_contract(request):
    customer = _get_customer(request)
    try:
        legal_entity = models.DeliveryCustomerLegalEntity.objects.get(customer=customer)

        if not is_legal_entity_completely_filled(legal_entity):
            return JsonResponse(
                data={
                    'code': 'legal_entity_is_not_completely_filled',
                    'detail': 'Прежде чем скачать договор, надо полностью заполнить данные об организации.',
                },
                status=400
            )

        contact_person = models.CustomerRepr.objects.get(
            customer_id=customer,
            main=True
        )

        name_full = legal_entity.full_name
        reason_code = ''
        if legal_entity.is_legal_entity:
            name_full = 'ООО ' + legal_entity.full_name
            reason_code = legal_entity.reason_code

        day, month, year = day_month_year(legal_entity.timestamp.date())

        return delivery_contract_response_pdf(
            contract_id=str(delivery_contract_id(legal_entity)),
            contract_day=day,
            contract_month=month,
            contract_year=year,
            legal_entity_name_full=name_full,
            legal_entity_name_short=legal_entity.full_name,
            legal_entity_person=contact_person.repr_name,
            legal_entity_person_reason='устава',
            email=contact_person.email,
            legal_address=legal_entity.legal_address,
            mail_address=legal_entity.mail_address,
            legal_entity_tax_number=legal_entity.tax_number,
            legal_entity_reason_code=reason_code,
            bank_account=legal_entity.bank_account,
            bank_name=legal_entity.bank_name,
            correspondent_account=legal_entity.correspondent_account,
            bank_identification_code=legal_entity.bank_identification_code
        )

    except ObjectDoesNotExist:
        return JsonResponse(data={}, status=404)


def _send_notification_email(legal_entity, topic):
    customer_repr = models.CustomerRepr.objects.get(
        customer_id=legal_entity.customer,
        main=True
    )

    body = 'Юрлицо: {}<br>' \
        'ФИО: {}<br>' \
        'Тел.: {}<br>' \
        'email: {}<br><br>' \
        '<a href="https://is.gettask.ru/delivery/new_customers_report/">проверить</a>'.format(
            legal_entity.full_name,
            customer_repr.repr_name,
            customer_repr.tel_number,
            customer_repr.email
        )

    # Todo: GT-1065
    _SPECIAL_EMAILS = [
        'ad@gettask.ru',
        'cherepanov.n@gettask.ru',
        'info@gettask.ru',
        'it@gettask.ru',
        'zallexx@yandex.ru',
    ]

    for target in _SPECIAL_EMAILS:
        send_email(
            target,
            topic,
            body,
            'gt_noreply'
        )


def _send_scan_notification_email(legal_entity):
    _send_notification_email(
        legal_entity,
        'Новый скан от {}'.format(legal_entity.customer.cust_name)
    )


def _send_new_user_email(legal_entity):
    _send_notification_email(
        legal_entity,
        'Новый пользователь "{}" прошел регистрацию'.format(legal_entity.customer.cust_name)
    )


@account_api(['POST'])
def upload_contract_scans(request):
    customer = _get_customer(request)
    try:
        with transaction.atomic():
            legal_entity = models.DeliveryCustomerLegalEntity.objects.get(customer=customer)

            if not is_legal_entity_completely_filled(legal_entity):
                raise Exception(
                    'Прежде чем приложить скан, надо полностью заполнить данные об организации.'
                )

            for key, image in request.FILES.items():
                models.add_photo(legal_entity, image)

        _send_scan_notification_email(legal_entity)

        return JsonResponse({})

    except ObjectDoesNotExist:
        return JsonResponse(data={}, status=404)


@account_api(['GET'])
def report_scan(request):
    pk = _get_value(request, 'pk')
    customer = _get_customer(request)

    try:
        photo = models.Photo.objects.get(pk=pk)

        if photo.content_type != ContentType.objects.get_for_model(models.Reconciliation):
            return HttpResponse(status=403)

        reconciliation_qs = models.Reconciliation.objects.filter(
            customer=customer
        )
        if get_user_location(request.user) is not None:
            reconciliation_qs = reconciliation_qs.filter(
                location__locationaccount__user=request.user
            )
        reconciliation_qs.get(pk=photo.object_id)
        return content_response(photo.image)

    except ObjectDoesNotExist:
        return HttpResponse(status=404)


def _get_report_status(request):
    STATUS_ALIASES = {
        'Новая': 'new',
        'Согласована': 'confirmed',
        'В оплате': 'in_payment',
        'Оплачена': 'paid'
    }

    st = _get_value(request, 'status')

    if st in STATUS_ALIASES.values():
        return st

    if st in STATUS_ALIASES.keys():
        return STATUS_ALIASES[st]

    return None


@account_api(['GET'])
def reports(request):
    first_day, last_day = get_first_last_day(request)
    st = _get_report_status(request)
    search_text = _get_value(request, 'search_text')

    customer = _get_customer(request)

    min_first_day = datetime.date(2020, 8, 1)
    if first_day is None or first_day < min_first_day:
        first_day = min_first_day

    reconciliations = models.Reconciliation.objects.filter(
        Q(first_day__range=(first_day, last_day)) |
        Q(last_day__range=(first_day, last_day)),
        customer=customer
    ).select_related(
        'invoice'
    ).with_status()
    if get_user_location(request.user) is not None:
        reconciliations = reconciliations.filter(
            location__locationaccount__user=request.user
        )

    if st:
        reconciliations = reconciliations.filter(status_=st)

    if search_text:
        reconciliations = reconciliations.annotate(
            pk_str=Cast('pk', TextField())
        ).filter(
            pk_str__icontains=search_text
        )

    return JsonResponse([_serialize_reconciliation(r) for r in reconciliations], safe=False)


@account_api(['POST'])
def confirm_report(request):
    recn_pk = _get_value(request, 'pk')
    try:
        models.confirm_reconciliation(recn_pk, request.user)
    except models.Reconciliation.DoesNotExist:
        return JsonResponse(data={}, status=status.HTTP_404_NOT_FOUND)

    recn = models.Reconciliation.objects.filter(
        pk=recn_pk,
    ).select_related(
        'invoice'
    ).with_status(
    ).get()

    return JsonResponse(_serialize_reconciliation(recn))


@account_api(['GET'])
def imports(request):
    customer = _get_customer(request)
    update_import_visit_timestamp(customer)
    first_day, last_day = get_first_last_day(request)
    st = _get_value(request, 'status')
    allowed_statuses = [st for st, _ in models.RequestsFile.STATUS_TYPES]
    if st not in allowed_statuses:
        st = None

    min_first_day = datetime.date(2020, 9, 15)
    if first_day is None or first_day < min_first_day:
        first_day = min_first_day

    files = models.RequestsFile.objects.filter(
        customer=customer,
        timestamp__date__range=(first_day, last_day)
    ).order_by('-pk')
    if st:
        files = files.filter(status=st)

    base_url = reverse('the_redhuman_is:gt_customer_requests_file')
    data = [_serialize_requests_file(f, base_url) for f in files]

    return JsonResponse(data, safe=False)


@account_api(['GET'])
def requests_file(request):
    customer = _get_customer(request)

    pk = _get_value(request, 'pk')
    file_type = _get_value(request, 'type')

    return requests_file_response(pk, file_type, customer)


def _invoice_content(delivery_invoice):
    return content_response(delivery_invoice.invoice_file)


@account_api(['GET'])
def invoice(request):
    customer = _get_customer(request)
    pk = _get_value(request, 'pk')

    try:
        delivery_invoice = models.DeliveryInvoice.objects.get(
            pk=pk,
            customer=customer
        )

        return _invoice_content(delivery_invoice)

    except ObjectDoesNotExist as e:
        return HttpResponse(status=404)


INVOICE_FIELDS = [
    'pk',
    'timestamp',
]


def _serialize_invoice(delivery_invoice):
    data = _serialize_object(delivery_invoice, INVOICE_FIELDS)

    data['amount'] = separate(delivery_invoice.amount)
    data['number'] = f'{delivery_invoice.pk}-GT'

    invoice_file = delivery_invoice.invoice_file
    base_url = reverse('the_redhuman_is:gt_customer_invoice')
    data['file'] = {
        'name': os.path.basename(invoice_file.name),
        'size': _get_size(invoice_file),
        'url': base_url + '?pk={}'.format(delivery_invoice.pk)
    }

    return data


@account_api(['GET'])
def invoices(request):
    first_day, last_day = get_first_last_day(request)
    customer = _get_customer(request)

    delivery_invoices = models.DeliveryInvoice.objects.filter(
        customer=customer,
        timestamp__gte=first_day,
        timestamp__lt=last_day + datetime.timedelta(days=1)
    )

    return JsonResponse([_serialize_invoice(i) for i in delivery_invoices], safe=False)


@account_api(['POST'])
def create_invoice(request):
    customer = _get_customer(request)
    amount = _get_value(request, 'amount')

    delivery_invoice = create_delivery_invoice(
        request.user,
        customer,
        amount
    )

    return _invoice_content(delivery_invoice)


def _send_reconciliation_confirmation_notice(notification):
    formatted_date = notification.reconciliation.date.strftime('%d.%m.%Y')
    subject = f'Заявки ГетТаск за {formatted_date} подтверждены'
    body = (
        '<p>Здравствуйте!</p>'
        f'<p>Спасибо, что подтвердили заявки за {formatted_date}: {notification.hours} часов'
        f' на сумму {notification.amount} руб.</p>'
    )

    send_email(
        to=notification.recipient_email,
        subject=subject,
        html=body,
        sender='gt_docs',
    )


@csrf_exempt
@require_POST
@transaction.atomic
def daily_reconciliation_confirm(request):
    try:
        notification = DailyReconciliationNotification.objects.all(
        ).select_related(
            'reconciliation__location'
        ).select_for_update(
            of=(
                'self',
                'reconciliation'
            )
        ).with_is_confirmed(
        ).filter(
            confirmation_key=request.POST['uuid']
        ).order_by(
            'recipient'
        ).first()

    except (KeyError, ValueError, ValidationError):
        return HttpResponseBadRequest()

    if notification is None:
        status_ = 'gone'

    else:
        if not notification.is_confirmed:
            confirm_daily_reconciliation(notification.reconciliation_id, notification.recipient)
            _send_reconciliation_confirmation_notice(notification)

        status_ = 'confirmed'

    return JsonResponse({
        'status': status_
    })


@require_GET
def daily_reconciliation_details(request):
    try:
        notification = DailyReconciliationNotification.objects.all(
        ).select_related(
            'reconciliation'
        ).with_is_confirmed(
        ).filter(
            confirmation_key=request.GET['uuid']
        ).first()

    except (KeyError, ValueError, ValidationError):
        return HttpResponseBadRequest()

    if notification is None:
        result = {'status': 'gone'}

    else:
        if notification.is_confirmed:
            result = {
                'status': 'confirmed',
                'date': string_from_date(notification.reconciliation.date)
            }
        else:
            result = {
                'status': 'new',
                'hours': notification.hours,
                'amount': notification.amount,
                'date': string_from_date(notification.reconciliation.date)
            }

    return JsonResponse(result)
