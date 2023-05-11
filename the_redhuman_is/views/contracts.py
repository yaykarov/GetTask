# -*- coding: utf-8 -*-

import datetime
import io
import json
import os
import re

from dal import autocomplete

from zipfile import ZipFile
from urllib.parse import quote_plus

from django import forms

from django.contrib.auth.mixins import LoginRequiredMixin

from django.db import transaction
from django.db.models import Count
from django.db.models import Q

from django.http import HttpResponse

from django.shortcuts import render, redirect

from django.urls import reverse

from django.utils import timezone

from the_redhuman_is.auth import staff_account_required
from the_redhuman_is.exceptions import WorkerException

from the_redhuman_is.forms import (
    FormExtension,
    SingleDateForm,
)

from the_redhuman_is.models import (
    Contract,
    Contractor,
    ContractorProxy,
    NoticeOfContract,
    NoticeOfTermination,
    Worker,
    add_photo,
    get_worker_photos,
)

from utils.date_time import (
    DATE_FORMAT,
    date_from_string,
    days_from_interval,
    first_last_day_from_month,
    string_from_date,
)

from doc_templates import doc_factory


class ContractorAutocomplete(
        LoginRequiredMixin,
        autocomplete.Select2QuerySetView):

    def get_queryset(self):
        contractors = Contractor.objects.all()
        if self.q:
            contractors = contractors.filter(
                full_name__icontains=self.q
            )

        return contractors


class ContractorProxyAutocomplete(
        LoginRequiredMixin,
        autocomplete.Select2QuerySetView):

    def get_queryset(self):
        contractor_pk = self.forwarded.get('contractor')
        if contractor_pk:
            proxies = ContractorProxy.objects.filter(
                active=True,
                contractor__pk=contractor_pk
            )
            if self.q:
                proxies = proxies.filter(
                    Q(number__icontains=self.q) |
                    Q(worker__name__icontains=self.q) |
                    Q(worker__last_name__icontains=self.q) |
                    Q(worker__patronymic__icontains=self.q)
                )
            return proxies
        return ContractorProxy.objects.none()


class SingleContractorForm(FormExtension):
    contractor = forms.ModelChoiceField(
        queryset=Contractor.objects.all(),
        label='Подрядчик',
        widget=autocomplete.ModelSelect2(
            url='the_redhuman_is:contractor_autocomplete',
            attrs={ 'class': 'form-control form-control-sm' }
        ),
        required=False
    )


class ContractorProxyForm(FormExtension):
    proxy = forms.ModelChoiceField(
        label="Доверенность",
        queryset=ContractorProxy.objects.all(),
        widget=autocomplete.ModelSelect2(
            url='the_redhuman_is:contractor_proxy_autocomplete',
            forward=['contractor']
        ),
        required=False
    )


# Todo: move to models?
def _end_date_suggest(contract):
    worker = contract.c_worker

    # Don't care about these citizenships
    if worker.citizenship.name in ['РФ', 'Белоруссия']:
        return datetime.date(year=2100, month=1, day=1)

    dates = []

    if worker.m_date_of_issue and not worker.m_date_of_exp:
        raise Exception(
            'У работника {} не заполнена дата окончания действия МК!'.format(
                worker
            )
        )

    if worker.m_date_of_exp:
        dates.append(worker.m_date_of_exp)

    passport = worker.actual_passport

    if not passport:
        raise Exception(
            'У работника {} несколько паспортов либо нет ни одного!'.format(worker)
        )

    if not passport.date_of_exp:
        raise Exception(
            'У работника {} не заполнена дата окончания действия паспорта!'.format(
                worker
            )
        )

    dates.append(passport.date_of_exp)

    registration = worker.actual_registration

    if not registration or not registration.is_actual:
        raise Exception(
            'У работника {} несколько документов о регистрации либо нет ни одного!'.format(
                worker
            )
        )

    return min(dates)


def _filter_contractor(function):
    def _proxy(contractor=None, *args, **kwargs):
        contracts = function(*args, **kwargs)
        if contractor:
            contracts = contracts.filter(
                c_worker__contract__contractor=contractor
            )
        return contracts
    return _proxy


def _contracts_active():
    return Contract.objects.filter(is_actual=True)


def _contracts_clean():
    return _contracts_active().filter(
        begin_date__isnull=True,
    )


def _contracts_to_register():
    deadline = timezone.now() - datetime.timedelta(days=4)

    workers_pks = Worker.objects.filter(
        worker_turnouts__timesheet__sheet_date__gte=deadline
    ).distinct(
    ).values_list(
        'id',
        flat=True
    )

    workers = Worker.objects.filter(
        pk__in=workers_pks
    ).annotate(
        turnout_count=Count('worker_turnouts')
    ).filter(
        turnout_count__gte=7
    ).distinct()

    contracts = _contracts_active().filter(
        begin_date__isnull=True,
        c_worker__in=workers
    ).distinct(
    )

    doc_deadline = (timezone.now() + datetime.timedelta(days=7)).date()
    result = []
    for contract in contracts:
        if _end_date_suggest(contract) > doc_deadline:
            result.append(contract.pk)

    return Contract.objects.filter(
        pk__in=result
    )


@_filter_contractor
def _contracts_registration_in_progress():
    return _contracts_active().filter(
        begin_date__isnull=False
    ).filter(
        noticeofcontract__photos__isnull=True
    )


def _contracts_registration_expiring():
    deadline = timezone.now() - datetime.timedelta(days=2)

    return _contracts_registration_in_progress().filter(
        begin_date__lt=deadline
    )


def _contracts_registered_with_notification():
    return _contracts_active().filter(
        noticeofcontract__photos__isnull=False
    ).distinct(
    )


@_filter_contractor
def _contracts_registered_with_notification_without_snils():
    return _contracts_registered_with_notification().filter(
        c_worker__snils__isnull=True
    )


@_filter_contractor
def _contracts_registered_with_notification_with_snils():
    return _contracts_registered_with_notification().filter(
        c_worker__snils__isnull=False
    )


def _contracts_to_fire():
    deadline = timezone.now() - datetime.timedelta(days=7)
    return _contracts_registered_with_notification().exclude(
        c_worker__worker_turnouts__timesheet__sheet_date__gte=deadline
    )


def _contracts_firing_in_progress():
    return Contract.objects.filter(
        is_actual=False,
        noticeofcontract__photos__isnull=False,
        noticeoftermination__photos__isnull=True,
    ).distinct()


def _contracts_firing_expiring():
    deadline = timezone.now() - datetime.timedelta(days=2)

    return _contracts_firing_in_progress().filter(
        noticeoftermination__date__lt=deadline
    )


def _contracts_fired():
    return Contract.objects.filter(
        is_actual=False,
        noticeofcontract__photos__isnull=False,
        noticeoftermination__photos__isnull=False,
    ).distinct()


def _fill_items(filters, display):
    contracts = None

    filter_items = []
    for key, data in filters.items():
        title, hint, actions, getter, style = data
        item = {
            'filter': getter(),
            'title': title,
            'hint': hint,
            'actions': actions,
            'key': key,
            'highlighted': False,
            'style': style,
        }
        if key == display:
            item['highlighted'] = True

        filter_items.append(item)

    return filter_items


def _hint(flags):
    titles = [
        ('Дата начала', 'есть', 'нет'),          # 0
        ('Справка об УоЗ', 'есть', 'нет'),       # 1
        ('СНИЛС', 'есть', 'нет (или не важно)'), # 2
        ('Дата расторжения', 'есть', 'нет'),     # 3
        ('Справка об УоР', 'есть', 'нет'),       # 4
        ('Отсутствовал больше 7 дней', 'да', 'не важно'),        # 5
        ('Находился в статусе больше 3 дней', 'да', 'не важно'), # 6
    ]

    text = ''
    for i in range(len(titles)):
        title, yes, no = titles[i]
        if (flags >> i) & 1:
            answer = yes
        else:
            answer = no
        text += '{}: {}\n'.format(title, answer)

    return text


def _actions(flags):
    actions = [
        'set_contractor',            # 0
        'set_begin_date',            # 1
        'set_end_date',              # 2
        'download_contract_notices', # 3
        'download_terminate_notices',# 4
    ]

    result = {}
    for i in range(len(actions)):
        if (flags >> i) & 1:
            result[actions[i]] = True

    return result


FILTERS_CONCLUSION = {
    'active': (
        'Договора без даты начала',
        'Вообще все активные договора,\nу которых нет даты начала,\n(но дата окончания может быть установлена\nна основании даты окончания документа)',
        _actions(0b00011),
        _contracts_clean,
        'primary'
    ),
    'to_register': (
        'На оформление',
        'Есть выходы за последние 4 дня,\nвсего выходов больше 7,\nдокументы заканчиваются не раньше, чем через 7 дней',
        _actions(0b00011),
        _contracts_to_register,
        'primary'
    ),
    'registration_in_progress': (
        'В оформлении',
        _hint(0b1),
        _actions(0b01101),
        _contracts_registration_in_progress,
        'primary'
    ),
    'registration_expiring': (
        '',
        _hint(0b1000001),
        _actions(0b01101),
        _contracts_registration_expiring,
        'danger'
    ),
    'snils_expiring': (
        'Уведомлено, нет СНИЛС',
        _hint(0b11),
        _actions(0b00100),
        _contracts_registered_with_notification_without_snils,
        'danger'
    ),
    'registered_with_notification_with_snils': (
        'Уведомлено, СНИЛС есть',
        _hint(0b111),
        _actions(0b10100),
        _contracts_registered_with_notification_with_snils,
        'success'
    ),
}

FILTERS_TERMINATION = {
    'to_fire': (
        'На расторжение',
        _hint(0b100011),
        _actions(0b10100),
        _contracts_to_fire,
        'primary'
    ),
    'firing_in_progress': (
        'Расторгаются',
        _hint(0b1011),
        _actions(0b10000),
        _contracts_firing_in_progress,
        'primary'
    ),
    'firing_expiring': (
        '',
        _hint(0b1001011),
        _actions(0b10000),
        _contracts_firing_expiring,
        'danger'
    ),
    'fired': (
        'Расторгнуто',
        _hint(0b0011011),
        _actions(0b00000),
        _contracts_fired,
        'success'
    ),
}


def filtered_contracts(filter_name):
    def _get_query(src, key):
        if key in src:
            return list(src[key])[3]()
        return None

    if filter_name == 'all':
        return Contract.objects.all()

    return (
        _get_query(FILTERS_CONCLUSION, filter_name) or
        _get_query(FILTERS_TERMINATION, filter_name) or
        _get_query(FILTERS_CONCLUSION, 'to_register')
    )


@staff_account_required
def contracts_list(request):
    display = request.GET.get('display')
    if display not in (list(FILTERS_CONCLUSION.keys()) + list(FILTERS_TERMINATION.keys())):
        display = 'to_register'

    items = [
        ('Найм: ', _fill_items(FILTERS_CONCLUSION, display)),
        ('Увольнение: ', _fill_items(FILTERS_TERMINATION, display))
    ]

    actions = {}
    for title, row in items:
        for item in row:
            if item['key'] == display:
                contracts = item['filter']
                actions = item['actions']

    contracts = contracts.select_related(
        'c_worker',
    )

    return render(
        request,
        'the_redhuman_is/contracts/list.html',
        {
            'filter_items': items,
            'actions': actions,
            'conclusion_form': SingleDateForm('conclusion_date', 'table'),
            'termination_form': SingleDateForm('termination_date', 'table'),
            'contractor_form': SingleContractorForm('table'),
            'proxy_form': ContractorProxyForm('table'),
            'contracts': contracts,
        }
    )


# Todo: move to models?
def _contract_images(contract):
    images = []

    class ImageAdder(object):
        def __init__(self, prefix):
            self.prefix = prefix
            self.index = 1

        def __call__(self, image):
            if image:
                tmp, ext = os.path.splitext(image.path)
                images.append(
                    (
                        '{} {}{}'.format(
                            self.prefix,
                            self.index,
                            ext
                        ),
                        image
                    )
                )
                self.index += 1

    add_contract_image = ImageAdder('Договор №{}, фото'.format(contract.number))

    for image in [contract.image, contract.image2, contract.image3]:
        add_contract_image(image)
    for photo in contract.get_images:
        add_contract_image(photo.image)

    add_worker_image = ImageAdder('Документы, фото')

    worker = contract.c_worker
    for photo in get_worker_photos(worker):
        add_worker_image(photo.image)

    return images


def _selected_contracts(request):
    contracts_ids = request.POST.getlist('id') + request.GET.getlist('id')
    contracts = Contract.objects.filter(
        pk__in=contracts_ids,
    )
    return contracts


# Todo: move to some utils?
def _make_zip_response(filename, callback):
    proxy_file = io.BytesIO()
    with ZipFile(proxy_file, "w") as zip_file:
        callback(zip_file)

    response = HttpResponse(content_type='application/zip')
    response[
        'Content-Disposition'
    ] = "attachment; filename*=UTF-8''{}".format(
        quote_plus(filename)
    )

    response.write(proxy_file.getvalue())

    return response


def _add_images_to_zip(zip_file, contracts):
    for contract in contracts:
        for filename, image in _contract_images(contract):
            with open(image.path, "rb") as image_contents:
                zip_file.writestr(
                    '{}/{}'.format(contract.c_worker, filename),
                    image_contents.read()
                )


@staff_account_required
def download_images_for_contracts(request):
    def _fill_zip(zip_file):
        _add_images_to_zip(zip_file, _selected_contracts(request))

    return _make_zip_response(
        'Photos_{}.zip'.format(
            timezone.now().strftime(DATE_FORMAT)
        ),
        _fill_zip
    )


@staff_account_required
# hire
def set_dates(request):
    begin_date = date_from_string(request.POST.get('conclusion_date'))
    if not begin_date:
        raise Exception('Begin date should not be empty!')

    contracts = _selected_contracts(request)
    if not request.user.is_superuser:
        if contracts.filter(begin_date__isnull=False).exists():
            raise Exception('Selected contracts should not have begin date!')

    with transaction.atomic():
        for contract in contracts:
            contract.begin_date = begin_date
            contract.end_date = _end_date_suggest(contract)
            contract.save()
            notification, created = NoticeOfContract.objects.get_or_create(
                contract=contract
            )
            notification.date = begin_date
            notification.save()

    return redirect('the_redhuman_is:contracts_list')


@staff_account_required
def fire(request):
    termination_date = date_from_string(request.POST.get('termination_date'))
    if not termination_date:
        raise Exception('Termination date should not be empty!')

    contracts = _selected_contracts(request)
    if not request.user.is_superuser:
        if contracts.filter(noticeoftermination__isnull=False).exists():
            raise Exception('Notification of termination already exists!')

    with transaction.atomic():
        for contract in contracts:
            contract.is_actual = False
            contract.save()
            notification, created = NoticeOfTermination.objects.get_or_create(
                contract=contract
            )
            notification.date = termination_date
            notification.save()

    return redirect('the_redhuman_is:contracts_list')


@staff_account_required
def set_contractor(request):
    contractor_pk = request.POST.get('contractor')
    if contractor_pk:
        contractor = Contractor.objects.get(pk=contractor_pk)

        contracts = _selected_contracts(request)
        if not request.user.is_superuser:
            if contracts.filter(contractor__isnull=False).exists():
                raise Exception(
                    'Selected contracts should not have contractor!'
                )

        with transaction.atomic():
            for contract in contracts:
                contract.contractor = contractor
                contract.save()

    return redirect('the_redhuman_is:contracts_list')


@staff_account_required
def attach_image(request):
    contract = Contract.objects.get(pk=request.POST['contract_id'])
    notification_type = request.POST.get('type')
    if notification_type == 'contract':
        notification, created = NoticeOfContract.objects.get_or_create(
            contract=contract
        )
    elif notification_type == 'terminate':
        notification, created = NoticeOfTermination.objects.get_or_create(
            contract=contract
        )
    else:
        raise Exception('Unknown notification type')

    for image in request.FILES.getlist('images'):
        add_photo(notification, image)

    return redirect(request.POST.get('next', '/'))


def _notification_list(
            contracts,
            proxy,
            notification_type
        ):

    if notification_type == 'contract':
        notification_prefix = 'УоЗ'
        Notification = NoticeOfContract
        create_document = getattr(doc_factory, 'notice_of_contract_document')
        create_reference = getattr(
            doc_factory,
            'reference_of_notification_of_contract'
        )
    elif notification_type == 'terminate':
        notification_prefix = 'УоР'
        Notification = NoticeOfTermination
        create_document = getattr(doc_factory, 'notification_of_termination_document')
        create_reference = getattr(
            doc_factory,
            'reference_of_notification_of_termination'
        )
    else:
        raise Exception('Unknown notification type')

    errors = []

    def _add_notifications(zip_file):
        for contract in contracts:
            worker = contract.c_worker

            notification = Notification.objects.get(
                contract=contract
            )
            try:
                values = notification.make_dict(proxy)
            except WorkerException as exception:
                errors.append(
                    {
                        'worker_id': exception.worker_id,
                        'errors': exception.get_value()
                    },
                )
            else:
                notification_date = notification.date.strftime(DATE_FORMAT)
                filename_suffix = '{} от {} №{} договор №{}.odt'.format(
                    notification_prefix,
                    notification_date,
                    notification.id,
                    contract.number
                )
                doc = create_document(values)
                filename = '{}/{}'.format(
                    worker,
                    filename_suffix
                )
                zip_file.writestr(filename, doc)

                reference = create_reference(
                    contract.contractor.full_name,
                    str(worker)
                )
                reference_filenme = '{}/Справка об {}'.format(
                    worker,
                    filename_suffix
                )
                zip_file.writestr(reference_filenme, reference)

    def _fill_zip_conclusion(zip_file):
        _add_notifications(zip_file)
        _add_images_to_zip(zip_file, contracts)

    if notification_type == 'contract':
        fill_zip = _fill_zip_conclusion
    else:
        fill_zip = _add_notifications

    response = _make_zip_response(
        '{}_{}.zip'.format(
            notification_prefix,
            timezone.now().strftime(DATE_FORMAT)
        ),
        fill_zip
    )

    return errors, response


@staff_account_required
def notifications_list(request, notification_type):
    contracts = _selected_contracts(request)
    proxy = None
    proxy_pk = request.GET.get('proxy')
    if proxy_pk:
        proxy = ContractorProxy.objects.get(pk=proxy_pk)

    errors, response = _notification_list(
        contracts,
        proxy,
        notification_type
    )

    if errors:
        request.session['workers_error'] = json.dumps(errors)
        return redirect(reverse('the_redhuman_is:notice_download_status'))
    else:
        return response


def _contracts_number(contractor, day):
    contracts = Contract.objects.filter(
        contractor=contractor,
        begin_date__lte=day
    )
    active = contracts.filter(
        noticeoftermination__isnull=True
    )
    active_that_day = contracts.filter(
        noticeoftermination__isnull=False,
        noticeoftermination__date__gt=day,
    )
    workers = Worker.objects.filter(
        Q(contract__in=active) |
        Q(contract__in=active_that_day)
    ).distinct()

    return workers.count()


def _average_contracts_in_month(contractor, year, month, last_day=None):
    first_day, last_date = first_last_day_from_month(year, month)
    if not last_day:
        last_day = last_date
    count = 0
    days = days_from_interval(first_day, last_day)
    for day in days:
        count += _contracts_number(contractor, day)
    return count / len(days)


def _average_contracs_(contractor, last_day):
    months = [i + 1 for i in range(last_day.month)]
    count = 0
    for month in months[:-1]:
        count += _average_contracts_in_month(contractor, last_day.year, month)
    count += _average_contracts_in_month(
        contractor,
        last_day.year,
        months[-1],
        last_day
    )
    return count / len(months)


@staff_account_required
def contractors_summary(request):
    contractors = Contractor.objects.all()
    today = datetime.date.today()
    data = []
    for contractor in contractors:
        data.append((
            contractor,
            _contracts_registered_with_notification_with_snils(
                contractor
            ).count(),
            _contracts_registration_in_progress(contractor).count(),
            _contracts_registered_with_notification_without_snils(
                contractor
            ).count(),
            _average_contracs_(contractor, today)
        ))

    return render(
        request,
        'the_redhuman_is/contracts/summary.html',
        {
            'today': today,
            'data' : data
        }
    )


@staff_account_required
def contractor_workers(request):
    contractor_param = request.GET.get('contractor')
    filter_param = request.GET.get('filter')

    if filter_param == 'reg_starting':
        contracts = _contracts_registration_in_progress(contractor_param)
    elif filter_param == 'reg_finishing':
        contracts = _contracts_registered_with_notification_without_snils(
            contractor_param
        )
    else:
        contracts = _contracts_registered_with_notification_with_snils(
            contractor_param
        )

    workers = Worker.objects.filter(
        contract__in=contracts
    ).distinct(
    )

    return render(
        request,
        'the_redhuman_is/reports/workers_list.html',
        {
            'workers': workers,
        }
    )


@staff_account_required
def notification_of_contract_images(request, pk):
    notification = NoticeOfContract.objects.get(pk=pk)
    return render(
        request,
        'the_redhuman_is/reports/photos_list.html',
        {
            'photos': notification.photos.all()
        }
    )


@staff_account_required
def notification_of_termination_images(request, pk):
    notification = NoticeOfTermination.objects.get(pk=pk)
    return render(
        request,
        'the_redhuman_is/reports/photos_list.html',
        {
            'photos': notification.photos.all()
        }
    )


@staff_account_required
def export_csv(request):
    contractor = request.GET.get('contractor')

    default_style = ''
    date_style = 'date'

    columns = [
        ('Фамилия',                  'c_worker__last_name',                                 default_style),
        ('Имя',                      'c_worker__name',                                      default_style),
        ('Отчество',                 'c_worker__patronymic',                                default_style),
        ('Телефон',                  'c_worker__tel_number',                                default_style),
        ('Дата рождения',            'c_worker__birth_date',                                date_style),
        ('Место рождения',           'c_worker__place_of_birth__name',                      default_style),
        ('МК серия',                 'c_worker__mig_series',                                default_style),
        ('МК номер',                 'c_worker__mig_number',                                default_style),
        ('МК Дата выдачи',           'c_worker__m_date_of_issue',                           date_style),
        ('МК Дата окончания',        'c_worker__m_date_of_exp',                             date_style),
        ('Гражданство',              'c_worker__citizenship__name',                         default_style),
        ('Пол',                      'c_worker__sex',                                       default_style),
        ('Паспорт, тип',             'c_worker__workerpassport__passport_type',             default_style),
        ('Паспорт, серия',           'c_worker__workerpassport__passport_series',           default_style),
        ('Паспорт, номер',           'c_worker__workerpassport__another_passport_number',   default_style),
        ('Паспорт, дата выдачи',     'c_worker__workerpassport__date_of_issue',             date_style),
        ('Паспорт, дата окончания',  'c_worker__workerpassport__date_of_exp',               date_style),
        ('Паспорт, выдан',           'c_worker__workerpassport__issued_by',                 default_style),
        ('Регистрация, дата выдачи', 'c_worker__workerregistration__r_date_of_issue',       date_style),
        ('Регистрация, город',       'c_worker__workerregistration__city',                  default_style),
        ('Регистрация, улица',       'c_worker__workerregistration__street',                default_style),
        ('Регистрация, дом',         'c_worker__workerregistration__house_number',          default_style),
        ('Регистрация, строение',    'c_worker__workerregistration__building_number',       default_style),
        ('Регистрация, помещение',   'c_worker__workerregistration__appt_number',           default_style),
        ('Должность',                'c_worker__position',                                  default_style),
        ('Трудовой/ГПХ',             'cont_type',                                           default_style),
        ('Номер договора',           'number',                                              default_style),
        ('Дата заключения',          'begin_date',                                          date_style),
        ('Дата окончания',           'end_date',                                            date_style),
        ('id',                       'c_worker__id',                                        default_style),
    ]

    def index_for_key(key_to_find):
        i = 0
        for caption, key, style in columns:
            if key == key_to_find:
                return i
            i += 1

    rows = Contract.objects.filter(
        is_actual=True,
        begin_date__isnull=False,
        c_worker__workerregistration__is_actual=True,
        c_worker__workerpassport__is_actual=True,
        contractor=contractor
    ).values_list(
        *[key for caption, key, style in columns]
    )

    RX = re.compile("^(\D+)(\d+)$")

    def passport_series_number(series, number):
        if series is None:
            series = "none"
        if number is None:
            number = "none"
        m = RX.match(number)
        if m:
            return m.group(1), m.group(2)
        return series, number

    def passport_s_and_num(column):
        s = rows[column][index_for_key('c_worker__workerpassport__passport_series')]
        n = rows[column][index_for_key('c_worker__workerpassport__another_passport_number')]
        return passport_series_number(s, n)

    def passport_series(column):
        s, n = passport_s_and_num(column)
        return s

    def passport_num(column):
        s, n = passport_s_and_num(column)
        return n

    extra_hooks = {
        'c_worker__workerpassport__passport_series': passport_series,
        'c_worker__workerpassport__another_passport_number': passport_num
    }

    captions = [caption for caption, key, style in columns]
    csv = ';'.join(captions) + '\n'

    for row_num in range(len(rows)):
        values = []
        for col_num in range(len(columns)):
            caption, key, style = columns[col_num]
            value = rows[row_num][col_num]
            if style == 'date':
                value = string_from_date(value)
            elif key in extra_hooks.keys():
                value = extra_hooks[key](row_num)
            if value is None:
                value = ''
            values.append(str(value))
        csv += ';'.join(values) + '\n'

    response = HttpResponse(csv.encode('cp1251'), content_type='text/csv')
    response[
        'Content-Disposition'
    ] = "attachment; filename*=CP1251''contracts.csv"
    return response
