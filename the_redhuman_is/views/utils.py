# -*- coding: utf-8 -*-

import datetime
import logging
import os
import time
import traceback

import magic

from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import (
    ObjectDoesNotExist,
    PermissionDenied,
)
from django.core.serializers.json import DjangoJSONEncoder

from django.db.models import Q
from django.http import (
    HttpResponse,
    Http404,
)
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone

from rest_framework import (
    exceptions,
    status,
)
from rest_framework.response import Response
from rest_framework.views import set_rollback

from urllib.parse import quote_plus

from rest_framework_simplejwt import exceptions as jwt_exceptions

from .. import models

import finance
from finance import model_utils

import applicants

from utils.date_time import (
    DATE_FORMAT,
    date_from_string
)
from the_redhuman_is.services.delivery.utils import DeliveryWorkflowError

from the_redhuman_is.tasks import send_tg_alert

dev_logger = logging.getLogger("dev_logger")


# Todo: remove?
def get_customer_account(request):
    user = request.user
    if user.is_authenticated:
        account = models.CustomerAccount.objects.filter(user=user)
        if account.exists():
            if account.count() > 1:
                dev_logger.error("Multiple CustomerAccounts for user " + user.username)
            return account.first()
    return None


def render_timesheet(request, timesheet, is_for_customer):
    turnouts = timesheet.worker_turnouts.all()
    return render(
        request,
        "the_redhuman_is/timesheet.html",
        {
            "timesheet": timesheet,
            "turnouts": turnouts,
            "is_for_customer": is_for_customer,
            "fines": {},
        }
    )


def render_image(request, image):
    customer_account = get_customer_account(request)
    return render(
        request,
        "the_redhuman_is/image.html",
        {
            "image": image,
            "is_for_customer": customer_account is not None
        }
    )


def _get_new_account(old_account):
    worker = old_account.l1
    if worker:
        return worker.worker_account.account
    else:
        return finance.models.Account.objects.get(name=old_account.name)


def _get_single(objects, message):
    if objects.exists():
        if objects.count() > 1:
            raise Exception(message)
        return objects.first()
    return None


def import_operations_and_accounts(request):
    start = time.time()
    # Clean all
    finance.models.Account.objects.all().delete()
    finance.models.Operation.objects.all().delete()
    models.WorkerOperatingAccount.objects.all().delete()
    models.CustomerOperatingAccounts.objects.all().delete()
    models.RkoOperation.objects.all().delete()

    # Сначала счета без рабочих, т.к. они могут потребоваться как родители для
    # счетов с рабочими
    for old_account in finance.models.Account.objects.filter(l1=None):
        account = finance.models.Account.objects.create(name=old_account.name)

    account_50 = model_utils.get_account("50")
    # root for all client accounts (?)
    account_60 = finance.models.Account.objects.create(name="60")
    # root for all worker accounts
    account_70 = model_utils.get_account("70")

    default_author = User.objects.get(username="redhuman")

    for old_account in finance.models.Account.objects.all().exclude(l1=None):
        worker = old_account.l1
        models.create_worker_operating_account(worker)

    for customer in models.Customer.objects.all():
        account = finance.models.Account.objects.create(name=str(customer), parent=account_60)
        models.CustomerOperatingAccounts.objects.create(customer=customer, account=account)

    for old_operation in finance.models.Operation.objects.all():
        author = default_author
        if old_operation.author:
            author = old_operation.author

        if not old_operation.debet or not old_operation.credit:
            raise Exception(
                "There is no debet or credit in operation {}.".format(old_operation.id))
        else:
            operation = finance.models.Operation.objects.create(
                timepoint=old_operation.date,
                author=author,
                comment=old_operation.comment,
                debet=_get_new_account(old_operation.debet),
                credit=_get_new_account(old_operation.credit),
                amount=old_operation.amount
            )

        # Rko
        rko = _get_single(
            models.Rko.objects.filter(operation=old_operation),
            "Multiple rkos for operation {}.".format(old_operation.id)
        )
        if rko:
            models.RkoOperation.objects.create(rko=rko, operation=operation)

        # Turnout
        turnouts = models.WorkerTurnout.objects.filter(operation_to_pay=old_operation)
        for turnout in turnouts:
            models.TurnoutOperationToPay.objects.create(turnout=turnout, operation=operation)

        turnouts = models.WorkerTurnout.objects.filter(operation_is_payed=old_operation)
        for turnout in turnouts:
            models.TurnoutOperationIsPayed.objects.create(turnout=turnout, operation=operation)

    finish = time.time()
    return HttpResponse("ok {}".format(finish - start))


# Todo: move to temporary_reports.py
def workers_wo_phones(request):
    filtered_applicants = applicants.models.active_applicants().filter(
        status__final__isnull=False
    )
    wrong_applicants = []
    for applicant in filtered_applicants:
        if not hasattr(applicant, 'worker_link'):
            if not models.Worker.objects.filter(tel_number=applicant.phone).exists():
                wrong_applicants.append(applicant)

    earliest = datetime.datetime(year=2018, month=8, day=30)
    recent_workers = models.Worker.objects.filter(
        worker_turnouts__timesheet__sheet_date__gte=earliest,
    ).exclude(
        worker_turnouts__timesheet__sheet_date__lt=earliest,
    ).filter(
        Q(tel_number__isnull=True) | Q(tel_number='')
    ).distinct()

    return render(
        request,
        'the_redhuman_is/reports/workers_wo_phones.html',
        {
            'applicants': wrong_applicants,
            'workers': recent_workers
        }
    )


def _get_value(request, key, default=None):
    value = request.GET.get(key)
    if not value:
        value = request.POST.get(key)
    if value is None:
        return default
    return value


def _get_values(request, key, default=None):
    if default is None:
        default = []
    value = request.GET.getlist(key) + request.POST.getlist(key)
    return value or default


def get_first_last_day(request, set_initial=True):
    if set_initial:
        last_day = timezone.localdate()
        first_day = last_day.replace(day=1)
    else:
        last_day = None
        first_day = None

    param_first_day = _get_value(request, 'first_day')
    if param_first_day:
        first_day = date_from_string(param_first_day)

    param_last_day = _get_value(request, 'last_day')
    if param_last_day:
        last_day = date_from_string(param_last_day)

    return first_day, last_day


def get_first_last_week_day(request):
    first_day, last_day = get_first_last_day(request, set_initial=False)
    if not last_day:
        last_day = timezone.localdate()
    if not first_day:
        first_day = last_day - datetime.timedelta(days=last_day.weekday())

    return first_day, last_day


def exception_to_json_error(status=200):
    def decorator(view_func):
        def proxy(request, *args, **kwargs):
            try:
                return view_func(request, *args, **kwargs)

            except Exception as e:
                return JsonResponse(data={'status': 'error', 'message': str(e)}, status=status)

        return proxy

    return decorator


def exception_to_500(view_func):
    def proxy(request, *args, **kwargs):
        try:
            return view_func(request, *args, **kwargs)

        except Exception as e:
            print(str(e))
            return JsonResponse(data={}, status=500)

    return proxy


def content_response(file_field):
    with file_field as f:
        f.open('rb')
        path = f.storage.path(f.name)
        content = f.file.read()
        response = HttpResponse(
            content,
            magic.from_buffer(content[:4096], mime=True)
        )
        response[
            'Content-Disposition'
        ] = "attachment; filename*=UTF-8''{}".format(quote_plus(os.path.basename(f.name)))

        return response


class DayMonthYearJSONEncoder(DjangoJSONEncoder):
    def default(self, o):
        # See "Date Time String Format" in the ECMA-262 specification.
        if isinstance(o, datetime.datetime):
            return super().default(o)
        if isinstance(o, datetime.date):
            return o.strftime(DATE_FORMAT)
        else:
            return super().default(o)


class APIJsonResponse(JsonResponse):
    def __init__(self, data, encoder=DayMonthYearJSONEncoder, **kwargs):
        super(APIJsonResponse, self).__init__(data, encoder=encoder, **kwargs)


class BadRequestError(exceptions.APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_code = 'error'
    default_detail = 'Ошибка запроса.'


class ConflictError(exceptions.PermissionDenied):
    status_code = status.HTTP_409_CONFLICT
    default_code = 'conflict'


class LockError(exceptions.APIException):
    status_code = status.HTTP_423_LOCKED
    default_code = 'locked'
    default_detail = 'Выполняется другая операция.'


class ServerError(exceptions.APIException):
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_code = 'server_error'
    default_detail = 'Внутренняя ошибка.'


def _rest_error_from_django(exc):
    from the_redhuman_is.services.delivery.utils import (
        DatabaseLockError,
        ObjectNotFoundError,
    )

    detail = None
    code = None
    if exc.args:
        detail = str(exc.args[0])

    if isinstance(exc, DeliveryWorkflowError):
        exception_class = ConflictError
    elif isinstance(exc, ObjectNotFoundError):
        exception_class = BadRequestError
        code = 'object_not_found'
    elif isinstance(exc, PermissionDenied):
        exception_class = exceptions.PermissionDenied
    elif isinstance(exc, DatabaseLockError):
        exception_class = LockError
    else:
        return exc

    return exception_class(detail=detail, code=code)


def _get_exception_headers(exc):
    headers = {}
    if getattr(exc, 'auth_header', None):
        headers['WWW-Authenticate'] = exc.auth_header
    if getattr(exc, 'wait', None):
        headers['Retry-After'] = '%d' % exc.wait
    return headers


def _get_response_data(exc: exceptions.APIException) -> dict:
    if isinstance(exc, jwt_exceptions.AuthenticationFailed):
        return exc.detail

    if isinstance(exc.detail, (list, dict)):
        data = {
            'detail': 'Неправильный формат данных.',
            'code': exc.default_code,
            'messages': exc.detail
        }
    else:
        data = {
            'detail': str(exc.detail),
            'code': exc.detail.code,
        }
    return data


def format_exception_message(exc, context):
    exc_info = repr(exc)
    request = context.get('request')
    if request is not None:
        request_info = 'View {}\nURL {} {!r}\nData {}\nUser {}#{}\n'.format(
            request.resolver_match.view_name,
            request.method,
            request.get_full_path(),
            request.data,
            request.user.username,
            request.user.pk,
        )
    else:
        request_info = None
    tb = ''.join(traceback.format_tb(exc.__traceback__))
    return '\n\n'.join((str(timezone.localtime()), exc_info, request_info, tb))


def rest_exception_handler(exc, context):
    from the_redhuman_is.services.delivery.utils import DatabaseLockError

    if isinstance(exc, Http404):
        exc = exceptions.NotFound()
    elif isinstance(exc, (PermissionDenied, ObjectDoesNotExist, DatabaseLockError)):
        exc = _rest_error_from_django(exc)

    if not isinstance(exc, exceptions.APIException):
        send_tg_alert(message=format_exception_message(exc, context))
        if not getattr(settings, 'REST_HANDLE_500', True):
            return None
        exc = ServerError(f'{exc.__class__.__name__}: {exc}')

    headers = _get_exception_headers(exc)
    set_rollback()

    return Response(_get_response_data(exc), status=exc.status_code, headers=headers)
