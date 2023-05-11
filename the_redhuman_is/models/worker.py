import re
from datetime import timedelta
from decimal import Decimal

from django.apps import apps
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.contrib.postgres.aggregates import ArrayAgg
from django.contrib.postgres.fields import ArrayField

from django.core.exceptions import ObjectDoesNotExist

from django.db import models

from django.db.models import (
    BooleanField,
    Case,
    CharField,
    Count,
    DateField,
    Exists,
    F,
    IntegerField,
    JSONField,
    OuterRef,
    Q,
    Subquery,
    Value,
    When,
)
from django.db.models.functions import (
    Coalesce,
    ExtractYear,
    Greatest,
    JSONObject,
    NullIf,
    Upper,
)
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from finance.models import Account

from the_redhuman_is.models.comment import Comment
from the_redhuman_is.models.photo import (
    Photo,
    get_photos,
    save_single_photo,
)
from utils import (
    get_tomorrow_date,
    normalized_phone,
)
from utils.expressions import PostgresConcatWS
from utils.functools import LazyInstance

DEFAULT_RECENT_TIMESPAN = timedelta(days=30)


class Metro(models.Model):
    name = models.CharField('Станция', max_length=200)

    def __str__(self):
        return self.name


class Country(models.Model):
    name = models.CharField('Страна', max_length=200)

    RUSSIA = LazyInstance(name='РФ')

    def __str__(self):
        return self.name


def country_by_name(name):
    replacements = {
        'Армения': 'Республика Армения',
        'Россия': 'РФ'
    }

    if name in replacements:
        name = replacements[name]

    return Country.objects.get(name=name)


class Position(models.Model):
    name = models.CharField('Должность', max_length=200)

    def __str__(self):
        return self.name


# Todo: get rid of this
def worker_upload_location(instance, filename):
    return f'workers/{instance}/{filename}'


class WorkerQuerySet(models.QuerySet):

    def with_has_contract(self):
        from the_redhuman_is.models.contract import Contract
        return self.annotate(
            has_contract=Exists(
                Contract.objects.filter(
                    c_worker=OuterRef('pk')
                )
            )
        )

    def with_has_med_card(self):
        return self.annotate(
            has_med_card=Exists(
                WorkerMedicalCard.objects.filter(
                    worker=OuterRef('pk')
                )
            )
        )

    def with_has_patent(self):
        return self.annotate(
            has_patent=Exists(
                WorkerPatent.objects.filter(
                    workers_id=OuterRef('pk')
                )
            )
        )

    def with_has_registration(self):
        return self.annotate(
            has_registration=Exists(
                WorkerRegistration.objects.filter(
                    workers_id=OuterRef('pk')
                )
            )
        )

    def with_has_passport(self):
        return self.annotate(
            has_passport=Exists(
                WorkerPassport.objects.filter(
                    is_actual=True,
                    workers_id=OuterRef('pk')
                )
            )
        )

    def with_passport(self):
        return self.annotate(
            passport=Subquery(
                WorkerPassport.objects.filter(
                    is_actual=True,
                    workers_id=OuterRef('pk')
                ).annotate(
                    fields=JSONObject(
                        series='passport_series',
                        number='another_passport_number',
                        date_of_issue='date_of_issue'
                    )
                ).values(
                    'fields'
                ),
                output_field=JSONField()
            )
        )

    def with_contract(self):
        from the_redhuman_is.models.contract import Contract
        return self.annotate(
            has_contract=Exists(
                Contract.objects.filter(
                    c_worker=OuterRef('pk')
                )
            )
        ).filter(
            has_contract=True
        )

    @staticmethod
    def _get_comment_subquery():
        return Comment.objects.filter(
            object_id=OuterRef('pk'),
            content_type=ContentType.objects.get_for_model(Worker),
        ).annotate(
            comment_fields=JSONObject(
                text='text',
                author=JSONObject(
                    id='author_id',
                    name='author__first_name',
                ),
                timestamp='timestamp',
            )
        )

    def with_last_comment(self):
        return self.annotate(
            last_comment=Subquery(
                self._get_comment_subquery(
                ).order_by(
                    '-timestamp'
                ).values(
                    'comment_fields'
                )[:1],
                output_field=JSONField()
            ),
        )

    def with_comments(self):
        return self.annotate(
            comments=Coalesce(
                Subquery(
                    self._get_comment_subquery(
                    ).values(
                        'object_id'
                    ).annotate(
                        comments_list=ArrayAgg(
                            'comment_fields',
                            ordering=(
                                '-timestamp',
                            )
                        )
                    ).values(
                        'comments_list'
                    )
                ),
                [],
                output_field=ArrayField(JSONField())
                )
            )

    def with_has_photo(self):
        return self.annotate(
            has_photo=Exists(
                Photo.objects.filter(
                    content_type=ContentType.objects.get_for_model(Worker),
                    object_id=OuterRef('pk'),
                )
            )
        )

    def with_full_name(self, upper=False):
        name_expression = PostgresConcatWS(
            Value(' '),
            F('last_name'),
            F('name'),
            NullIf(F('patronymic'), Value(''))
        )
        if upper:
            name_expression = Upper(name_expression)
        return self.annotate(
            full_name=name_expression
        )

    def with_last_turnout_date(self):
        from the_redhuman_is.models.delivery import RequestWorkerTurnout
        return self.annotate(
            last_turnout_date=Subquery(
                RequestWorkerTurnout.objects.filter(
                    requestworker__worker=OuterRef('pk'),
                ).order_by(
                    '-requestworker__request__date'
                ).values(
                    'requestworker__request__date'
                )[:1],
                output_field=DateField()
            )
        )

    def with_assigned_requests(self, first_day=None):
        from the_redhuman_is.models.delivery import RequestWorker, ItemWorker
        assigned_requests_sq = RequestWorker.objects.annotate(
            has_active_items=Exists(
                ItemWorker.objects.filter(
                    requestworker=OuterRef('pk'),
                    itemworkerrejection__isnull=True,
                )
            ),
        ).filter(
            has_active_items=True,
            worker=OuterRef('pk'),
            workerrejection__isnull=True,
        )
        if first_day is not None:
            assigned_requests_sq = assigned_requests_sq.filter(
                request__date__gte=first_day
            )
            field_name = 'has_recent_requests'
        else:
            field_name = 'has_assigned_requests'
        return self.annotate(
            **{field_name: Exists(assigned_requests_sq)}
        )

    def _with_turnout_status_code_exists(self, dt=DEFAULT_RECENT_TIMESPAN):
        return self.with_assigned_requests(
        ).with_assigned_requests(
            first_day=timezone.localdate() - dt
        ).annotate(
            status_code=Case(
                When(
                    banned__isnull=False,
                    then=Value(Worker.BANNED)
                ),
                When(
                    has_recent_requests=True,
                    then=Value(Worker.ONLINE_RECENT)
                ),
                When(
                    has_assigned_requests=True,
                    then=Value(Worker.ONLINE_PAST)
                ),
                default=Value(Worker.NO_TURNOUTS),
                output_field=IntegerField()
            )
        )

    def _with_turnout_status_code_last_date(self, dt=DEFAULT_RECENT_TIMESPAN):
        return self.annotate(
            status_code=Case(
                When(
                    banned__isnull=False,
                    then=Value(Worker.BANNED)
                ),
                When(
                    last_turnout_date__gt=timezone.localdate() - dt,
                    then=Value(Worker.ONLINE_RECENT)
                ),
                When(
                    last_turnout_date__isnull=False,
                    then=Value(Worker.ONLINE_PAST)
                ),
                default=Value(Worker.NO_TURNOUTS),
                output_field=IntegerField()
            )
        )

    def with_turnout_status_code(self):
        if 'last_turnout_date' not in self.query.annotations:
            return self._with_turnout_status_code_exists()
        else:
            return self._with_turnout_status_code_last_date()

    def with_contract_status(self):
        from the_redhuman_is.models.contract import Contract

        now = timezone.localtime()

        contracts = Contract.objects.filter(c_worker__pk=OuterRef('pk'))
        actual_contract = contracts.filter(
            Q(begin_date__isnull=True) | Q(end_date__gt=now),
            is_actual=True,
        )
        actual_contract_with_photos = actual_contract.annotate(
            has_scans=Exists(
                Photo.objects.filter(
                    content_type=ContentType.objects.get_for_model(Contract),
                    object_id=OuterRef('pk')
                )
            )
        ).exclude(
            Q(has_scans=False) &
            Q( # Todo: get rid of this fields (and this block)
                Q(image__isnull=True) | Q(image=''),
                Q(image2__isnull=True) | Q(image2=''),
                Q(image3__isnull=True) | Q(image3='')
            )
        )
        selfemployment_data = WorkerSelfEmploymentData.objects.filter(
            worker=OuterRef('pk'),
            deletion_ts__isnull=True,
        )
        contract_exists = Exists(contracts)
        actual_contract_exists = Exists(actual_contract)
        actual_contract_with_photos_exists = Exists(actual_contract_with_photos)
        selfemployment_data_exists = Exists(selfemployment_data)

        return self.annotate(
            contract_status=Case(
                When(selfemployment_data_exists, then=Value('самозанятый')),
                When(actual_contract_with_photos_exists, then=Value('актуальный')),
                When(actual_contract_exists, then=Value('без скана')),
                When(contract_exists, then=Value('просрочен')),
                default=Value('нет'),
                output_field=CharField()
            ),
        )

    def with_is_selfemployed(self):
        return self.annotate(
            is_selfemployed=Exists(
                WorkerSelfEmploymentData.objects.filter(
                    worker=OuterRef('pk'),
                    deletion_ts__isnull=True
                )
            )
        )

    # Todo: remove this
    def with_selfemployment_tax_number(self):
        return self.annotate(
            tax_number=Subquery(
                WorkerSelfEmploymentData.objects.filter(
                    worker=OuterRef('pk'),
                    deletion_ts__isnull=True,
                ).values(
                    'tax_number'
                ),
                output_field=CharField()
            )
        )

    def with_selfemployment_data(self, more=False):
        fields = [
            'tax_number',
            'bank_account',
            'bank_identification_code',
        ]
        if more:
            fields.extend([
                'cardholder_name',
                'bank_name',
                'correspondent_account',
            ])
        return self.annotate(
            wse=Subquery(
                WorkerSelfEmploymentData.objects.filter(
                    worker=OuterRef('pk'),
                    deletion_ts__isnull=True
                ).annotate(
                    data=JSONObject(**{
                        field: field
                        for field in fields
                    })
                ).values(
                    'data'
                ),
                output_field=JSONField()
            )
        )

    def with_cardholder_name(self, upper=False):
        selfemployment_subquery = WorkerSelfEmploymentData.objects.filter(
            worker=OuterRef('pk'),
            deletion_ts__isnull=True
        )
        if upper:
            selfemployment_subquery = selfemployment_subquery.annotate(
                uppercase_cardholder=Upper('cardholder_name')
            )
            field_name = 'uppercase_cardholder'
        else:
            field_name = 'cardholder_name'

        return self.annotate(
            cardholder_name=Subquery(
                selfemployment_subquery.values(
                    field_name
                ),
                output_field=CharField()
            )
        )

    def with_paysheet_amount_to_pay(self, paysheet):
        return self.annotate(
            paysheet_amount_to_pay=Subquery(
                apps.get_model('the_redhuman_is', 'Paysheet_v2Entry').objects.filter(
                    worker__pk=OuterRef('pk'),
                    paysheet=paysheet
                ).values('amount')
            )
        )

    def with_paysheet_entry(self, paysheet_id: int):
        return self.annotate(
            paysheet_entry=Subquery(
                apps.get_model('the_redhuman_is', 'Paysheet_v2Entry').objects.filter(
                    worker__pk=OuterRef('pk'),
                    paysheet_id=paysheet_id
                ).annotate(
                    fields=JSONObject(
                        amount='amount',
                        pk='pk'
                    )
                ).values(
                    'fields'
                ),
                output_field=JSONField()
            )
        )

    def with_has_registry_receipt(self, paysheet):
        return self.annotate(
            has_registry_receipt=Exists(
                apps.get_model('the_redhuman_is', 'WorkerReceipt').objects.filter(
                    workerreceiptregistrynum__registry_num__paysheetregistry__paysheet=paysheet,
                    worker=OuterRef('pk')
                )
            )
        )

    def with_paysheet_receipt_url(self, paysheet_id):
        return self.annotate(
            paysheet_receipt_url=Subquery(
                apps.get_model('the_redhuman_is', 'WorkerReceipt').objects.filter(
                    workerreceiptpaysheetentry__paysheet_entry__paysheet_id=paysheet_id,
                    worker=OuterRef('pk')
                ).values(
                    'url'
                )
            )
        )

    def with_unconfirmed_count(self):
        from the_redhuman_is.models.delivery import ItemWorker, RequestWorker
        return self.annotate(
            unconfirmed_count=Coalesce(
                Subquery(
                    RequestWorker.objects.annotate(
                        has_active_items=Exists(
                            ItemWorker.objects.filter(
                                requestworker=OuterRef('pk'),
                                itemworkerrejection__isnull=True,
                            )
                        ),
                    ).filter(
                        has_active_items=True,
                        requestworkerturnout__isnull=True,
                        worker=OuterRef('pk'),
                    ).values(
                        'worker'
                    ).annotate(
                        count=Count('pk')
                    ).values('count'),
                ),
                0,
                output_field=IntegerField()
            ),
        )

    # require with_is_selfemployed() and with_cardholder_name() call to work
    def with_worker_type(self):
        return self.annotate(
            worker_type=Case(
                When(
                    # no valid selfemployment data
                    is_selfemployed=False,
                    then=Value('not_selfemployed'),
                ),
                When(
                    # citizenship not Russia
                    ~Q(citizenship=Country.RUSSIA.pk),
                    then=Value('foreign'),
                ),
                When(
                    # own card
                    cardholder_name=F('full_name'),
                    then=Value('selfemployed_own_account'),
                ),
                # not own card
                default=Value('selfemployed_another_account'),
                output_field=CharField()
            ),
        )

    def with_is_online_tomorrow(self):
        from the_redhuman_is.models.delivery import OnlineStatusMark

        return self.annotate(
            is_online_tomorrow=Subquery(
                OnlineStatusMark.objects.filter(
                    user__workeruser__worker=OuterRef('pk'),
                    timestamp__date__gte=timezone.localdate()
                ).order_by(
                    '-timestamp'
                ).values(
                    'online'
                )[:1],
                output_field=models.BooleanField()
            )
        )

    def with_paysheet_workdays(self, paysheet_id):
        from the_redhuman_is.services.paysheet import annotate_with_paysheet_workdays
        return annotate_with_paysheet_workdays(
            self,
            paysheet_id,
            OuterRef('pk')
        )

    def with_in_weekend_rest_zone(self):
        from the_redhuman_is.models.delivery import WeekendRest
        return self.annotate(
            in_weekend_rest_zone=Exists(
                WeekendRest.objects.filter(
                    zone__workerzone__worker=OuterRef('pk')
                )
            )
        )

    def with_last_active_day(self):
        return self.annotate(
            last_active_day=Greatest(
                'last_turnout_date',
                'input_date',
                output_field=DateField()
            )
        )

    def with_planned_contact_day(self):
        return self.annotate(
            planned_contact_day=Subquery(
                PlannedContact.objects.filter(
                    worker=OuterRef('pk'),
                ).order_by(
                    '-timestamp'
                ).values(
                    'date'
                )[:1],
                output_field=DateField()
            )
        )

    def with_age(self):
        year, month, day = timezone.localdate().timetuple()[:3]
        return self.annotate(
            age=(
                Value(year) -
                ExtractYear('birth_date') -
                Case(
                    When(
                        Q(birth_date__month__gt=month) |
                        Q(
                            birth_date__month=month,
                            birth_date__day__gt=day
                        ),
                        then=1,
                    ),
                    default=0,
                )
            )
        )

    def with_registration_ok(self, deadline=None):
        if deadline is None:
            deadline = timezone.localdate()
        return self.annotate(
            registration_ok=Case(
                When(
                    Q(m_date_of_exp__gt=deadline) |
                    Q(citizenship=Country.RUSSIA.pk),
                    then=Value(True),
                ),
                default=Value(False),
                output_field=BooleanField()
            )
        )

    def with_selfie_if_loader(self):
        return self.annotate(
            selfie=Case(
                When(
                    position__name='Грузчик',
                    then=Subquery(
                        Photo.objects.filter(
                            content_type=ContentType.objects.get_for_model(Worker),
                            object_id=OuterRef('pk'),
                            image__contains='selfie',
                        ).order_by(
                            '-timestamp'
                        ).values(
                            'image'
                        )[:1]
                    )
                ),
                default=Value(None),
                output_field=CharField()
            ),
        )

    def with_talk_bank_client_id(self):
        return self.annotate(
            talk_bank_client_id=F('talkbankclient__client_id')
        )

    def with_talk_bank_payment_attempt(self, paysheet_id):
        return self.annotate(
            talk_bank_payment_attempt=Subquery(
                apps.get_model('the_redhuman_is', 'PaysheetEntryTalkBankPaymentAttempt').objects.filter(
                    paysheet_id=paysheet_id,
                    worker=OuterRef('pk'),
                ).annotate(
                    data=JSONObject(
                        payment_result='status',
                        payment_result_description='description',
                        service_desciption='service_description',
                    )
                ).values(
                    'data'
                ),
                output_field=JSONField()
            )
        )

    def with_talk_bank_payment(self, paysheet_id):
        return self.annotate(
            talk_bank_payment=Subquery(
                apps.get_model('the_redhuman_is', 'PaysheetEntryTalkBankPayment').objects.filter(
                    paysheet_entry__paysheet_id=paysheet_id,
                    paysheet_entry__worker=OuterRef('pk')
                ).annotate(
                    data=JSONObject(
                        tax_number='tax_number',
                        amount='amount',
                        bank_account='bank_account',
                        bank_name='bank_name',
                        bank_identification_code='bank_identification_code',
                        completed='completed',
                        status='status',
                        order_slug='order_slug',
                        talk_bank_commission='talk_bank_commission',
                        beneficiary_partner_commission='beneficiary_partner_commission',
                    )
                ).values(
                    'data'
                ),
                output_field=JSONField()
            )
        )

    def with_talk_bank_bind_status(self):
        return self.annotate(
            talk_bank_bind_status=Subquery(
                apps.get_model('the_redhuman_is', 'TalkBankBindStatus').objects.filter(
                    worker=OuterRef('pk')
                ).annotate(
                    data=JSONObject(
                        timestamp='timestamp',
                        is_bound='is_bound',
                        operation_result='operation_result',
                        operation_result_description='operation_result_description',
                    )
                ).order_by(
                    '-pk'
                ).values(
                    'data'
                )[:1],
                output_fields=JSONField()
            )
        )

    def filter_by_text(self, value):
        qs = self
        if 'full_name' not in qs.query.annotations:
            qs = qs.with_full_name()
        return qs.annotate(
            passport_number_contains_value=Exists(
                WorkerPassport.objects.filter(
                    workers_id=OuterRef('pk'),
                    # is_actual=True,
                    another_passport_number__icontains=value
                )
            )
        ).filter(
            Q(passport_number_contains_value=True) |
            Q(tel_number__icontains=value) |
            Q(full_name__icontains=value)
        )

    def filter_by_name_or_phone(self, value):
        qs = self
        if 'full_name' not in qs.query.annotations:
            qs = qs.with_full_name()
        return qs.filter(
            Q(tel_number__icontains=value) |
            Q(full_name__icontains=value)
        )

    def filter_rf_or_mk(self, deadline=None):
        qs = self
        if 'registration_ok' not in qs.query.annotations:
            qs = qs.with_registration_ok(deadline)
        return qs.filter(
            registration_ok=True,
        )

    def filter_by_turnout_customer(self, customer_id):
        from the_redhuman_is.models.models import WorkerTurnout
        return self.annotate(
            has_turnout=Exists(
                WorkerTurnout.objects.filter(
                    worker=OuterRef('pk'),
                    timesheet__customer=customer_id,
                )
            )
        ).filter(
            has_turnout=True
        )

    def filter_mobile(self):
        return self.filter(
            mobileappworker__isnull=False,
        )

    def filter_with_contract(self):
        from the_redhuman_is.models.contract import Contract
        contracts = Contract.objects.filter(
            is_actual=True,
        ).annotate(
            has_scans=Exists(
                Photo.objects.filter(
                    content_type=ContentType.objects.get_for_model(Contract),
                    object_id=OuterRef('pk')
                )
            )
        ).exclude(
            Q(has_scans=False) &
            Q(  # Todo: get rid of this fields (and this block)
                Q(image__isnull=True) | Q(image=''),
                Q(image2__isnull=True) | Q(image2=''),
                Q(image3__isnull=True) | Q(image3='')
            )
        ).filter(
            c_worker=OuterRef('pk')
        )
        return self.filter_rf_or_mk(
        ).annotate(
            has_contract=Exists(contracts)
        ).filter(
            has_contract=True
        )

    def filter_without_contract(self):
        return self.filter(contract__isnull=True)

    def filter_to_deal_with(self):
        return self.filter_without_contract(
        ).with_has_photo(
        ).filter(
            m_date_of_exp__gt=get_tomorrow_date()
        ).exclude(
            Q(workerregistration__r_date_of_issue__isnull=True) |
            Q(has_photo=False)
        )

    def filter_by_payment_attempt(self, paysheet_id):
        return self.filter(
            paysheetentrytalkbankpaymentattempt__paysheet_id=paysheet_id
        )


class Worker(models.Model):
    NO_TURNOUTS = 0
    ONLINE_RECENT = 1
    ONLINE_PAST = 2
    BANNED = -1
    TURNOUT_STATUS_CHOICES = [
        (ONLINE_RECENT, 'Актив'),
        (ONLINE_PAST, 'Выходил давно'),
        (NO_TURNOUTS, 'Не выходил'),
        (BANNED, 'Забанен'),
    ]

    input_date = models.DateTimeField(
        'Дата внесения',
        auto_now_add=True
    )
    last_name = models.CharField(
        'Фамилия',
        max_length=100
    )
    name = models.CharField(
        'Имя',
        max_length=100
    )
    patronymic = models.CharField(
        'Отчество',
        max_length=100,
        blank=True,
    )
    sex = models.CharField(
        verbose_name='Пол',
        max_length=100,
        choices=(
            ('Муж', 'Муж'),
            ('Жен', 'Жен'),
        ),
        default='Муж',
    )
    birth_date = models.DateField(
        'Дата рождения',
        blank=True,
        null=True
    )
    mig_series = models.CharField(
        'МК, серия',
        max_length=7,
        blank=True,
        null=True
    )
    mig_number = models.CharField(
        'МК, номер',
        max_length=8,
        blank=True,
        null=True
    )
    m_date_of_issue = models.DateField(
        'МК, дата выдачи',
        blank=True,
        null=True
    )
    m_date_of_exp = models.DateField(
        'МК, дата окончания',
        blank=True,
        null=True
    )
    tel_number = models.CharField(
        'Телефон',
        max_length=12,
        blank=True,
        null=True
    )
    metro = models.ForeignKey(
        Metro,
        on_delete=models.PROTECT,
        verbose_name='Метро',
        blank=True,
        null=True
    )

    # Todo: remove
    metro1 = models.CharField(
        verbose_name='Метро',
        default='Н/д',
        max_length=100,
        blank=True,
        null=True,
    )

    # Todo: remove
    status = models.CharField(
        verbose_name='Статус',
        max_length=100,
        choices=(
            ('Новый', 'Новый'),
            ('Неверный номер', 'Неверный номер'),
            ('Не хочет', 'Не хочет'),
            ('Хочет, но позже', 'Хочет, но позже'),
            ('Хочет', 'Хочет'),
            ('Черный список', 'Черный список'),
        ),
        default='Новый',
        blank=True,
        null=True,
    )
    # Todo: remove
    speaks_russian = models.CharField(
        verbose_name='Знание русского',
        max_length=100,
        choices=(
            ('Н/д', 'Н/д'),
            ('Плохо', 'Плохо'),
            ('Средне', 'Средне'),
            ('Хорошо', 'Хорошо'),
        ),
        default='Н/д',
        blank=True,
        null=True,
    )
    position = models.ForeignKey(
        Position,
        on_delete=models.PROTECT,
        verbose_name='Должность',
    )

    # Todo: remove
    position1 = models.CharField(
        verbose_name='Должность',
        max_length=15,
        blank=True, null=True,
        choices=(
            ('Грузчик', 'Грузчик'),
            ('Стажер', 'Стажер'),
            ('Бригадир', 'Бригадир'),
        ),
        default='Грузчик',
    )
    citizenship = models.ForeignKey(
        Country,
        on_delete=models.PROTECT,
        verbose_name='Гражданство',
        related_name='citizens'
    )
    # Todo: remove
    citizenship1 = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        choices=(
            ('РФ', 'РФ'),
            ('Киргизия', 'Киргизия'),
            ('Казахстан', 'Казахстан'),
            ('Узбекистан', 'Узбекистан'),
            ('Украина', 'Украина'),
            ('Белоруссия', 'Белоруссия'),
            ('Таджикистан', 'Таджикистан'),
            ('Республика Армения', 'Республика Армения'),
            ('Республика Молдова', 'Республика Молдова'),
        ),
        default='Киргизия',
        verbose_name='Гражданство'
    )
    # Todo: not nullable
    place_of_birth = models.ForeignKey(
        Country,
        on_delete=models.PROTECT,
        verbose_name='Место рождения',
        related_name='workers_born',
        blank=True,
        null=True,
    )
    # Todo: remove
    place_of_birth1 = models.CharField(
        max_length=100,
        choices=(
            ('Российская Федерация',
             'Российская Федерация'),
            ('Киргизия', 'Киргизия'),
            ('Казахстан', 'Казахстан'),
            ('Таджикистан', 'Таджикистан'),
            ('Узбекистан', 'Узбекистан'),
            ('Украина', 'Украина'),
            ('Белоруссия', 'Белоруссия'),
            ('Республика Армения',
             'Республика Армения'),
            ('Республика Молдова',
             'Республика Молдова'),
        ),
        default='Киргизия',
        verbose_name='Место рождения',
        blank=True,
        null=True,
    )
    contract_type = models.CharField(
        verbose_name='Договор',
        max_length=100,
        choices=(
            ('Трудовой', 'Трудовой'),
            ('ГПХ', 'ГПХ'),
        ),
        default='ГПХ',
        blank=True,
        null=True,
    )

    objects = WorkerQuerySet.as_manager()

    class Meta:
        ordering = ('last_name', 'name', 'patronymic')

    def save(self, *args, **kwargs):
        if self.tel_number:
            self.tel_number = normalized_phone(self.tel_number)

            # Todo: it is not race safe
            same_phone_workers = Worker.objects.filter(
                tel_number=self.tel_number
            ).exclude(
                pk=self.pk
            )
            if same_phone_workers.exists():
                raise Exception(
                    'Есть работник с номером {}: {}'.format(
                        self.tel_number,
                        ', '.join([str(w) for w in same_phone_workers])
                    )
                )
        super().save(*args, **kwargs)

    def __str__(self):
        if self.patronymic:
            return '%s %s %s' % (self.last_name, self.name, self.patronymic)
        else:
            return '%s %s' % (self.last_name, self.name)

    def save_worker(self):
        self.input_date = timezone.now()
        self.save()

    def get_turnouts(self, from_date=None):
        if from_date is not None:
            turnouts = apps.get_model('the_redhuman_is', 'WorkerTurnout').objects.filter(
                worker_id=self,
                worker_turnouts__timesheet__sheet_date__gte=from_date
            ).order_by('timesheet__sheet_date')
            return turnouts
        else:
            turnouts = apps.get_model('the_redhuman_is', 'WorkerTurnout').objects.filter(worker_id=self).order_by(
                'timesheet__sheet_date')
            return turnouts

    def day_timesheets(self):
        return apps.get_model('the_redhuman_is', 'WorkerTurnout').objects.filter(
            worker_id=self,
            timesheet__sheet_turn='День'
        ).count()

    def night_timesheets(self):
        return apps.get_model('the_redhuman_is', 'WorkerTurnout').objects.filter(
            worker_id=self,
            timesheet__sheet_turn='Ночь'
        ).count()

    def rate_of_dayshifts(self):
        day = apps.get_model('the_redhuman_is', 'WorkerTurnout').objects.filter(
            worker_id=self,
            timesheet__sheet_turn='День'
        ).count()
        average = apps.get_model('the_redhuman_is', 'WorkerTurnout').objects.filter(worker_id=self).count()
        if average > 0:
            return round(day / average * 100, 1)

    def days_after_last_turnout(self):
        last_turnout = apps.get_model('the_redhuman_is', 'TimeSheet').objects.filter(
            worker_turnouts__worker_id=self).latest('sheet_date')
        delta = timezone.localdate() - last_turnout.sheet_date
        return delta.days

    def get_last_turnout(self):
        turnout = apps.get_model('the_redhuman_is', 'TimeSheet').objects.filter(
            worker_turnouts__worker_id=self).latest('sheet_date')
        return '{} - {}'.format(turnout.cust_location, turnout.customer)

    def get_last_comment(self):
        comment = WorkerComments.objects.filter(worker=self).latest('date')
        return '{}'.format(comment.text, )

    # Todo: looks like broken
    def get_actual_contract(self):
        now = timezone.now()
        return self.contract.filter(
            Q(begin_date__isnull=True) | Q(end_date__gt=now),
            is_actual=True
        ).first()

    @property
    def actual_passport(self):
        try:
            return WorkerPassport.objects.get(
                workers_id=self,
                is_actual=True
            )
        except WorkerPassport.DoesNotExist:
            return None

    @property
    def actual_registration(self):
        try:
            return WorkerRegistration.objects.get(
                workers_id=self,
                is_actual=True
            )
        except WorkerRegistration.DoesNotExist:
            return None

    @property
    def actual_patent(self):
        try:
            return WorkerPatent.objects.get(
                workers_id=self,
                is_actual=True
            )
        except WorkerPatent.DoesNotExist:
            return None

    @property
    def place_of_birth_name(self):
        if self.place_of_birth:
            return self.place_of_birth.name
        else:
            return ''

    @property
    def citizenship_name(self):
        if self.citizenship:
            return self.citizenship.name
        else:
            return ''

    @property
    def position_name(self):
        if self.position:
            return self.position.name
        else:
            return ''

    def update_snils(self, number, date_of_issue, image):
        if hasattr(self, 'snils'):
            snils = self.snils
            snils.number = number
            snils.date_of_issue = date_of_issue
            snils.save()
        else:
            snils = WorkerSNILS.objects.create(
                worker=self,
                number=number,
                date_of_issue=date_of_issue
            )
        if image:
            save_single_photo(snils, image)


@receiver(post_save, sender=Worker)
def update_account_name(sender, instance, created, raw, using, update_fields, **kwargs):
    if update_fields is None or {'last_name', 'name', 'patronymic'} & set(update_fields):
        try:
            account = Account.objects.get(
                worker_account__worker=instance
            )
        except Account.DoesNotExist:
            pass
        else:
            account.name = str(instance)
            account.save(update_fields=['name', 'full_name'])


def get_worker_photos(worker):
    photos = get_photos(worker)

    try:
        migration_card = WorkerMigrationCard.objects.get(worker=worker)
        photos = photos.union(get_photos(migration_card))
    except ObjectDoesNotExist:
        pass

    passports = WorkerPassport.objects.filter(workers_id=worker)
    for passport in passports:
        photos = photos.union(get_photos(passport))

    return photos.order_by('pk')


class WorkerIsBannedException(Exception):
    pass


class BannedWorker(models.Model):
    worker = models.OneToOneField(
        Worker,
        verbose_name='Работник',
        related_name='banned',
        on_delete=models.PROTECT,
    )

    def __str__(self):
        return str(self.worker)


class MobileAppWorker(models.Model):
    worker = models.OneToOneField(
        Worker,
        on_delete=models.CASCADE
    )
    timestamp = models.DateTimeField(
        auto_now_add=True
    )

    def __str__(self):
        return str(self.worker)


class WorkerUser(models.Model):
    worker = models.OneToOneField(
        Worker,
        on_delete=models.PROTECT
    )
    user = models.OneToOneField(
        User,
        on_delete=models.PROTECT
    )

    def __str__(self):
        return '{} - {}'.format(
            self.user.username,
            self.worker
        )


class WorkerComments(models.Model):
    worker = models.OneToOneField(Worker, on_delete=models.CASCADE)
    date = models.DateTimeField(
        'Дата создания',
        auto_now_add=True
    )
    author = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        verbose_name='Автор'
    )
    text = models.TextField(
        verbose_name='Комментарий',
        blank=True,
        null=True,
    )

    class Meta:
        ordering = ('-date',)

    def __str__(self):
        worker = Worker.objects.get(workercomments__id=self.pk)
        return '{0} {1} {2}'.format(self.author, worker, self.date)


class WorkerTag(models.Model):
    timestamp = models.DateTimeField(
        verbose_name='Время создания',
        default=timezone.now
    )
    author = models.ForeignKey(
        User,
        verbose_name='Автор',
        on_delete=models.PROTECT
    )

    tag = models.CharField(
        max_length=40
    )
    worker = models.OneToOneField(
        Worker,
        on_delete=models.CASCADE,
    )


class WorkerPassport(models.Model):
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['workers_id'],
                condition=Q(is_actual=True),
                name='unique_actual_passport',
            )
        ]
    workers_id = models.ForeignKey(
        Worker,
        on_delete=models.CASCADE
    )
    passport_type = models.CharField(
        verbose_name='Тип паспорта',
        max_length=15,
        choices=(
            ('Внутренний', 'Внутренний'),
            ('Заграничный', 'Заграничный'),
            ('PФ', 'РФ'),
        ),
        default='Новый',
        blank=True,
        null=True,
    )
    passport_series = models.CharField(
        'Серия паспорта',
        max_length=5,
        blank=True,
        null=True
    )
    another_passport_number = models.CharField(
        'Номер паспорта',
        max_length=11,
        blank=True,
        null=True
    )
    date_of_issue = models.DateField('Дата выдачи', blank=True, null=True)
    date_of_exp = models.DateField('Дата окончания', blank=True, null=True)
    issued_by = models.CharField(
        'Кем выдан',
        max_length=200,
        blank=True,
        null=True
    )
    is_actual = models.BooleanField(default=True)

    def __str__(self):
        return '{0}'.format(self.workers_id)

    def save(self, *args, **kwargs):
        if not self.pk and self.is_actual:
            WorkerPassport.objects.filter(
                workers_id=self.workers_id
            ).update(is_actual=False)
        super().save(*args, **kwargs)


class WorkerRegistration(models.Model):
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['workers_id'],
                condition=Q(is_actual=True),
                name='unique_actual_registration',
            )
        ]
    workers_id = models.ForeignKey(Worker, on_delete=models.CASCADE)
    r_date_of_issue = models.DateField(
        'Дата постановки на учет',
    )
    city = models.CharField(
        'Город',
        max_length=100,
    )
    street = models.CharField(
        'Улица',
        max_length=100,
    )
    house_number = models.CharField(
        'Дом',
        max_length=100,
        blank=True,
        null=True
    )
    building_number = models.CharField(
        'Строение',
        max_length=100,
        blank=True,
        null=True
    )
    appt_number = models.CharField(
        'Квартира',
        max_length=100,
        blank=True,
        null=True
    )
    is_actual = models.BooleanField(default=True)

    def __str__(self):
        return '{0}'.format(self.workers_id)

    def save(self, *args, **kwargs):
        if not self.pk and self.is_actual:
            WorkerRegistration.objects.filter(
                workers_id=self.workers_id
            ).update(is_actual=False)
        super().save(*args, **kwargs)


class WorkerPatent(models.Model):
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['workers_id'],
                condition=Q(is_actual=True),
                name='unique_actual_patent',
            )
        ]

    workers_id = models.ForeignKey(
        Worker,
        on_delete=models.CASCADE,
    )

    series = models.CharField('Серия', max_length=20,
                              blank=True, null=True)
    number = models.CharField('Номер', max_length=20,
                              blank=True, null=True)

    date_of_issue = models.DateField('Дата выдачи', blank=True, null=True)
    date_end = models.DateField('Дата окончания срока действия', blank=True,
                                null=True)
    issued_by = models.CharField('Кем выдан', max_length=100, blank=True,
                                 null=True)

    profession = models.CharField('Профессия', max_length=100,
                                  blank=True, null=True)

    profession_id = models.IntegerField('Код профессии', blank=True, null=True)

    is_actual = models.BooleanField(default=True)

    def __str__(self):
        return '{0}'.format(self.workers_id)

    def save(self, *args, **kwargs):
        if not self.pk and self.is_actual:
            WorkerPatent.objects.filter(
                workers_id=self.workers_id
            ).update(is_actual=False)
        super().save(*args, **kwargs)


# Todo: remove
def medcard_upload_location(card, filename):
    return 'workers/{}/card_{}'.format(card.worker, filename)


class WorkerMedicalCard(models.Model):
    worker = models.ForeignKey(
        Worker,
        on_delete=models.CASCADE,
    )
    number = models.CharField('Номер медкнижки', max_length=30, blank=True,
                              null=True)
    card_date_of_issue = models.DateField('Дата выдачи', blank=True, null=True)
    card_date_of_exp = models.DateField('Дата окончания', blank=True, null=True)

    image = models.ImageField(
        null=True, blank=True, upload_to=medcard_upload_location)
    image2 = models.ImageField(
        null=True, blank=True, upload_to=medcard_upload_location)
    image3 = models.ImageField(
        null=True, blank=True, upload_to=medcard_upload_location)

    def __str__(self):
        return str(self.worker)


_SNILS_RX = re.compile(r'^\d{3}-\d{3}-\d{3} \d{2}$')


def check_SNILS(snils):
    m = _SNILS_RX.match(snils)
    if not m:
        raise Exception('Номер СНИЛС должен быть в формате 112-233-445 95')
    digits = [c for c in snils[:-2] if c.isdigit()]

    same = 1
    for i in range(1, len(digits)):
        if digits[i - 1] == digits[i]:
            same += 1
        else:
            same = 1
        if same >= 3:
            raise Exception(
                'В номере СНИЛС не может идти 3 одинаковых цифры подряд'
            )

    # Проверка контрольного числа только для номеров больше 001-001-998
    if int(''.join(digits)) <= 1001998:
        return

    checksum = 0
    for i in range(len(digits)):
        checksum += int(digits[i]) * (9 - i)
    if checksum > 101:
        checksum %= 101
    elif checksum in [100, 101]:
        checksum = 0

    if checksum != int(snils[-2:]):
        raise Exception('У номера СНИЛС неверная контрольная сумма')


class WorkerSNILS(models.Model):
    worker = models.OneToOneField(
        Worker,
        verbose_name='Работник',
        related_name='snils',
        on_delete=models.CASCADE)
    number = models.CharField('СНИЛС', max_length=14)
    date_of_issue = models.DateField('Дата выдачи')

    def photo(self):
        photos = get_photos(self)
        if photos.exists():
            return photos.get()
        else:
            return None

    def save(self, *args, **kwargs):
        check_SNILS(self.number)
        super(WorkerSNILS, self).save(*args, **kwargs)


# Todo: move actual data from Worker model
class WorkerMigrationCard(models.Model):
    worker = models.OneToOneField(
        Worker,
        verbose_name='Работник',
        related_name='migration_card',
        on_delete=models.CASCADE
    )

    def __str__(self):
        return str(self.worker)


class WorkerSelfEmploymentData(models.Model):
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['worker'],
                condition=Q(deletion_ts__isnull=True),
                name='unique_actual_data',
            )
        ]

    worker = models.ForeignKey(
        Worker,
        verbose_name='Работник',
        related_name='selfemployment_data',
        on_delete=models.CASCADE
    )

    deletion_ts = models.DateTimeField(
        null=True,
        blank=True,
    )

    tax_number = models.CharField(
        verbose_name='ИНН',
        max_length=20,
    )

    bank_account = models.CharField(
        verbose_name='Расчетный счет',
        max_length=25,
    )
    bank_name = models.CharField(
        verbose_name='Наименование банка',
        max_length=200,
    )
    bank_identification_code = models.CharField(
        verbose_name='БИК',
        max_length=9,
    )
    correspondent_account = models.CharField(
        verbose_name='Корреспондентский счет',
        max_length=20,
    )
    cardholder_name = models.CharField(
        verbose_name='ФИО держателя карты',
        max_length=255,
    )

    @property
    def is_actual(self):
        return self.deletion_ts is None

    def __init__(self, *args, **kwargs):
        super(WorkerSelfEmploymentData, self).__init__(*args, **kwargs)
        self._loaded_values = {}

    def __str__(self):
        return str(self.worker)

    @classmethod
    def from_db(cls, db, field_names, values):
        new = super(WorkerSelfEmploymentData, cls).from_db(db, field_names, values)
        new._loaded_values = dict(zip(field_names, values))
        return new

    def save(self, **kwargs):
        changed = {f for f, v in self._loaded_values.items() if getattr(self, f) != v}
        if 'update_fields' in kwargs:
            changed = {f for f in kwargs['update_fields'] if f in changed}
        if 'worker' in changed:
            raise ValueError("Updating worker isn't allowed.")  # disallow moving data from worker to worker
        toggle_deletion = 'deletion_ts' in changed
        changed.discard('deletion_ts')
        if changed:  # data fields are changed
            if self._loaded_values['deletion_ts'] is None:  # if record was not soft-deleted
                self.deletion_ts = timezone.now()  # soft delete
                super(WorkerSelfEmploymentData, self).save(update_fields=['deletion_ts'])
                self.id = None  # insert
                self.deletion_ts = timezone.now() if toggle_deletion else None  # restore incoming deletion status
            elif toggle_deletion:  # if record is being undeleted and edited
                WorkerSelfEmploymentData.objects.filter(
                    worker=self.worker, deletion_ts__isnull=True
                ).update(deletion_ts=timezone.now())  # soft delete a valid record if exists
                self.id = None  # insert
        elif self.deletion_ts is None:  # if record is being undeleted or created
            WorkerSelfEmploymentData.objects.filter(
                worker=self.worker, deletion_ts__isnull=True
            ).update(deletion_ts=timezone.now())  # soft delete a valid record if exists
        super(WorkerSelfEmploymentData, self).save(**kwargs)
        for f in self._loaded_values:
            self._loaded_values[f] = getattr(self, f)


class WorkerLabelType(models.Model):
    name = models.TextField(unique=True)
    comment_required = models.BooleanField(default=False)

    def __str__(self):
        return f'{self.name}'


class WorkerLabel(models.Model):
    worker = models.OneToOneField(Worker, on_delete=models.CASCADE)
    label = models.ForeignKey(WorkerLabelType, on_delete=models.PROTECT)

    def __str__(self):
        return f'{self.worker} {self.label}'


class PlannedContact(models.Model):
    timestamp = models.DateTimeField(
        verbose_name='Время создания',
        default=timezone.now
    )
    author = models.ForeignKey(
        User,
        verbose_name='Автор',
        on_delete=models.PROTECT
    )

    worker = models.ForeignKey(
        Worker,
        on_delete=models.PROTECT,
        db_index=False,
    )
    date = models.DateField()

    class Meta:
        indexes = [
            models.Index(
                fields=['worker', '-timestamp'],
                name='plannedcontact_worker_ts_idx',
            ),
        ]

    def __str__(self):
        return f'{self.worker} {self.date}'


class WorkerRating(models.Model):
    AVAILABLE = 2
    NOT_AVAILABLE = -1
    NO_ANSWER = 1
    UNKNOWN = 0

    TOMORROW = 2
    ANOTHER_DAY = 1
    NOT_READY = -1

    worker = models.OneToOneField(
        Worker,
        on_delete=models.PROTECT,
    )
    last_call = models.DateTimeField(
        null=True,
    )
    is_benevolent = models.BooleanField(
        default=True,
    )
    reliability = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default=Decimal('5.00'),
    )
    availability = models.SmallIntegerField(
        choices=[
            (AVAILABLE, 'На связи'),
            (NOT_AVAILABLE, 'Нет связи'),
            (NO_ANSWER, 'Не отвечает'),
            (UNKNOWN, 'Не звонили'),
        ],
        default=UNKNOWN,
    )
    readiness = models.SmallIntegerField(
        choices=[
            (TOMORROW, 'Готов завтра'),
            (ANOTHER_DAY, 'Готов в другой день'),
            (NOT_READY, 'Не готов'),
            (UNKNOWN, 'Неизвестно'),
        ],
        default=UNKNOWN,
    )
