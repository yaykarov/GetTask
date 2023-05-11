import re
from datetime import timedelta
from functools import cached_property

from django.contrib.contenttypes.fields import GenericRelation
from django.db import models
from django.db.models import Max
from django.utils import timezone

from constance import config

from the_redhuman_is.exceptions import WorkerException
from the_redhuman_is.models.photo import (
    Photo,
    get_photos,
)
from the_redhuman_is.models.worker import (
    Worker,
    WorkerPassport,
)
from utils import as_default_timezone


class Contractor(models.Model):
    department_of_internal_affairs = models.CharField(
        verbose_name='Название отделения МВД',
        max_length=160
    )
    is_legal_entity = models.BooleanField(
        verbose_name='Является ли подрядчик юридическим лицом (False, если ИП)'
    )
    full_name = models.CharField(
        verbose_name='Полное наименование организации/ИП',
        max_length=160
    )
    # Todo: checksum validation?
    reg_number = models.CharField(
        verbose_name='Номер регистрации (ОГРН/ОГРНИП)',
        max_length=20
    )
    tax_number = models.CharField(
        verbose_name='Идентификационный номер налогоплательщика (ИНН)',
        max_length=20
    )
    reason_code = models.CharField(
        verbose_name='Код причины постановки на учет (КПП)',
        max_length=20,
        blank=True,
        null=True
    )
    full_address = models.CharField(
        verbose_name='Адрес места нахождения',
        max_length=160
    )
    phone_number = models.CharField(
        verbose_name='Контактный телефон',
        max_length=20
    )
    manager_position = models.CharField(
        verbose_name='Должность руководителя',
        max_length=160
    )
    manager_name = models.CharField(
        verbose_name='Фамилия и инициалы руководителя',
        max_length=160
    )

    # Todo: change this somehow
    work_address = models.CharField(
        verbose_name='Адрес места трудовой деятельности',
        max_length=160
    )

    def __str__(self):
        return self.full_name


# Доверенность
class ContractorProxy(models.Model):
    contractor = models.ForeignKey(Contractor, on_delete=models.CASCADE)
    worker = models.ForeignKey(Worker, on_delete=models.PROTECT)
    active = models.BooleanField(default=True)
    number = models.CharField(
        verbose_name='Номер доверенности',
        max_length=20
    )
    issue_date = models.DateField(
        verbose_name='Дата доверенности'
    )

    def __str__(self):
        return '{} №{} от {}'.format(
            self.worker,
            self.number,
            self.issue_date.strftime('%d.%m.%Y')
        )


class PreferredContractor(models.Model):
    contractor = models.ForeignKey(Contractor, on_delete=models.CASCADE)
    location = models.OneToOneField(
        'CustomerLocation',
        on_delete=models.CASCADE)


def default_contractor():
    return Contractor.objects.get(
        full_name__icontains='АЛЬФА-ГРУПП'
    )


def contract_upload_location(instance, filename):
    return f'workers/{instance.c_worker}/contract_{filename}'


class Contract(models.Model):
    created_date = models.DateField(
        'Дата создания записи',
        auto_now_add=True,
        blank=True,
        null=True)
    begin_date = models.DateField(
        'Дата заключения',
        blank=True,
        null=True)
    end_date = models.DateField(
        'Дата окончания',
        blank=True,
        null=True)
    cont_type = models.CharField(
        'Тип договора',
        blank=True,
        null=True,
        max_length=100,
        choices=(
            ('Трудовой', 'Трудовой'),
            ('ГПХ', 'ГПХ'),
        ),
        default='ГПХ'
    )
    # Todo: rename to worker
    c_worker = models.ForeignKey(
        Worker,
        on_delete=models.CASCADE,
        related_name='contract')
    is_actual = models.BooleanField(
        'Действующий',
        default=True)
    number = models.IntegerField(
        'Номер договора',
        blank=True,
        null=True,
    )
    # Todo: make it not-nullable
    contractor = models.ForeignKey(
        Contractor,
        on_delete=models.PROTECT,
        related_name='contracts',
        null=True,
        blank=True)

    # Todo: migrate these images to a Photo
    image = models.ImageField(
        'Страница №1',
        null=True,
        blank=True,
        upload_to=contract_upload_location)
    image2 = models.ImageField(
        'Страница №2',
        null=True,
        blank=True,
        upload_to=contract_upload_location)
    image3 = models.ImageField(
        'Приложение №1',
        null=True,
        blank=True,
        upload_to=contract_upload_location)

    class Meta:
        ordering = ('-id', '-begin_date')

    def save(self, *args, **kwargs):
        if self.id:
            if self.contractor:
                current = Contract.objects.get(pk=self.id)
                if self.contractor != current.contractor:
                    max_number = Contract.objects.filter(
                        contractor=self.contractor
                    ).aggregate(
                        Max('number')
                    )['number__max'] or 0

                    self.number = max_number + 1
            else:
                self.number = None

        if self.is_actual:
            Contract.objects.filter(
                c_worker=self.c_worker
            ).update(is_actual=False)
        super(Contract, self).save(*args, **kwargs)

    def __str__(self):
        if self.begin_date is None:
            return '{0} №{1}'.format(self.c_worker, self.pk)
        else:
            begin_date = self.begin_date.strftime('%d.%m.%Y')
            return '{0} №{1} {2}'.format(self.c_worker, self.pk, begin_date)

    def days_before_finish(self):
        if self.end_date is not None:
            td = self.end_date - timezone.now().date()
            return td.days if td.days > 0 else 0

    @property
    def duration(self):
        if self.end_date is None or self.begin_date is None:
            return None
        td = self.end_date - self.begin_date
        return td.days

    def _not_last_days(self) -> bool:
        edge_delta = timedelta(days=config.CONTRACT_EDGE_DAYS)
        diff = self.end_date - timezone.now().date()
        return edge_delta < diff

    def _last_one_day(self) -> bool:
        return timedelta(days=1) >= self.end_date - timezone.now().date()

    @cached_property
    def conclude_notice(self) -> 'NoticeOfContract':
        return self.noticeofcontract

    @cached_property
    def termination_notice(self) -> 'NoticeOfTermination':
        return self.noticeoftermination

    # Todo: bad name for a property
    # Warning: old image fields still in use
    @property
    def get_images(self):
        return get_photos(self)


def _make_notification_dict(contract, proxy, doc_date):
    # Todo: merge with 'exceptions' mechanism
    if proxy and contract.contractor != proxy.contractor:
        raise Exception(
            'Доверенность "{}" оформлена на подрядчика "{}". ' \
            'Договор "{}" заключен с подрядчиком "{}". При формировании ' \
            'уведомления подрядчик должен быть един.'.format(
                proxy,
                proxy.contractor,
                contract,
                contract.contractor
            )
        )

    def _d_m_y(date):
        date_str = date.strftime('%Y-%m-%d')
        return date_str[8:], date_str[5:7], date_str[:4]

    def _d_M_y(date):
        MONTHS = {
            '01': 'Января',
            '02': 'Февраля',
            '03': 'Марта',
            '04': 'Апреля',
            '05': 'Мая',
            '06': 'Июня',
            '07': 'Июля',
            '08': 'Августа',
            '09': 'Сентября',
            '10': 'Октября',
            '11': 'Ноября',
            '12': 'Декабря',
        }
        d, m, y = _d_m_y(date)
        return d, MONTHS[m], y

    exceptions = []
    values = {}

    contractor = contract.contractor
    if contractor:
        values[
            'contractor_department_of_internal_affairs'
        ] = contractor.department_of_internal_affairs
        if contractor.is_legal_entity:
            reg_number_prefix = 'ОГРН {}'
            values['contractor_legal_entity'] = 'X'
            values['contractor_tax_and_reason_code'] = 'ИНН {} КПП {}'.format(
                contractor.tax_number,
                contractor.reason_code
            )
        else:
            reg_number_prefix = 'ОГРНИП {}'
            values['contractor_individual'] = 'X'
            values['contractor_tax_and_reason_code'] = 'ИНН {}'.format(
                contractor.tax_number,
            )
        values['contractor_full_name'] = contractor.full_name
        values['contractor_reg_number'] = reg_number_prefix.format(
            contractor.reg_number
        )
        values['contractor_full_address'] = contractor.full_address
        values['contractor_phone_number'] = contractor.phone_number
        values['contractor_manager_position'] = contractor.manager_position
        values['contractor_manager_name'] = contractor.manager_name
        values['contractor_work_address'] = contractor.work_address

        if proxy:
            values['contractor_proxy_number'] = proxy.number
            proxy_worker = proxy.worker
            values['contractor_proxy_name'] = str(proxy_worker)
            passport = proxy_worker.actual_passport
            values[
                'contractor_proxy_passport_series'
            ] = passport.passport_series
            values[
                'contractor_proxy_passport_number'
            ] = passport.another_passport_number
            values[
                'contractor_proxy_passport_issued_by'
            ] = passport.issued_by

            d, m, y = _d_M_y(proxy.issue_date)
            values['contractor_proxy_issue_date_day'] = d
            values['contractor_proxy_issue_date_month'] = m
            values['contractor_proxy_issue_date_year'] = y[2:]

            d, m, y = _d_M_y(passport.date_of_issue)
            values['contractor_proxy_passport_issue_date_day'] = d
            values['contractor_proxy_passport_issue_date_month'] = m
            values['contractor_proxy_passport_issue_date_year'] = y
    else:
        exceptions.append('contractor')

    worker = contract.c_worker

    try:
        values['last_name'] = worker.last_name.upper()
    except AttributeError:
        exceptions.append('lastname')
    try:
        values['name'] = worker.name.upper()
    except AttributeError:
        exceptions.append('name')

    if worker.patronymic:
        values['patronymic'] = worker.patronymic.upper()
    else:
        values['patronymic'] = ' '

    if worker.citizenship:
        values['citizenship'] = worker.citizenship.name.upper()
    else:
        values['citizenship'] = ' '

    if worker.place_of_birth:
        values['place_of_birth'] = worker.place_of_birth.name.upper()
    else:
        values['place_of_birth'] = ' '
    try:
        d, m, y = _d_m_y(worker.birth_date)
        values['birth_date_day'] = d
        values['birth_date_month'] = m
        values['birth_date_year'] = y
    except:
        exceptions.append('birth_date')

    if worker.sex == 'Муж':
        values['sex_m'] = 'X'
        values['sex_w'] = ''
    elif worker.sex == 'Жен':
        values['sex_m'] = ''
        values['sex_w'] = 'X'

    workerpass = worker.actual_passport
    if not workerpass:
        exceptions.append('workerpass')
    else:
        if not workerpass.another_passport_number:
            exceptions.append('workerpass')
        else:
            values['passport'] = 'ПАСПОРТ'
            rx = re.compile('^(\D+)(\d+)$')
            m = rx.match(workerpass.another_passport_number)
            if m:
                values['pass_series'] = m.group(1)
                values['pass_num'] = m.group(2)
            else:
                # Todo?
                values['pass_series'] = ''
                values['pass_num'] = workerpass.another_passport_number

        if workerpass.date_of_issue:
            d, m, y = _d_m_y(workerpass.date_of_issue)
            values['pass_date_of_issue_day'] = d
            values['pass_date_of_issue_month'] = m
            values['pass_date_of_issue_year'] = y
        else:
            exceptions.append('pass_date_of_issue')
        if workerpass.issued_by:
            values['pass_issued_by'] = workerpass.issued_by.upper()
        else:
            exceptions.append('pass_issued_by')

    values['mig_series_number'] = '{0} {1}'.format(
        worker.mig_series,
        worker.mig_number
    )

    try:
        d, m, y = _d_m_y(worker.m_date_of_issue)
        values['m_day'] = d
        values['m_month'] = m
        values['m_year'] = y
    except:
        exceptions.append('mig_date')

    workerreg = worker.actual_registration
    if not workerreg:
        exceptions.append('registration')
    else:
        if (not workerreg.building_number) and (not workerreg.appt_number):
            values['reg_address'] = 'ГОРОД {0} УЛИЦА {1} ДОМ {2}'.format(
                workerreg.city,
                workerreg.street,
                workerreg.house_number
            ).upper()
        elif not workerreg.building_number:
            values['reg_address'] = 'ГОРОД {0} УЛИЦА {1} ДОМ {2} КВАРТИРА {3}'.format(
                workerreg.city, workerreg.street, workerreg.house_number,
                workerreg.appt_number).upper()
        elif not workerreg.appt_number:
            values['reg_address'] = 'ГОРОД {0} УЛИЦА {1} ДОМ {2} СТРОЕНИЕ {3}'.format(
                workerreg.city, workerreg.street, workerreg.house_number,
                workerreg.building_number).upper()
        else:
            values['reg_address'] = 'ГОРОД {0} УЛИЦА {1} ДОМ {2} СТРОЕНИЕ {3} КВАРТИРА {4}'.format(
                workerreg.city, workerreg.street, workerreg.house_number,
                workerreg.building_number, workerreg.appt_number).upper()
        if workerreg.r_date_of_issue:
            d, m, y = _d_m_y(workerreg.r_date_of_issue)
            values['reg_date_day'] = d
            values['reg_date_month'] = m
            values['reg_date_year'] = y
        else:
            exceptions.append('reg_date_of_issue')

    values['cont_name'] = 'ПОДСОБНЫЙ РАБОЧИЙ ОКПДТР 167711'

    if contract.cont_type == 'Трудовой':
        values['td'] = 'X'
        values['gpd'] = ''
    elif contract.cont_type == 'ГПХ':
        values['td'] = ''
        values['gpd'] = 'X'

    workerpatent = worker.actual_patent
    if workerpatent:
        values['patent'] = 'ПАТЕНТ'
        values['patent_series'] = workerpatent.series
        values['patent_num'] = workerpatent.number
        try:
            d, m, y = _d_m_y(workerreg.r_date_of_issue)
            values['patent_date_of_issue_day'] = d
            values['patent_date_of_issue_month'] = m
            values['patent_date_of_issue_year'] = y
            values['patent_issued_by'] = workerpatent.issued_by
            values['patent_start_date_day'] = d
            values['patent_start_date_month'] = m
            values['patent_start_date_year'] = y
        except:
            exceptions.append('patent_begin_date')
        try:
            d, m, y = _d_m_y(workerpatent.date_end)
            values['patent_end_date_day'] = d
            values['patent_end_date_month'] = m
            values['patent_end_date_year'] = y
        except:
            exceptions.append('patent_end_date')

    try:
        d, m, y = _d_m_y(doc_date)
        values['cont_day'] = d
        values['cont_month'] = m
        values['cont_year'] = y

        values['doc_day'] = d
        _, M, _ = _d_M_y(doc_date)
        values['doc_month'] = M
        values['doc_year'] = y[2:]

    except:
        exceptions.append('contract_begin_date')

    if not exceptions:
        return values
    else:
        raise WorkerException(worker.pk, exceptions)


# Todo: remove this
def notice_of_contract_upload_location(instance, filename):
    return f'workers/{instance.contract.c_worker}/notices_of_contract_{filename}'


class NoticeOfContract(models.Model):
    date = models.DateTimeField(
        'Дата создания',
        blank=True,
        null=True,
        default=timezone.now)
    replication_date = models.DateTimeField(
        'Дата прикрепления справки',
        blank=True,
        null=True)
    # Todo: remove (use Photo)
    image = models.ImageField(
        'Фото справки',
        null=True,
        blank=True,
        upload_to=notice_of_contract_upload_location)

    contract = models.OneToOneField(
        Contract,
        on_delete=models.PROTECT,
        verbose_name='Договор'
    )

    photos = GenericRelation(Photo)

    def __str__(self):
        return 'Уведомление о заключении №{num} от {date} для {worker}'.format(
            num=self.pk,
            date=self.date,
            worker=self.contract.c_worker
        )

    def make_dict(self, proxy):
        return _make_notification_dict(
            self.contract,
            proxy,
            self.contract.begin_date
        )


# Todo: remove this
def notice_of_termination_upload_location(instance, filename):
    return f'workers/{instance.contract.c_worker}/noticeoftermination_{filename}'


class NoticeOfTermination(models.Model):

    date = models.DateTimeField(
        'Дата расторжения',
        default=timezone.now
    )
    replication_date = models.DateTimeField(
        'Дата прикрепления справки',
        blank=True,
        null=True
    )
    # Todo: remove (use Photo)
    image = models.ImageField(
        'Фото справки',
        null=True,
        blank=True,
        upload_to=notice_of_termination_upload_location
    )
    contract = models.OneToOneField(
        Contract,
        on_delete=models.PROTECT,
        verbose_name='Договор'
    )

    photos = GenericRelation(Photo)

    def get_date(self):
        return as_default_timezone(self.date).date()

    def __str__(self):
        return 'Уведомление о расторжении №{0} от {1} для {2}'.format(
            self.pk,
            self.date,
            self.contract.c_worker
        )

    def make_dict(self, proxy):
        return _make_notification_dict(
            self.contract,
            proxy,
            self.get_date()
        )


class NoticeOfArrival(models.Model):
    date = models.DateField(
        verbose_name='Дата создания',
        auto_now_add=True
    )
    contract = models.ForeignKey(
        Contract,
        on_delete=models.PROTECT,
    )

    def __str__(self):
        return '{0} - {1}'.format(self.pk, self.date)

    def make_dict(self):
        worker = Worker.objects.get(contract__id=self.contract.pk)
        exceptions = list()

        values = dict()
        try:
            values['worker_lastname'] = self.contract.c_worker.last_name.upper()
        except AttributeError:
            exceptions.append('lastname')
        try:
            values['worker_name_and_surname'] = self.contract.c_worker.name.upper()
        except AttributeError:
            exceptions.append('name')
        if self.contract.c_worker.patronymic:
            values['worker_name_and_surname'] += ' ' + self.contract.c_worker.patronymic.upper()

        if self.contract.c_worker.citizenship:
            values['citizenship'] = self.contract.c_worker.citizenship.name.upper()
        else:
            values['citizenship'] = ' '
        try:
            birth_date = self.contract.c_worker.birth_date
            birth_date = birth_date.strftime('%Y-%m-%d')
            values['birth_date_day'] = birth_date[8:]
            values['birth_date_month'] = birth_date[5:7]
            values['birth_date_year'] = birth_date[:4]
        except:
            exceptions.append('birth_date')

        if self.contract.c_worker.sex == 'Муж':
            values['sex_m'] = 'X'
            values['sex_w'] = ''
        elif self.contract.c_worker.sex == 'Жен':
            values['sex_m'] = ''
            values['sex_w'] = 'X'

        if self.contract.c_worker.place_of_birth:
            values['place_of_birth_country'] = self.contract.c_worker.place_of_birth.name.upper()
        else:
            values['place_of_birth_county'] = ' '

        try:
            workerpasss = WorkerPassport.objects.get(workers_id=worker,
                                                     is_actual=True)
            values['passport'] = 'ПАСПОРТ'
            values['pass_series'] = ''
            values['pass_num'] = workerpasss.another_passport_number

            pass_date_of_issue = workerpasss.date_of_issue
            pass_date_of_issue = pass_date_of_issue.strftime('%Y-%m-%d')
            values['pass_date_of_issue_day'] = pass_date_of_issue[8:]
            values['pass_date_of_issue_month'] = pass_date_of_issue[5:7]
            values['pass_date_of_issue_year'] = pass_date_of_issue[:4]

            if workerpasss.date_of_exp:
                pass_date_of_exp = workerpasss.date_of_exp
                pass_date_of_exp = pass_date_of_exp.strftime('%Y-%m-%d')
                values['pass_date_of_exp_day'] = pass_date_of_exp[8:]
                values['pass_date_of_exp_month'] = pass_date_of_exp[5:7]
                values['pass_date_of_exp_year'] = pass_date_of_exp[:4]

        except WorkerPassport.DoesNotExist:
            exceptions.append('workerpass')
        except:
            exceptions.append('pass_date_of_issue')

        # values['profession'] = 'ПОДСОБНЫЙ РАБОЧИЙ'

        try:
            mig_date = self.contract.c_worker.m_date_of_issue
            mig_date = mig_date.strftime('%Y-%m-%d')
            values['m_day'] = mig_date[8:]
            values['m_month'] = mig_date[5:7]
            values['m_year'] = mig_date[:4]
        except:
            exceptions.append('mig_date')

        values['mig_series'] = self.contract.c_worker.mig_series
        values['mig_number'] = self.contract.c_worker.mig_number

        if not exceptions:
            values['worker_lastname2'] = values['worker_lastname']
            values['worker_name_and_surname2'] = values['worker_name_and_surname']
            values['citizenship2'] = values['citizenship']
            values['birth_date_day2'] = values['birth_date_day']
            values['birth_date_month2'] = values['birth_date_month']
            values['birth_date_year2'] = values['birth_date_year']
            values['sex_m2'] = values['sex_m']
            values['sex_w2'] = values['sex_w']
            values['passport2'] = values['passport']
            values['pass_series2'] = values['pass_series']
            values['pass_num2'] = values['pass_num']

        if not exceptions:
            return values
        else:
            raise WorkerException(worker.pk, exceptions)
