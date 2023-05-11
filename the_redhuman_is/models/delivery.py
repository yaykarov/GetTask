# -*- coding: utf-8 -*-

import datetime
import os
from functools import cached_property

from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.contrib.postgres.aggregates import ArrayAgg
from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import PermissionDenied

from django.core.validators import MinValueValidator

from django.db import models
from django.db.models import (
    BooleanField,
    Case,
    CharField,
    Count,
    DecimalField,
    Exists,
    ExpressionWrapper,
    F,
    FloatField,
    IntegerField,
    JSONField,
    Min,
    OuterRef,
    Q,
    Subquery,
    Sum,
    TextField,
    TimeField,
    Value,
    When,
)
from django.db.models.functions import (
    Cast,
    Ceil,
    Coalesce,
    Concat,
    Greatest,
    JSONObject,
    NullIf,
)

from django.utils import timezone

from utils.expressions import (
    Haversine,
    MakeAware,
    PostgresConcatWS,
)
from utils.numbers import ZERO_OO
from .models import (
    Customer,
    CustomerLocation,
    CustomerService,
    WorkerTurnout,
)

from .photo import Photo
from .worker import Worker

from utils.date_time import (
    as_default_timezone,
    string_from_date,
)


class ConfirmedDailyReconciliationExists(PermissionDenied):
    pass


def _delivery_requests_upload_location(instance, filename):
    return 'delivery/requests/{}/{}'.format(
        instance.id,
        filename
    )


def _delivery_requests_processed_upload_location(instance, filename):
    return 'delivery/requests/{}/processed/{}'.format(
        instance.id,
        filename
    )


class RequestsFile(models.Model):
    STATUS_TYPES = (
        ('processing', 'Формируется'),
        ('finished_with_errors', 'Завершено с ошибками'),
        ('finished', 'Завершено'),
        ('error', 'Не удалось сформировать')
    )

    timestamp = models.DateTimeField(
        verbose_name='Время импорта',
        default=timezone.now
    )
    author = models.ForeignKey(
        User,
        verbose_name='Автор',
        on_delete=models.PROTECT
    )
    customer = models.ForeignKey(
        Customer,
        verbose_name='Клиент',
        on_delete=models.PROTECT
    )

    status = models.CharField(
        verbose_name='Статус',
        max_length=50,
        choices=STATUS_TYPES,
        default='processing'
    )
    status_description = models.TextField(
        verbose_name='Статус (описание)',
        default='Формируется'
    )

    data_file = models.FileField(
        upload_to=_delivery_requests_upload_location
    )

    processed_data_file = models.FileField(
        upload_to=_delivery_requests_processed_upload_location,
        null=True
    )

    def short_filename(self):
        return os.path.basename(str(self.data_file))

    def __str__(self):
        return '{}, {}: {}'.format(
            string_from_date(self.timestamp),
            self.author.username,
            self.short_filename()
        )


class DeliveryService(models.Model):
    # Todo: transform this list to some data in db
    ZONES = (
        ('msk',     'Москва'),
        ('msk_15',  'МО до 15'),
        ('msk_30',  'МО до 30'),
        ('msk_45',  'МО до 45'),
        ('msk_60',  'МО до 60'),
        ('msk_60+', 'МО от 60'),
        ('spb',     'Санкт-Петербург'),
        ('spb_15',  'Санкт-Петербург до 15'),
        ('spb_30',  'Санкт-Петербург до 30'),
        ('spb_45',  'Санкт-Петербург до 45'),
        ('spb_60',  'Санкт-Петербург до 60'),
        ('spb_60+', 'Санкт-Петербург от 60'),
        ('orel',     'Орёл'),
        ('orel_15',  'Орёл до 15'),
        ('orel_30',  'Орёл до 30'),
        ('orel_45',  'Орёл до 45'),
        ('orel_60',  'Орёл до 60'),
        ('orel_60+', 'Орёл от 60'),
        ('sochi',     'Сочи'),
        ('sochi_15',  'Сочи до 15'),
        ('sochi_30',  'Сочи до 30'),
        ('sochi_45',  'Сочи до 45'),
        ('sochi_60',  'Сочи до 60'),
        ('sochi_60+', 'Сочи от 60'),
        ('adler',     'Адлер'),
        ('adler_15',  'Адлер до 15'),
        ('adler_30',  'Адлер до 30'),
        ('adler_45',  'Адлер до 45'),
        ('adler_60',  'Адлер до 60'),
        ('adler_60+', 'Адлер от 60'),
        ('ulyanovsk',     'Ульяновск'),
        ('ulyanovsk_15',  'Ульяновск до 15'),
        ('ulyanovsk_30',  'Ульяновск до 30'),
        ('ulyanovsk_45',  'Ульяновск до 45'),
        ('ulyanovsk_60',  'Ульяновск до 60'),
        ('ulyanovsk_60+', 'Ульяновск от 60'),
        ('samara',     'Самара'),
        ('samara_15',  'Самара до 15'),
        ('samara_30',  'Самара до 30'),
        ('samara_45',  'Самара до 45'),
        ('samara_60',  'Самара до 60'),
        ('samara_60+', 'Самара от 60'),
        ('vyborg',     'Выборг'),
        ('vyborg_15',  'Выборг до 15'),
        ('vyborg_30',  'Выборг до 30'),
        ('vyborg_45',  'Выборг до 45'),
        ('vyborg_60',  'Выборг до 60'),
        ('vyborg_60+', 'Выборг от 60'),
        ('lipetsk',     'Липецк'),
        ('lipetsk_15',  'Липецк до 15'),
        ('lipetsk_30',  'Липецк до 30'),
        ('lipetsk_45',  'Липецк до 45'),
        ('lipetsk_60',  'Липецк до 60'),
        ('lipetsk_60+', 'Липецк от 60'),
        ('kaliningrad',     'Калининград'),
        ('kaliningrad_15',  'Калининград до 15'),
        ('kaliningrad_30',  'Калининград до 30'),
        ('kaliningrad_45',  'Калининград до 45'),
        ('kaliningrad_60',  'Калининград до 60'),
        ('kaliningrad_60+', 'Калининград от 60'),
        ('nn',     'Нижний Новгород'),
        ('nn_15',  'Нижний Новгород до 15'),
        ('nn_30',  'Нижний Новгород до 30'),
        ('nn_45',  'Нижний Новгород до 45'),
        ('nn_60',  'Нижний Новгород до 60'),
        ('nn_60+', 'Нижний Новгород от 60'),
        ('tyumen',     'Тюмень'),
        ('tyumen_15',  'Тюмень до 15'),
        ('tyumen_30',  'Тюмень до 30'),
        ('tyumen_45',  'Тюмень до 45'),
        ('tyumen_60',  'Тюмень до 60'),
        ('tyumen_60+', 'Тюмень от 60'),
        ('perm',     'Пермь'),
        ('perm_15',  'Пермь до 15'),
        ('perm_30',  'Пермь до 30'),
        ('perm_45',  'Пермь до 45'),
        ('perm_60',  'Пермь до 60'),
        ('perm_60+', 'Пермь от 60'),
        ('bataisk',     'Батайск'),
        ('bataisk_15',  'Батайск до 15'),
        ('bataisk_30',  'Батайск до 30'),
        ('bataisk_45',  'Батайск до 45'),
        ('bataisk_60',  'Батайск до 60'),
        ('bataisk_60+', 'Батайск от 60'),
        ('rostov_on_don',     'Ростов-на-Дону'),
        ('rostov_on_don_15',  'Ростов-на-Дону до 15'),
        ('rostov_on_don_30',  'Ростов-на-Дону до 30'),
        ('rostov_on_don_45',  'Ростов-на-Дону до 45'),
        ('rostov_on_don_60',  'Ростов-на-Дону до 60'),
        ('rostov_on_don_60+', 'Ростов-на-Дону от 60'),
        ('ryazan',     'Рязань'),
        ('ryazan_15',  'Рязань до 15'),
        ('ryazan_30',  'Рязань до 30'),
        ('ryazan_45',  'Рязань до 45'),
        ('ryazan_60',  'Рязань до 60'),
        ('ryazan_60+', 'Рязань от 60'),
        ('voronezh',     'Воронеж'),
        ('voronezh_15',  'Воронеж до 15'),
        ('voronezh_30',  'Воронеж до 30'),
        ('voronezh_45',  'Воронеж до 45'),
        ('voronezh_60',  'Воронеж до 60'),
        ('voronezh_60+', 'Воронеж от 60'),
        ('belgorod',     'Белгород'),
        ('belgorod_15',  'Белгород до 15'),
        ('belgorod_30',  'Белгород до 30'),
        ('belgorod_45',  'Белгород до 45'),
        ('belgorod_60',  'Белгород до 60'),
        ('belgorod_60+', 'Белгород от 60'),
        ('petrozavodsk',     'Петрозаводск'),
        ('petrozavodsk_15',  'Петрозаводск до 15'),
        ('petrozavodsk_30',  'Петрозаводск до 30'),
        ('petrozavodsk_45',  'Петрозаводск до 45'),
        ('petrozavodsk_60',  'Петрозаводск до 60'),
        ('petrozavodsk_60+', 'Петрозаводск от 60'),
        ('kursk',     'Курск'),
        ('kursk_15',  'Курск до 15'),
        ('kursk_30',  'Курск до 30'),
        ('kursk_45',  'Курск до 45'),
        ('kursk_60',  'Курск до 60'),
        ('kursk_60+', 'Курск от 60'),
        ('dmitrov',     'Дмитров'),
        ('dmitrov_15',  'Дмитров до 15'),
        ('dmitrov_30',  'Дмитров до 30'),
        ('dmitrov_45',  'Дмитров до 45'),
        ('dmitrov_60',  'Дмитров до 60'),
        ('dmitrov_60+', 'Дмитров от 60'),
        ('novosibirsk',     'Новосибирск'),
        ('novosibirsk_15',  'Новосибирск до 15'),
        ('novosibirsk_30',  'Новосибирск до 30'),
        ('novosibirsk_45',  'Новосибирск до 45'),
        ('novosibirsk_60',  'Новосибирск до 60'),
        ('novosibirsk_60+', 'Новосибирск от 60'),
        ('krasnodar',     'Краснодар'),
        ('krasnodar_15',  'Краснодар до 15'),
        ('krasnodar_30',  'Краснодар до 30'),
        ('krasnodar_45',  'Краснодар до 45'),
        ('krasnodar_60',  'Краснодар до 60'),
        ('krasnodar_60+', 'Краснодар от 60'),
        ('serpukhov',     'Серпухов'),
        ('serpukhov_15',  'Серпухов до 15'),
        ('serpukhov_30',  'Серпухов до 30'),
        ('serpukhov_45',  'Серпухов до 45'),
        ('serpukhov_60',  'Серпухов до 60'),
        ('serpukhov_60+', 'Серпухов от 60'),
        ('omsk',     'Омск'),
        ('omsk_15',  'Омск до 15'),
        ('omsk_30',  'Омск до 30'),
        ('omsk_45',  'Омск до 45'),
        ('omsk_60',  'Омск до 60'),
        ('omsk_60+', 'Омск от 60'),
        ('ufa',     'Уфа'),
        ('ufa_15',  'Уфа до 15'),
        ('ufa_30',  'Уфа до 30'),
        ('ufa_45',  'Уфа до 45'),
        ('ufa_60',  'Уфа до 60'),
        ('ufa_60+', 'Уфа от 60'),
        ('arkhangelsk',     'Архангельск'),
        ('arkhangelsk_15',  'Архангельск до 15'),
        ('arkhangelsk_30',  'Архангельск до 30'),
        ('arkhangelsk_45',  'Архангельск до 45'),
        ('arkhangelsk_60',  'Архангельск до 60'),
        ('arkhangelsk_60+', 'Архангельск от 60'),
        ('severodvinsk',     'Северодвинск'),
        ('severodvinsk_15',  'Северодвинск до 15'),
        ('severodvinsk_30',  'Северодвинск до 30'),
        ('severodvinsk_45',  'Северодвинск до 45'),
        ('severodvinsk_60',  'Северодвинск до 60'),
        ('severodvinsk_60+', 'Северодвинск от 60'),
    )

    TRAVEL_HOURS = {
        '':    0,
        '15':  1,
        '30':  2,
        '45':  3,
        '60':  4,
        '60+': 4,
    }

    # Todo: get rid of this
    is_for_united_request = models.BooleanField(
        verbose_name='Тариф только для "объединенных" заявок',
        default=False
    )
    # Todo: get rid of this
    min_mass = models.FloatField(
        verbose_name='Минимальная масса для тарифа',
        default=0
    )
    zone = models.CharField(
        verbose_name='Зона',
        max_length=32,
        choices=ZONES,
        default='msk'
    )
    service = models.ForeignKey(
        CustomerService,
        verbose_name='Услуга',
        on_delete=models.PROTECT,
    )
    customer_service_name = models.CharField(
        verbose_name='Название для клиента',
        max_length=50,
    )
    operator_service_name = models.CharField(
        verbose_name='Название для оператора',
        max_length=50,
    )

    # Часов за дорогу
    travel_hours = models.IntegerField(
        verbose_name='Часов за дорогу',
    )

    # Часов за работу (т.е. сколько указано в табеле)
    # + часов за дорогу
    hours = models.IntegerField(
        verbose_name='Часов всего'
    )

    def __str__(self):
        return '{}: {}/{}/{}ч'.format(
            self.service.customer.cust_name,
            self.customer_service_name,
            self.service.service.name,
            self.hours
        )


class DeliveryRequestQuerySet(models.QuerySet):

    def with_confirmed_timepoint(self):
        return self.annotate(
            confirmed_timepoint=Subquery(
                DeliveryItem.objects.filter(
                    request=OuterRef('pk'),
                    workers_required__gt=0,
                ).values(
                    'request'
                ).annotate(
                    Min('confirmed_timepoint')
                ).values(
                    'confirmed_timepoint__min'
                ),
                output_field=TimeField()
            )
        )

    def with_new_worker_timepoint(self):
        return self.annotate(
            new_worker_timepoint=Subquery(
                DeliveryItem.objects.with_itemworker_count(
                ).filter(
                    request=OuterRef('pk'),
                    itemworker_count__lt=F('workers_required'),
                    confirmed_timepoint__isnull=False,
                ).values(
                    'request'
                ).annotate(
                    Min('confirmed_timepoint')
                ).values(
                    'confirmed_timepoint__min'
                ),
                output_field=TimeField()
            )
        )

    def with_worker_timepoint(self, worker_id):
        return self.annotate(
            worker_timepoint=Subquery(
                ItemWorker.objects.filter(
                    item__request=OuterRef('pk'),
                    requestworker__worker=worker_id,
                ).values(
                    'item__request'
                ).annotate(
                    Min('item__confirmed_timepoint')
                ).values(
                    'item__confirmed_timepoint__min'
                ),
                output_field=TimeField()
            )
        )

    def with_score(self):
        # how to subquery:
        # https://hansonkd.medium.com/the-dramatic-benefits-of-django-subqueries-and-annotations-4195e0dafb16
        requestworker_query = (
            RequestWorker.objects.annotate(
                has_items=Exists(
                    ItemWorker.objects.filter(
                        requestworker=OuterRef('pk'),
                        itemworkerrejection__isnull=True,
                    )
                ),
            ).filter(
                request=OuterRef('id'),
                workerrejection__isnull=True,
                has_items=True,
            ).values(
                'request'
            ).annotate(
                cnt=Count('id')
            ).values(
                'cnt'
            )
        )
        return self.annotate(
            score=Greatest(
                (
                    Subquery(
                        requestworker_query,
                        output_field=models.IntegerField()
                    ) + Value(1)
                ) / Value(2),
                Value(1)
            )
        )

    def with_score_v2(self):
        turnout_qs = RequestWorkerTurnout.objects.filter(
            requestworker__request=OuterRef('pk'),
            workerturnout__hours_worked__isnull=False,
        ).annotate(
            _score=Ceil(
                F('workerturnout__hours_worked') / Value(6, output_field=IntegerField()),
                output_field=IntegerField()
            )
        ).values(
            'requestworker__request'
        ).annotate(
            Sum('_score')
        ).values(
            '_score__sum'
        )

        return self.annotate(
            score=Coalesce(
                Subquery(
                    turnout_qs,
                    output_field=IntegerField()
                ),
                1
            ),
        )

    def with_items_count(self):
        return self.annotate(
            items_count=Coalesce(
                Subquery(
                    DeliveryItem.objects.filter(
                        request=OuterRef('pk'),
                        workers_required__gt=0,
                    ).values(
                        'request'
                    ).annotate(
                        item_count=Count('pk')
                    ).values(
                        'item_count'
                    ),
                    output_field=IntegerField()
                ),
                0
            )
        )

    @staticmethod
    def get_requests_to_merge_subquery():
        return DeliveryRequest.objects.all(
        ).with_arrival_time(
        ).with_confirmation_time(
        ).annotate(
            driver_name_blank=Coalesce('driver_name', Value('', output_field=TextField())),
            driver_phones_blank=Coalesce('driver_phones', Value('', output_field=TextField())),
            blank=Value('', output_field=TextField()),
        ).filter(
            date=OuterRef('date'),
            customer=OuterRef('customer'),
        ).exclude(
            pk=OuterRef('pk'),
        ).exclude(
            driver_name_blank='',
            driver_phones_blank='',
        ).filter(
            Q(driver_name_blank=OuterRef('driver_name_blank')) |
            Q(driver_name_blank='') |
            Q(blank=OuterRef('driver_name_blank'))
        ).filter(
            Q(driver_phones_blank=OuterRef('driver_phones_blank')) |
            Q(driver_phones_blank='') |
            Q(blank=OuterRef('driver_phones_blank'))
        ).filter(
            Q(driver_name_blank=OuterRef('driver_name_blank')) |
            Q(driver_phones_blank=OuterRef('driver_phones_blank'))
        ).exclude(
            arrival_time__isnull=False,
            arrival_time__gt=(
                OuterRef('arrival_time') + Value(datetime.timedelta(minutes=2*60))
            ),
        ).exclude(
            arrival_time__isnull=False,
            arrival_time__lt=(
                OuterRef('arrival_time') - Value(datetime.timedelta(minutes=2*60))
            ),
        ).exclude(
            status__in=DeliveryRequest.FAIL_STATUSES
        ).exclude(
            status=DeliveryRequest.COMPLETE,
            timestamp__gt=(
                OuterRef('confirmation_time') + Value(datetime.timedelta(minutes=5))
            )
        ).exclude(
            status=DeliveryRequest.COMPLETE,
            confirmation_time__isnull=False,
            confirmation_time__lt=(
                OuterRef('timestamp') - Value(datetime.timedelta(minutes=5))
            )
        )

    def with_merge_data(self):
        queryset = self.annotate(
            driver_name_blank=Coalesce('driver_name', Value('', output_field=TextField())),
            driver_phones_blank=Coalesce('driver_phones', Value('', output_field=TextField())),
        )
        if 'arrival_time' not in queryset.query.annotations:
            queryset = queryset.with_arrival_time()
        if 'confirmation_time' not in queryset.query.annotations:
            queryset = queryset.with_confirmation_time()

        return queryset.annotate(
            merge_candidates=Subquery(
                self.get_requests_to_merge_subquery(
                ).values(
                    'customer'
                ).annotate(
                    pks=ArrayAgg(
                        'pk',
                        ordering=('pk',)
                    )
                ).values('pks'),
                output_field=ArrayField(base_field=IntegerField())
            ),
        ).annotate(
            requests_to_merge_with=Case(
                When(
                    status__in=DeliveryRequest.FAIL_STATUSES,
                    then=[]
                ),
                When(
                    driver_name_blank='',
                    driver_phones_blank='',
                    then=[],
                ),
                default=F('merge_candidates'),
                output_field=ArrayField(base_field=IntegerField())
            )
        )

    def with_arrival_time(self):
        # todo change to last arrival at first item after first item is implemented
        # this is "first arrival at any item" but should be "last arrival at first item"
        return self.annotate(
            arrival_time=Subquery(
                ItemWorkerStart.objects.filter(
                    itemworker__requestworker__request=OuterRef('pk'),
                    itemworker__itemworkerrejection__isnull=True,
                    itemworker__requestworker__workerrejection__isnull=True,
                ).order_by(
                    'timestamp'
                ).values(
                    'timestamp'
                )[:1]
            )
        )

    def with_confirmation_time(self):
        return self.annotate(
            confirmation_time=Subquery(
                ItemWorkerFinish.objects.filter(
                    itemworker__requestworker__request=OuterRef('pk'),
                    itemworker__requestworker__workerrejection__isnull=True,
                    itemworker__itemworkerrejection__isnull=True,
                ).order_by(
                    '-timestamp'
                ).values(
                    'timestamp'
                )[:1]
            )
        )

    def with_worked_hours(self):
        """
        Real worked hours after request is finished.
        """
        return self.annotate(
            worked_hours=Coalesce(
                Subquery(
                    WorkerTurnout.objects.filter(
                        requestworkerturnout__requestworker__request=OuterRef('pk'),
                        hours_worked__isnull=False,
                    ).order_by(
                    ).values(
                        'requestworkerturnout__requestworker__request'
                    ).annotate(
                        Sum('hours_worked')
                    ).values(
                        'hours_worked__sum'
                    ),
                    output_field=DecimalField(),
                ),
                ZERO_OO
            )
        )

    def with_hours(self):
        from the_redhuman_is.models.turnout_calculators import (
            NIGHT_SURCHARGE,
            DAYTIME,
        )
        queryset = self
        if 'confirmed_timepoint' not in queryset.query.annotations:
            queryset = queryset.with_confirmed_timepoint()

        return queryset.with_worker_count(
            turnout=False
        ).with_worked_hours(
        ).annotate(
            night_surcharge=Case(
                When(
                    Q(confirmed_timepoint__lt=DAYTIME.start) |
                    Q(confirmed_timepoint__gte=DAYTIME.stop),
                    then=Value(NIGHT_SURCHARGE)
                ),
                default=Value(ZERO_OO),
                output_field=models.DecimalField()
            )
        ).annotate(
            hours=Coalesce(
                ExpressionWrapper(
                    F('worked_hours') +
                    F('worker_no_turnout_count') * (
                        F('delivery_service__hours') +
                        F('night_surcharge')
                    ),
                    output_field=models.DecimalField()
                ),
                ZERO_OO,
                output_field=models.DecimalField()
            ),
        )

    def with_worker_amount(self):
        return self.annotate(
            worker_amount=Coalesce(
                Subquery(
                    RequestWorkerTurnout.objects.filter(
                        requestworker__request=OuterRef('pk'),
                    ).values(
                        'requestworker__request'
                    ).annotate(
                        amount_sum=Sum(
                            'workerturnout__turnoutoperationtopay__operation__amount'
                        )
                    ).values(
                        'amount_sum'
                    ),
                    output_field=DecimalField(),
                ),
                ZERO_OO
            ),
        )

    def with_customer_amount(self):
        """
        Real operation amount (sum) after request is finished.
        """
        return self.annotate(
            customer_amount=Coalesce(
                Subquery(
                    RequestWorkerTurnout.objects.filter(
                        requestworker__request=OuterRef('pk'),
                    ).values(
                        'requestworker__request'
                    ).annotate(
                        amount_sum=Sum(
                            'workerturnout__turnoutcustomeroperation__operation__amount'
                        )
                    ).values(
                        'amount_sum'
                    ),
                    output_field=DecimalField(),
                ),
                ZERO_OO
            ),
        )

    def with_customer_resolution(self):
        return self.annotate(
            has_suspicious_start=Exists(
                ItemWorkerStart.objects.filter(
                    itemworker__requestworker__request=OuterRef('pk'),
                    itemworker__requestworker__workerrejection__isnull=True,
                    itemworker__itemworkerrejection__isnull=True,
                    is_suspicious=True,
                ).exclude(
                    itemworkerdiscrepancycheck__is_ok=True
                )
            )
        ).annotate(
            customer_resolution=Case(
                When(
                    deliveryrequestconfirmation__isnull=False,
                    then=Value(DeliveryRequest.CUSTOMER_CONFIRMED)
                ),
                When(
                    has_suspicious_start=True,
                    then=Value(DeliveryRequest.SUSPICIOUS)
                ),
                default=Value(DeliveryRequest.NORMAL),
                output_field=models.CharField()
            )
        )

    def with_is_paid_by_customer(self):
        from .reconciliation import Reconciliation

        return self.annotate(
            is_paid_by_customer=Exists(
                Reconciliation.objects.filter(
                    Q(location__isnull=True) |
                    Q(location=OuterRef('location')),
                    customer=OuterRef('customer'),
                    first_day__lte=OuterRef('date'),
                    last_day__gte=OuterRef('date'),
                    payment_operation__isnull=False,
                )
            )
        )

    def with_in_payment_by_customer(self):
        from .reconciliation import Reconciliation

        return self.annotate(
            in_payment_by_customer=Exists(
                Reconciliation.objects.filter(
                    Q(location__isnull=True) |
                    Q(location=OuterRef('location')),
                    customer=OuterRef('customer'),
                    first_day__lte=OuterRef('date'),
                    last_day__gte=OuterRef('date'),
                    payment_operation__isnull=True,
                )
            )
        )

    def with_new_start_photo_count(self):
        return self.annotate(
            new_start_photo_count=Coalesce(
                Subquery(
                    ItemWorkerStart.objects.filter(
                        itemworker__itemworkerrejection__isnull=True,
                        itemworker__requestworker__request=OuterRef('pk'),
                        itemworker__requestworker__workerrejection__isnull=True,
                        itemworkerstartconfirmation__isnull=True,
                    ).annotate(
                        photo_count=Subquery(
                            Photo.objects.filter(
                                content_type=ContentType.objects.get_for_model(
                                    ItemWorkerStart
                                ),
                                photorejectioncomment__isnull=True,
                                object_id=OuterRef('pk')
                            ).values(
                                'object_id'
                            ).annotate(
                                Count('pk')
                            ).values(
                                'pk__count'
                            ),
                            output_field=IntegerField(),
                        )
                    ).order_by(
                    ).values(
                        'itemworker__requestworker__request'
                    ).annotate(
                        Sum('photo_count')
                    ).values(
                        'photo_count__sum'
                    ),
                    output_field=IntegerField(),
                ),
                0
            )
        )

    def with_start_photos(self):
        return self.annotate(
            start_photos=Coalesce(
                Subquery(
                    ItemWorkerStart.objects.filter(
                        itemworker__itemworkerrejection__isnull=True,
                        itemworker__requestworker__request=OuterRef('pk'),
                        itemworker__requestworker__workerrejection__isnull=True,
                        itemworkerstartconfirmation__isnull=False,
                    ).annotate(
                        photo=Subquery(
                            Photo.objects.filter(
                                content_type=ContentType.objects.get_for_model(
                                    ItemWorkerStart
                                ),
                                photorejectioncomment__isnull=True,
                                object_id=OuterRef('pk')
                            ).values(
                                'pk'
                            ).order_by(
                                '-pk'
                            )[:1],
                            output_field=IntegerField(),
                        )
                    ).order_by(
                    ).values(
                        'itemworker__requestworker__request'
                    ).annotate(
                        photos=ArrayAgg('photo')
                    ).values(
                        'photos'
                    ),
                    output_field=ArrayField(IntegerField()),
                ),
                []
            )
        )

    def with_new_finish_photo_count(self):
        return self.annotate(
            new_finish_photo_count=Coalesce(
                Subquery(
                    ItemWorkerFinish.objects.filter(
                        itemworker__itemworkerrejection__isnull=True,
                        itemworker__requestworker__request=OuterRef('pk'),
                        itemworker__requestworker__workerrejection__isnull=True,
                        itemworkerfinishconfirmation__isnull=True,
                    ).annotate(
                        photo_count=Subquery(
                            Photo.objects.filter(
                                content_type=ContentType.objects.get_for_model(
                                    ItemWorkerFinish
                                ),
                                photorejectioncomment__isnull=True,
                                object_id=OuterRef('pk')
                            ).values(
                                'object_id'
                            ).annotate(
                                Count('pk')
                            ).values(
                                'pk__count'
                            ),
                            output_field=IntegerField(),
                        )
                    ).order_by(
                    ).values(
                        'itemworker__requestworker__request'
                    ).annotate(
                        Sum('photo_count')
                    ).values(
                        'photo_count__sum'
                    ),
                    output_field=IntegerField(),
                ),
                0
            )
        )

    def with_finish_photos(self):
        return self.annotate(
            finish_photos=Coalesce(
                Subquery(
                    Photo.objects.filter(
                        itemworkerfinish__itemworker__requestworker__request=OuterRef('pk'),
                        itemworkerfinish__itemworker__itemworkerrejection__isnull=True,
                        itemworkerfinish__itemworker__requestworker__workerrejection__isnull=True,
                    ).values(
                        'itemworkerfinish__itemworker__requestworker__request'
                    ).annotate(
                        photos=ArrayAgg('pk')
                    ).values(
                        'photos'
                    ),
                    output_field=ArrayField(IntegerField())
                ),
                [],
                output_field=ArrayField(ArrayField(IntegerField()))
            )
        )

    def with_extra_photo_count(self):
        return self.annotate(
            extra_photo_count=Coalesce(
                Subquery(
                    Photo.objects.filter(
                        content_type=ContentType.objects.get_for_model(DeliveryRequest),
                        object_id=OuterRef('pk')
                    ).values(
                        'object_id'
                    ).annotate(
                        Count('pk')
                    ).values(
                        'pk__count'
                    ),
                    output_field=IntegerField(),
                ),
                0
            )
        )

    def with_extra_photos_exist(self):
        return self.annotate(
            extra_photos_exist=Exists(
                Photo.objects.filter(
                    content_type=ContentType.objects.get_for_model(DeliveryRequest),
                    object_id=OuterRef('pk')
                ).values(
                    'object_id'
                )
            )
        )

    def with_has_self_assigned_worker(self):
        return self.annotate(
            has_self_assigned_worker=Exists(
                RequestWorker.objects.annotate(
                    has_items=Exists(
                        ItemWorker.objects.filter(
                            requestworker=OuterRef('pk'),
                            itemworkerrejection__isnull=True,
                        )
                    )
                ).filter(
                    request=OuterRef('pk'),
                    author=F('worker__workeruser__user'),
                    workerrejection__isnull=True,
                    has_items=True,
                )
            )
        )

    def with_passport_selfies(self):
        return self.annotate(
            passport_selfies=Coalesce(
                Subquery(
                    RequestWorker.objects.annotate(
                        has_items=Exists(
                            ItemWorker.objects.filter(
                                requestworker=OuterRef('pk'),
                                itemworkerrejection__isnull=True,
                            )
                        )
                    ).filter(
                        request=OuterRef('pk'),
                        has_items=True,
                        workerrejection__isnull=True,
                    ).annotate(
                        photo=Subquery(
                            Photo.objects.filter(
                                content_type=ContentType.objects.get_for_model(Worker),
                                object_id=OuterRef('worker_id'),
                                image__endswith='selfie.jpg',
                            ).values(
                                'pk'
                            )
                        )
                    ).order_by(
                    ).values(
                        'request'
                    ).annotate(
                        ps_pks=ArrayAgg('photo')
                    ).values('ps_pks'),
                    output_field=ArrayField(IntegerField())
                ),
                []
            ),
        )

    def with_last_status_change(self):
        return self.annotate(
            last_status_change=Subquery(
                DeliveryRequestStatusChange.objects.filter(
                    request=OuterRef('pk')
                ).order_by(
                    '-timestamp'
                ).values(
                    'timestamp'
                )[:1]
            )
        )

    def with_is_overdue(self):
        deadline = timezone.now() - datetime.timedelta(minutes=15)
        return self.with_last_status_change(
        ).annotate(
            is_overdue=Case(
                When(
                    status=DeliveryRequest.WORKERS_ASSIGNED,
                    last_status_change__lt=deadline,
                    then=Value(True)
                ),
                default=Value(False),
                output_field=BooleanField()
            )
        )

    def with_is_worker_assignment_delayed(self):
        # requires confirmed_datetime field from cls.with_is_expiring
        min_confirmed_datetime = timezone.now() + datetime.timedelta(hours=2)

        return self.annotate(
            has_understaffed_items=Exists(
                DeliveryItem.objects.with_itemworker_count(
                ).filter(
                    request=OuterRef('pk'),
                    itemworker_count__lt=F('workers_required')
                )
            )
        ).annotate(
            is_worker_assignment_delayed=Case(
                When(
                    confirmed_timepoint__isnull=False,
                    confirmed_datetime__lte=min_confirmed_datetime,
                    has_understaffed_items=True,
                    then=Value(True)
                ),
                default=Value(False),
                output_field=BooleanField()
            )
        )

    def with_is_expiring(self, reserve_timedelta=datetime.timedelta(seconds=0)):
        min_confirmed_datetime = timezone.now() + reserve_timedelta
        return self.with_confirmed_timepoint(
        ).with_arrival_time(
        ).annotate(
            confirmed_datetime=MakeAware(
                F('date') + F('confirmed_timepoint'),
                tzinfo=timezone.get_current_timezone()
            )
        ).annotate(
            is_expiring=Case(
                When(
                    Q(
                        confirmed_timepoint__isnull=False,
                        arrival_time__isnull=True,
                        confirmed_datetime__lte=min_confirmed_datetime,
                    ),
                    then=Value(True)
                ),
                When(
                    Q(
                        confirmed_timepoint__isnull=False,
                        arrival_time__isnull=False,
                        confirmed_datetime__lte=(
                            F('arrival_time') +
                            Value(reserve_timedelta)
                        ),
                    ),
                    then=Value(True)
                ),
                default=Value(False),
                output_field=BooleanField()
            )
        )

    def with_can_be_edited(self):
        return self.annotate(
            can_be_edited=~Exists(
                DailyReconciliation.objects.filter(
                    location=OuterRef('location'),
                    date=OuterRef('date'),
                    dailyreconciliationconfirmation__isnull=False
                )
            )
        )

    def with_is_private(self):
        return self.annotate(
            is_private=Exists(
                PrivateDeliveryRequest.objects.filter(
                    request=OuterRef('pk')
                )
            )
        )

    def with_operator(self):
        return self.annotate(
            operator=Subquery(
                DeliveryRequestOperator.objects.filter(
                    request=OuterRef('pk')
                ).annotate(
                    data=JSONObject(
                        id='operator__id',
                        name=Coalesce(
                            NullIf('operator__first_name', Value('')),
                            'operator__username'
                        )
                    )
                ).values(
                    'data'
                ),
            )
        )

    def with_worker_count(self, confirmed=None, turnout=None):
        worker_sq = RequestWorker.objects.filter(
            request=OuterRef('pk'),
            workerrejection__isnull=True,
        ).order_by()

        filter_args = {}
        annotation_name_components = []

        if turnout is not None:
            filter_args['requestworkerturnout__isnull'] = not turnout
            if turnout:
                annotation_name_components.append('turnout')
            else:
                annotation_name_components.append('no_turnout')

        if turnout is not True:
            worker_sq = worker_sq.annotate(
                active=Exists(
                    ItemWorker.objects.filter(
                        requestworker=OuterRef('id'),
                        itemworkerrejection__isnull=True,
                    )
                )
            ).filter(
                active=True
            )

        if confirmed is not None:
            filter_args['workerconfirmation__isnull'] = not confirmed
            if confirmed:
                annotation_name_components.append('confirmed')
            else:
                annotation_name_components.append('unconfirmed')

        worker_sq = worker_sq.filter(**filter_args)
        annotation_name = '_'.join(['worker'] + annotation_name_components + ['count'])

        return self.annotate(**{
            annotation_name: Coalesce(
                Subquery(
                    worker_sq.order_by(
                    ).values(
                        'request'
                    ).annotate(
                        count=Count('pk')
                    ).values('count'),
                    output_field=IntegerField()
                ),
                0,
            )
        })

    def with_payment_status(self, customer_id):
        from .reconciliation import Reconciliation, ReconciliationPaymentOperation

        reconciliation_sq = Reconciliation.objects.filter(
            customer=customer_id,
            first_day__lte=OuterRef('date'),
            last_day__gte=OuterRef('date'),
        ).annotate(
            is_paid=Exists(
                ReconciliationPaymentOperation.objects.filter(
                    reconciliation=OuterRef('pk')
                )
            )
        ).values('is_paid')

        return self.annotate(
            is_paid=Coalesce(
                Subquery(
                    reconciliation_sq.filter(
                        location=OuterRef('location')
                    )
                ),
                Subquery(
                    reconciliation_sq.filter(
                        location__isnull=True
                    )
                ),
                output_field=BooleanField()
            )
        )

    def with_zone_name(self):
        return self.annotate(
            zone_name=Subquery(
                ZoneGroup.objects.filter(
                    locationzonegroup__location=OuterRef('location')
                ).values(
                    'name'
                ),
                output_field=models.CharField()
            )
        )

    def filter_by_text(self, text, mode='bo'):
        queryset = self.annotate(
            has_item_with_text=Exists(
                DeliveryItem.objects.filter(
                    Q(code__icontains=text) |
                    Q(shipment_type__icontains=text) |
                    Q(address__icontains=text),
                    request=OuterRef('pk')
                )
            ),
            pk_str=Cast(
                'pk',
                output_field=models.CharField()
            )
        )
        predicates = (
            Q(pk_str__icontains=text) |
            Q(driver_name__icontains=text) |
            Q(has_item_with_text=True)
        )
        if mode == 'customer_autocomplete':
            pass
        else:
            predicates |= (
                Q(route__icontains=text) |
                Q(driver_phones__icontains=text) |
                Q(comment__icontains=text)
            )
            if mode == 'customer':
                predicates |= Q(customer_comment__icontains=text)
            else:
                queryset = queryset.annotate(
                    has_worker_with_text=Exists(
                        RequestWorker.objects.filter(
                            Q(worker__last_name__icontains=text) |
                            Q(worker__name__icontains=text) |
                            Q(worker__patronymic__icontains=text),
                            request=OuterRef('pk')
                        )
                    ),
                )
                predicates |= (
                    Q(has_worker_with_text=True) |
                    Q(customer__cust_name__icontains=text)
                )
        return queryset.filter(predicates)

    def filter_self_assign_ready(self, day, zone_id):
        queryset = self.with_is_private(
        ).filter(
            date=day,
            delivery_service__isnull=False,
            location__locationzonegroup__zone_group=zone_id,
            is_private=False,
        ).exclude(
            status__in=DeliveryRequest.FINAL_STATUSES,
        )

        if 'new_worker_timepoint' in queryset.query.annotations:
            queryset = queryset.filter(
                new_worker_timepoint__isnull=False,
            )
        else:
            queryset = queryset.annotate(
                has_understaffed_items=Exists(
                    DeliveryItem.objects.with_itemworker_count(
                    ).filter(
                        request=OuterRef('pk'),
                        itemworker_count__lt=F('workers_required'),
                        confirmed_timepoint__isnull=False,
                    )
                )
            ).filter(
                has_understaffed_items=True,
            )
        return queryset

    def _finalize_item_annotation(self, item_field_names, item_sq):
        return self.annotate(
            items=Coalesce(
                Subquery(
                    item_sq.annotate(
                        item_fields=JSONObject(**{
                            field: field
                            for field in item_field_names
                        })
                    ).order_by(
                    ).values(
                        'request'
                    ).annotate(
                        items_list=ArrayAgg(
                            'item_fields',
                            ordering=(
                                'confirmed_timepoint',
                                'interval_begin',
                                'interval_end',
                                'id',
                            )
                        )
                    ).values(
                        'items_list'
                    ),
                    output_field=ArrayField(JSONField())
                ),
                []
            )
        )

    def with_items_for_assigned_worker(
            self,
            worker_id,
            location=None,
            with_amount_estimate=False
    ):
        item_field_names = [
            'address',
            'id',
            'interval_begin',
            'interval_end',
            'confirmed_timepoint',
            'log',
            'mass',
            'metro',
            'shipment_type',
        ]
        if with_amount_estimate:
            item_field_names.extend([  # to discard
                'carrying_distance',
                'floor',
                'has_elevator',
            ])

        itemworker_ssq = ItemWorker.objects.filter(
            item=OuterRef('id'),
            requestworker__worker=worker_id,
            itemworkerrejection__isnull=True,
            requestworker__workerrejection__isnull=True,
        )
        item_sq = DeliveryItem.objects.annotate(
            worker_assigned=Exists(
                itemworker_ssq
            )
        ).annotate(
            log=Subquery(
                itemworker_ssq.with_status(
                ).with_photos(
                ).annotate(
                    itemworker_fields=JSONObject(
                        start_photos='start_photos',
                        finish_photos='finish_photos',
                        waybill='itemworkerfinish__photo',
                        start='itemworkerstart__timestamp',
                        start_confirmed='itemworkerstart__itemworkerstartconfirmation__timestamp',
                        finish='itemworkerfinish__timestamp',
                        finish_confirmed='itemworkerfinish__itemworkerfinishconfirmation__timestamp',
                        status='status',
                        discrepancy_ok='itemworkerstart__itemworkerdiscrepancycheck__is_ok',
                        is_suspicious='itemworkerstart__is_suspicious',
                    )
                ).values(
                    'itemworker_fields'
                ),
                output_field=JSONField()
            ),
        ).filter(
            request=OuterRef('pk'),
            worker_assigned=True,
        ).with_metro(
        )
        if location is not None:
            item_sq = item_sq.with_distance(location.latitude, location.longitude)
            item_field_names.append('distance')
        return self._finalize_item_annotation(item_field_names, item_sq)

    def with_items_for_unassigned_worker(self, location=None):
        item_field_names = [
            'address',
            'id',
            'interval_begin',
            'interval_end',
            'metro',
            'confirmed_timepoint',
            # to discard
            'carrying_distance',
            'floor',
            'has_elevator',
            'mass',
        ]
        item_sq = DeliveryItem.objects.with_itemworker_count(
        ).filter(
            request=OuterRef('pk'),
            itemworker_count__lt=F('workers_required'),
        ).with_metro(
        )
        if location is not None:
            item_sq = item_sq.with_distance(location.latitude, location.longitude)
            item_field_names.append('distance')
        return self._finalize_item_annotation(item_field_names, item_sq)

    def with_items_for_backoffice(self, with_workers=False):
        item_field_names = [
            'id',
            'interval_begin',
            'interval_end',
            'code',
            'mass',
            'volume',
            'max_size',
            'place_count',
            'shipment_type',
            'address',
            'has_elevator',
            'floor',
            'carrying_distance',
            'workers_required',
            'metro',
            'confirmed_timepoint',
        ]
        item_sq = DeliveryItem.objects.filter(
            request=OuterRef('pk')
        ).with_metro()
        if with_workers:
            item_field_names.append('assigned_workers')
            item_sq = item_sq.with_assigned_workers()
        return self._finalize_item_annotation(item_field_names, item_sq)

    def with_items_for_customer(self, item_field_names=None):
        if item_field_names is None:
            item_field_names = [
                'id',
                'interval_begin',
                'interval_end',
                'code',
                'mass',
                'volume',
                'max_size',
                'place_count',
                'shipment_type',
                'address',
                'has_elevator',
                'floor',
                'carrying_distance',
                'workers_required',
            ]
        item_sq = DeliveryItem.objects.filter(
            request=OuterRef('pk')
        )
        return self._finalize_item_annotation(item_field_names, item_sq)

    def with_items_for_map(self):
        item_field_names = [
            'pk',
            'code',
            'geotag_',
        ]
        item_sq = DeliveryItem.objects.with_geotag(
            with_timestamp=True
        ).filter(
            request=OuterRef('pk')
        )
        return self._finalize_item_annotation(item_field_names, item_sq)

    def with_other_workers(self, worker_id):
        return self.annotate(
            other_workers=Coalesce(
                Subquery(
                    RequestWorker.objects.with_full_name(
                    ).annotate(
                        on_same_item=Exists(
                            ItemWorker.objects.annotate(
                                same_item=Exists(
                                    ItemWorker.objects.filter(
                                        requestworker__worker=worker_id,
                                        itemworkerrejection__isnull=True,
                                        item=OuterRef('item')
                                    )
                                )
                            ).filter(
                                requestworker=OuterRef('pk'),
                                itemworkerrejection__isnull=True,
                                same_item=True,
                            )
                        )
                    ).exclude(
                        worker=worker_id
                    ).filter(
                        on_same_item=True,
                        workerrejection__isnull=True,
                        request=OuterRef('pk'),
                    ).annotate(
                        worker_fields=JSONObject(
                            name='full_name',
                            phone=Concat(
                                Value('+'),
                                F('worker__tel_number'),
                            )
                        )
                    ).values(
                        'request'
                    ).annotate(
                        workers_list=ArrayAgg(
                            'worker_fields'
                        )
                    ).values(
                        'workers_list'
                    ),
                    output_field=ArrayField(JSONField())
                ),
                []
            )
        )


class DeliveryRequest(models.Model):
    AUTOTARIFICATION = 'autotarification_attempt'
    NEW = 'new'
    DECLINED = 'declined'
    CANCELLED = 'cancelled'
    REMOVED = 'removed'
    FAILED = 'failed'
    DRIVER_CALLBACK = 'driver_callback'
    NO_RESPONSE = 'no_response'
    CANCELLED_WITH_PAYMENT = 'cancelled_with_payment'
    TIMEPOINT_CONFIRMED = 'timepoint_confirmed'
    ARRIVAL_REJECTED = 'partly_arrival_submitted'
    WORKERS_ASSIGNED = 'partly_confirmed'
    WORKERS_CONFIRMED = 'partly_arrived'
    ARRIVED = 'partly_photo_attached'
    CHEQUE_ATTACHED = 'photo_attached'
    COMPLETE = 'finished'

    CALLBACK_STATUSES = [
        DRIVER_CALLBACK,
        NO_RESPONSE,
    ]

    FAIL_STATUSES = [
        DECLINED,
        CANCELLED,
        REMOVED,
        FAILED,
    ]

    WORK_STATUSES = [
        ARRIVAL_REJECTED,
        WORKERS_ASSIGNED,
        WORKERS_CONFIRMED,
        ARRIVED,
        CHEQUE_ATTACHED,
    ]

    MANUAL_STATUSES = FAIL_STATUSES + CALLBACK_STATUSES + [
        NEW,
        CANCELLED_WITH_PAYMENT,
    ]

    CANCELLED_STATUSES = FAIL_STATUSES + [
        CANCELLED_WITH_PAYMENT,
    ]

    SUCCESS_STATUSES = [
        CANCELLED_WITH_PAYMENT,
        COMPLETE,
    ]

    FINAL_STATUSES = SUCCESS_STATUSES + FAIL_STATUSES

    STATUS_TYPES = (
        (AUTOTARIFICATION, 'Тарифицируется'),
        (NEW, 'Новая'),
        (DECLINED, 'Не принята в работу'),
        (CANCELLED, 'Отмена'),
        (REMOVED, 'Удалена'),
        (FAILED, 'Срыв заявки'),
        (DRIVER_CALLBACK, 'Перезвонит сам'),
        (NO_RESPONSE, 'Нет ответа'),
        (CANCELLED_WITH_PAYMENT, 'Отмена с оплатой'),
        (TIMEPOINT_CONFIRMED, 'Поиск исполнителя'),
        (WORKERS_ASSIGNED, 'Назначен'),
        (ARRIVAL_REJECTED, 'Принята исполнителем'),
        (WORKERS_CONFIRMED, 'Принята исполнителем'),
        (ARRIVED, 'На месте'),
        (CHEQUE_ATTACHED, 'Проверка табеля'),
        (COMPLETE, 'Выполнена'),
    )

    SORTING_ORDER = {
        AUTOTARIFICATION: 1,
        NEW: 2,
        DECLINED: 3,
        CANCELLED: 4,
        REMOVED: 5,
        FAILED: 6,
        DRIVER_CALLBACK: 7,
        NO_RESPONSE: 8,
        TIMEPOINT_CONFIRMED: 9,
        WORKERS_ASSIGNED: 10,
        ARRIVAL_REJECTED: 11,
        WORKERS_CONFIRMED: 12,
        ARRIVED: 13,
        CHEQUE_ATTACHED: 14,
        CANCELLED_WITH_PAYMENT: 15,
        COMPLETE: 16,
    }

    CUSTOMER_CONFIRMED = 'confirmed'
    SUSPICIOUS = 'suspicious'
    NORMAL = 'normal'

    CUSTOMER_RESOLUTIONS = [
        (CUSTOMER_CONFIRMED, CUSTOMER_CONFIRMED),
        (SUSPICIOUS, SUSPICIOUS),
        (NORMAL, NORMAL),
    ]

    ACTIVE = 'active'
    PAID = 'paid'
    IN_PAYMENT = 'in_payment'

    PAYMENT_STATUSES = [
        (ACTIVE, ACTIVE),
        (PAID, PAID),
        (IN_PAYMENT, IN_PAYMENT),
    ]

    timestamp = models.DateTimeField(
        verbose_name='Время создания',
        default=timezone.now
    )
    author = models.ForeignKey(
        User,
        verbose_name='Автор',
        on_delete=models.PROTECT
    )

    customer = models.ForeignKey(
        Customer,
        verbose_name='Клиент',
        on_delete=models.PROTECT
    )
    location = models.ForeignKey(
        CustomerLocation,
        verbose_name='Объект (филиал)',
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        db_index=False,
    )

    date = models.DateField(
        verbose_name='Дата',
    )

    status = models.CharField(
        verbose_name='Статус',
        max_length=200,
        choices=STATUS_TYPES,
        default=AUTOTARIFICATION
    )
    status_description = models.CharField(
        verbose_name='Статус (описание)',
        max_length=200,
        default='Тарифицируется'
    )

    route = models.TextField(
        verbose_name='Маршрут',
        blank=True,
        null=True
    )

    driver_name = models.TextField(
        verbose_name='ФИО водителя',
        blank=True,
        null=True
    )
    driver_phones = models.TextField(
        verbose_name='Телефоны водителя',
        blank=True,
        null=True
    )

    delivery_service = models.ForeignKey(
        DeliveryService,
        verbose_name='Услуга',
        on_delete=models.PROTECT,
        blank=True,
        null=True
    )
    comment = models.TextField(
        verbose_name='Комментарий',
        blank=True,
        null=True
    )
    customer_comment = models.TextField(
        verbose_name='Комментарий клиента',
        blank=True,
        null=True
    )

    objects = DeliveryRequestQuerySet.as_manager()

    def __init__(self, *args, **kwargs):
        super(DeliveryRequest, self).__init__(*args, **kwargs)
        self._loaded_values = {}

    def __str__(self):
        return '{} {}'.format(
            self.pk,
            string_from_date(self.date)
        )

    class Meta:
        indexes = [
            models.Index(
                fields=['location', 'date'],
                name='deliveryreq_location_date_idx',
            ),
        ]

    @classmethod
    def from_db(cls, db, field_names, values):
        new = super(DeliveryRequest, cls).from_db(db, field_names, values)
        new._loaded_values = dict(zip(field_names, values))
        return new

    def save(self, **kwargs):
        user = kwargs.pop('user', None)
        if not self._loaded_values:
            user = self.author
        if user is None:
            raise ValueError('Delivery request change author cannot be None.')
        super(DeliveryRequest, self).save(**kwargs)
        if (
                ('status' not in self._loaded_values or
                 self._loaded_values['status'] != self.status)
                and
                ('update_fields' not in kwargs or 'status' in kwargs['update_fields'])
        ):
            DeliveryRequestStatusChange.objects.create(
                status=self.status,
                request=self,
                timestamp=timezone.now(),
                author=user
            )
            self._loaded_values['status'] = self.status

    def code(self):
        items = self.deliveryitem_set.all().order_by('pk')
        if items.count() > 1:
            return self.route + ': ' + '; '.join([item.code for item in items])
        else:
            return items.first().code

    def address(self, delimeter='; '):
        items = self.deliveryitem_set.all().order_by('pk')
        return delimeter.join([item.address for item in items])

    def mass_text(self):
        items = self.deliveryitem_set.all().order_by('pk')
        return '; '.join([str(item.mass) for item in items])

    def mass(self):
        items = self.deliveryitem_set.all().order_by('pk')
        return sum([item.mass for item in items]) or 0

    def active_workers(self):
        return ItemWorker.objects.filter(
            item__request=self,
            requestworker__workerrejection__isnull=True,
            itemworkerrejection__isnull=True,
        )

    @cached_property
    def confirmed_timepoint(self):
        return self.deliveryitem_set.filter(
            workers_required__gt=0
        ).aggregate(
            Min('confirmed_timepoint')
        )['confirmed_timepoint__min']


class PrivateDeliveryRequest(models.Model):
    timestamp = models.DateTimeField(
        verbose_name='Время создания',
        default=timezone.now
    )
    author = models.ForeignKey(
        User,
        verbose_name='Автор',
        on_delete=models.PROTECT
    )

    request = models.OneToOneField(
        DeliveryRequest,
        verbose_name='Заявка',
        on_delete=models.CASCADE
    )

    def __str__(self):
        return str(self.request)


class DeliveryRequestConfirmation(models.Model):
    timestamp = models.DateTimeField(
        verbose_name='Время подтверждения',
        default=timezone.now
    )
    author = models.ForeignKey(
        User,
        verbose_name='Автор',
        on_delete=models.PROTECT
    )

    request = models.OneToOneField(
        DeliveryRequest,
        verbose_name='Заявка',
        on_delete=models.CASCADE
    )

    def __str__(self):
        return str(self.request)


class DeliveryRequestStatusChange(models.Model):
    timestamp = models.DateTimeField(
        verbose_name='Время изменения',
        default=timezone.now
    )
    author = models.ForeignKey(
        User,
        verbose_name='Автор',
        on_delete=models.PROTECT,
    )

    request = models.ForeignKey(
        DeliveryRequest,
        verbose_name='Заявка',
        on_delete=models.CASCADE
    )
    status = models.CharField(
        verbose_name='Статус',
        max_length=200,
        choices=DeliveryRequest.STATUS_TYPES,
    )

    def __str__(self):
        return f'{self.request.pk} {self.status}'


class DeliveryRequestTimepointChange(models.Model):
    timestamp = models.DateTimeField(
        verbose_name='Время изменения',
        default=timezone.now
    )
    author = models.ForeignKey(
        User,
        verbose_name='Автор',
        on_delete=models.PROTECT,
    )
    request = models.ForeignKey(
        DeliveryRequest,
        verbose_name='Заявка',
        on_delete=models.CASCADE
    )
    confirmed_timepoint = models.TimeField(
        verbose_name='Согласованное время подачи',
        blank=True,
        null=True
    )

    def __str__(self):
        return f'{self.request.pk} {self.confirmed_timepoint}'


class DeliveryRequestOperator(models.Model):
    timestamp = models.DateTimeField(
        verbose_name='Время создания',
        default=timezone.now
    )
    operator = models.ForeignKey(
        User,
        verbose_name='Оператор',
        on_delete=models.PROTECT
    )

    request = models.OneToOneField(
        DeliveryRequest,
        verbose_name='Заявка',
        on_delete=models.CASCADE
    )

    def __str__(self):
        return f'{self.request.pk}/{self.operator.username}'


class DeliveryItemQuerySet(models.QuerySet):

    def with_dadata_address_exists(self):
        return self.annotate(
            dadata_address_exists=Exists(
                NormalizedAddress.objects.filter(
                    location__pk=OuterRef('pk'),
                    version=OuterRef('address_version')
                )
            )
        )

    def with_googlemaps_address_exists(self):
        return self.annotate(
            googlemaps_address_exists=Exists(
                GoogleMapsAddress.objects.filter(
                    location__pk=OuterRef('pk'),
                    version=OuterRef('address_version')
                )
            ),
        )

    def with_metro(self):
        # todo combine into one address annotation?
        return self.annotate(
            metro=Subquery(
                NormalizedAddress.objects.filter(
                    location=OuterRef('pk'),
                    version=OuterRef('address_version'),
                ).annotate(
                    # todo process null lines/stations correctly
                    metro=JSONObject(
                        region='region',
                        line='nearest_metro_line',
                        station='nearest_metro_station',
                    )
                ).values(
                    'metro'
                ),
                output_field=JSONField()
            )
        )

    def with_geotag(self, with_timestamp=False):
        fields = [
            'latitude',
            'longitude',
        ]
        if with_timestamp:
            fields.append('timestamp')
        return self.annotate(
            geotag_=Subquery(
                NormalizedAddress.objects.filter(
                    location=OuterRef('pk'),
                    version=OuterRef('address_version'),
                ).annotate(
                    address_fields=JSONObject(**{
                        field: field
                        for field in fields
                    })
                ).values(
                    'address_fields'
                ),
                output_field=JSONField()
            )
        )

    def with_itemworker_count(self):
        return self.annotate(
            itemworker_count=Coalesce(
                Subquery(
                    ItemWorker.objects.filter(
                        item=OuterRef('pk'),
                        requestworker__workerrejection__isnull=True,
                        itemworkerrejection__isnull=True,
                    ).order_by(
                    ).values(
                        'item'
                    ).annotate(
                        count=Count('id')
                    ).values(
                        'count'
                    ),
                    output_field=IntegerField()
                ),
                0
            )
        )

    def with_assigned_workers(self):
        return self.annotate(
            assigned_workers=Coalesce(
                Subquery(
                    ItemWorker.objects.filter(
                        item=OuterRef('pk'),
                        requestworker__workerrejection__isnull=True,
                        itemworkerrejection__isnull=True
                    ).annotate(
                        worker_fields=JSONObject(
                            id='requestworker__worker',
                            name=PostgresConcatWS(
                                Value(' '),
                                F('requestworker__worker__last_name'),
                                F('requestworker__worker__name'),
                                NullIf(
                                    F('requestworker__worker__patronymic'),
                                    Value('')
                                )
                            ),
                            start='itemworkerstart__timestamp',
                        )
                    ).order_by(
                    ).values(
                        'item'
                    ).annotate(
                        workers_list=ArrayAgg(
                            'worker_fields',
                            ordering=(
                                'timestamp',
                            )
                        )
                    ).values(
                        'workers_list'
                    ),
                    output_field=ArrayField(JSONField())
                ),
                []
            )
        )

    def with_distance(self, latitude, longitude):
        return self.annotate(
            distance=Subquery(
                NormalizedAddress.objects.filter(
                    location=OuterRef('pk'),
                    version=OuterRef('address_version'),
                ).annotate(
                    item_distance=Haversine(
                        'latitude',
                        latitude,
                        'longitude',
                        longitude,
                    )
                ).values(
                    'item_distance'
                ),
                output_field=FloatField()
            )
        )


class DeliveryItem(models.Model):
    request = models.ForeignKey(
        DeliveryRequest,
        verbose_name='Заявка',
        on_delete=models.PROTECT
    )

    interval_begin = models.TimeField(
        verbose_name='Время исполнения с'
    )
    interval_end = models.TimeField(
        verbose_name='Время исполнения по'
    )

    code = models.TextField(
        verbose_name='Индекс',
    )
    mass = models.FloatField(
        verbose_name='Масса'
    )
    volume = models.FloatField(
        verbose_name='Объем'
    )
    max_size = models.FloatField(
        verbose_name='Макс. габарит',
        blank=True,
        null=True
    )
    place_count = models.IntegerField(
        verbose_name='Кол-во мест'
    )
    shipment_type = models.TextField(
        verbose_name='Характер груза',
    )
    address = models.TextField(
        verbose_name='Адрес'
    )
    address_version = models.IntegerField(
        verbose_name='Версия адреса',
        default=0
    )
    has_elevator = models.BooleanField(
        verbose_name='Есть лифт',
        blank=True,
        null=True
    )
    floor = models.IntegerField(
        verbose_name='Этаж',
        blank=True,
        null=True
    )
    carrying_distance = models.IntegerField(
        verbose_name='Пронос',
        blank=True,
        null=True
    )
    workers_required = models.PositiveIntegerField(
        verbose_name='Необходимое число рабочих',
        default=1
    )
    confirmed_timepoint = models.TimeField(
        verbose_name='Согласованное время подачи',
        blank=True,
        null=True,
    )

    objects = DeliveryItemQuerySet.as_manager()

    def __str__(self):
        return '{}, Заявка №{}, {}'.format(
            self.pk,
            self.request.pk,
            self.address
        )

    @cached_property
    def geotag(self):
        if not hasattr(self, 'geotag_',):
            return DeliveryItem.objects.with_geotag().values_list(
                'geotag_',
                flat=True
            ).get(pk=self.pk)
        return getattr(self, 'geotag_')


class NormalizedAddressQuerySet(models.QuerySet):
    def with_itemworker_count(self):
        return self.annotate(
            itemworker_count=Coalesce(
                Subquery(
                    ItemWorker.objects.filter(
                        item=OuterRef('location'),
                        requestworker__workerrejection__isnull=True,
                        itemworkerrejection__isnull=True,
                    ).order_by(
                    ).values(
                        'item'
                    ).annotate(
                        count=Count('id')
                    ).values(
                        'count'
                    ),
                    output_field=IntegerField()
                ),
                0
            )
        )


# Address from dadata.ru
class NormalizedAddress(models.Model):
    timestamp = models.DateTimeField(
        verbose_name='Время прибытия',
        default=timezone.now
    )

    location = models.ForeignKey(
        DeliveryItem,
        verbose_name='Адрес',
        on_delete=models.PROTECT
    )
    version = models.IntegerField(
        verbose_name='Версия',
    )

    latitude = models.FloatField(
        verbose_name='Широта'
    )
    longitude = models.FloatField(
        verbose_name='Долгота'
    )

    region = models.TextField(
        verbose_name='ISO код региона',
        blank=True,
        null=True,
    )
    nearest_metro_line = models.TextField(
        verbose_name='Ближайшая линия метро',
        blank=True,
        null=True
    )
    nearest_metro_station = models.TextField(
        verbose_name='Ближайшая станция метро',
        blank=True,
        null=True
    )

    raw_data = models.TextField(
        verbose_name='Сырые данные'
    )

    objects = NormalizedAddressQuerySet.as_manager()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['location', 'version'],
                name='normalized_address_unique_location_version'
            ),
        ]

    def __str__(self):
        return '{} {} {}, {}'.format(
            self.location.request.pk,
            self.location.address,
            self.latitude,
            self.longitude
        )


class GoogleMapsAddress(models.Model):
    timestamp = models.DateTimeField(
        verbose_name='Время прибытия',
        default=timezone.now
    )

    location = models.ForeignKey(
        DeliveryItem,
        verbose_name='Адрес',
        on_delete=models.PROTECT
    )
    version = models.IntegerField(
        verbose_name='Версия',
    )

    raw_data = models.TextField(
        verbose_name='Сырые данные'
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['location', 'version'],
                name='googlemaps_address_unique_location_version'
            ),
        ]

    def __str__(self):
        return '{} {}'.format(
            self.location.request.pk,
            self.location.address,
        )


class AssignedWorker(models.Model):
    request = models.ForeignKey(
        DeliveryRequest,
        verbose_name='Заявка',
        related_name='assigned_workers',
        on_delete=models.PROTECT,
    )
    worker = models.ForeignKey(
        Worker,
        verbose_name='Рабочий',
        related_name='assigned_delivery_requests',
        on_delete=models.PROTECT,
    )

    confirmed = models.BooleanField(
        verbose_name='Подтверждено (оператором или рабочим)',
        default=False
    )
    confirmed_by = models.ForeignKey(
        User,
        verbose_name='Подтвердивший',
        on_delete=models.PROTECT,
        blank=True,
        null=True
    )

    def __str__(self):
        return '{} {}'.format(
            self.request.pk,
            self.worker
        )


class AssignedWorkerAuthor(models.Model):
    timestamp = models.DateTimeField(
        verbose_name='Время назначения',
        default=timezone.now
    )
    author = models.ForeignKey(
        User,
        verbose_name='Автор',
        on_delete=models.PROTECT
    )

    assigned_worker = models.OneToOneField(
        AssignedWorker,
        verbose_name='Рабочий',
        on_delete=models.CASCADE,
    )

    def __str__(self):
        return f'{self.author.username} {self.assigned_worker}'


# Todo: rename to GeoLocation
class Location(models.Model):
    timestamp = models.DateTimeField(
        verbose_name='Время прибытия',
        default=timezone.now
    )

    provider = models.TextField(
        verbose_name='Провайдер'
    )
    latitude = models.FloatField(
        verbose_name='Широта'
    )
    longitude = models.FloatField(
        verbose_name='Долгота'
    )
    time = models.BigIntegerField(
        verbose_name='Время GPS'
    )


class ArrivalLocation(models.Model):
    timestamp = models.DateTimeField(
        verbose_name='Время прибытия',
        default=timezone.now
    )

    worker = models.OneToOneField(
        AssignedWorker,
        verbose_name='Рабочий',
        on_delete=models.PROTECT
    )

    confirmed = models.BooleanField(
        verbose_name='Подтверждено оператором'
    )

    location = models.OneToOneField(
        Location,
        null=True,
        default=None,
        on_delete=models.PROTECT
    )

    # По сути, тут кэшируется факт того, что точка из location слишком далеко от
    # любого из адресов в заявке
    is_suspicious = models.BooleanField(
        verbose_name='Отметка подозрительна',
        default=True
    )

    def __str__(self):
        return '{} {}'.format(
            self.timestamp,
            self.worker
        )


class TurnoutPhoto(models.Model):
    timestamp = models.DateTimeField(
        verbose_name='Время фото',
        default=timezone.now
    )

    location = models.OneToOneField(
        ArrivalLocation,
        verbose_name='Точка прибытия',
        on_delete=models.PROTECT
    )

    photo = models.ForeignKey(
        Photo,
        verbose_name='Фото',
        on_delete=models.PROTECT
    )
    photo_rejected = models.BooleanField(
        verbose_name='Фото отклонено',
        default=False
    )
    rejection_comment = models.TextField(
        verbose_name='Комментарий',
        default=''
    )


class PhotoRejectionComment(models.Model):
    timestamp = models.DateTimeField(
        default=timezone.now
    )
    author = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
    )

    photo = models.OneToOneField(
        Photo,
        verbose_name='Фото',
        on_delete=models.PROTECT
    )
    rejection_comment = models.TextField(
        verbose_name='Комментарий',
        default=''
    )


class AssignedWorkerTurnout(models.Model):
    timestamp = models.DateTimeField(
        verbose_name='Время подтверждения',
        default=timezone.now,
    )

    assigned_worker = models.OneToOneField(
        AssignedWorker,
        verbose_name='Рабочий',
        related_name='turnout',
        on_delete=models.PROTECT,
    )

    turnout = models.OneToOneField(
        WorkerTurnout,
        verbose_name='Выход',
        on_delete=models.PROTECT,
    )

    def __str__(self):
        return '{} {}'.format(
            self.assigned_worker.worker,
            self.turnout.pk
        )


class DriverSms(models.Model):
    timestamp = models.DateTimeField(
        verbose_name='Время отправки',
        default=timezone.now
    )

    request = models.ForeignKey(
        DeliveryRequest,
        verbose_name='Заявка',
        on_delete=models.PROTECT
    )

    text = models.TextField(
        verbose_name='Текст',
    )

    def __str__(self):
        return '{} {}'.format(
            as_default_timezone(self.timestamp).strftime('%d.%m.%Y %H:%M'),
            self.request.pk
        )


class SmsPhone(models.Model):
    sms = models.ForeignKey(
        DriverSms,
        verbose_name='СМС',
        on_delete=models.CASCADE
    )

    phone = models.TextField(
        verbose_name='Телефон',
    )

    def __str__(self):
        return '{} {}'.format(
            self.sms.request.pk,
            self.phone
        )


class ZoneGroup(models.Model):
    name = models.CharField(
        verbose_name='Название',
        max_length=64,
    )
    code = models.CharField(
        verbose_name='Код',
        max_length=64,
        unique=True,
    )

    def __str__(self):
        return self.name


class WeekendRest(models.Model):
    zone = models.OneToOneField(
        ZoneGroup,
        on_delete=models.CASCADE
    )

    def __str__(self):
        return str(self.zone)


class DeliveryZone(models.Model):
    group = models.ForeignKey(
        ZoneGroup,
        verbose_name='Группа',
        on_delete=models.PROTECT
    )
    code = models.CharField(
        verbose_name='Код зоны',
        max_length=64,
        unique=True
    )
    name = models.CharField(
        verbose_name='Название',
        max_length=64,
    )

    def __str__(self):
        return f'{self.group}/{self.name} ({self.code})'


class LocationZoneGroup(models.Model):
    # Todo: OneToOne?
    location = models.ForeignKey(
        CustomerLocation,
        verbose_name='Объект (филиал)',
        on_delete=models.PROTECT
    )
    zone_group = models.ForeignKey(
        ZoneGroup,
        verbose_name='Группа зон доставки',
        on_delete=models.PROTECT
    )

    def __str__(self):
        return f'{self.zone_group} - {self.location}'


class OperatorZoneGroup(models.Model):
    operator = models.ForeignKey(
        User,
        verbose_name='Оператор',
        on_delete=models.PROTECT
    )

    zone_group = models.ForeignKey(
        ZoneGroup,
        verbose_name='Группа зон доставки',
        on_delete=models.PROTECT
    )

    def __str__(self):
        return f'{self.operator.username}/{self.operator.first_name}/{self.zone_group.name}'


class WorkerZone(models.Model):
    worker = models.OneToOneField(
        Worker,
        on_delete=models.PROTECT
    )
    zone = models.ForeignKey(
        ZoneGroup,
        on_delete=models.PROTECT
    )

    def __str__(self):
        return f'{self.worker} {self.zone}'


class TurnoutDiscrepancyCheck(models.Model):
    timestamp = models.DateTimeField(
        verbose_name='Время проверки',
        default=timezone.now,
    )
    author = models.ForeignKey(
        User,
        verbose_name='Автор',
        on_delete=models.PROTECT
    )
    turnout = models.OneToOneField(
        ArrivalLocation,
        verbose_name='Выход',
        on_delete=models.PROTECT
    )
    is_ok = models.BooleanField(
        null=True,
        default=None,
        db_index=True,
    )
    comment = models.TextField(
        verbose_name='Комментарий',
        default=''
    )

    def __str__(self):
        return f'{self.pk} {self.author}'


class RequestsAutoMergeEnabled(models.Model):
    location = models.OneToOneField(
        CustomerLocation,
        verbose_name='Объект (филиал)',
        on_delete=models.CASCADE
    )

    def __str__(self):
        return str(self.location)


class DailyReconciliationQuerySet(models.QuerySet):
    def with_last_notifications(self):
        return self.annotate(
            last_notifications=Coalesce(
                Subquery(
                    DailyReconciliationNotification.objects.filter(
                        reconciliation=OuterRef('pk')
                    ).annotate(
                        notification_fields=JSONObject(
                            is_ok='is_ok',
                            timestamp='timestamp',
                            attachment='attachment',
                            recipient_email='recipient_email',
                        )
                    ).values(
                        'reconciliation'
                    ).annotate(
                        notifications_list=ArrayAgg(
                            'notification_fields',
                            ordering=('-timestamp',)
                        )
                    ).values(
                        'notifications_list'
                    ),
                    output_field=ArrayField(JSONField())
                ),
                []
            )
        )

    def with_status(self):
        delivery_request_qs = DeliveryRequest.objects.with_customer_resolution(
        ).filter(
            date=OuterRef('date'),
            location=OuterRef('location')
        )

        return self.annotate(
            last_notification=Subquery(
                DailyReconciliationNotification.objects.filter(
                    reconciliation=OuterRef('pk')
                ).order_by(
                    '-timestamp'
                ).values(
                    'reconciliation'
                ).annotate(
                    data=JSONObject(
                        is_ok='is_ok',
                        timestamp='timestamp',
                    )
                ).values(
                    'data'
                )[:1],
            ),
            lacks_info=Exists(
                delivery_request_qs.filter(
                    Q(customer_resolution=DeliveryRequest.SUSPICIOUS) |
                    ~Q(status__in=DeliveryRequest.FINAL_STATUSES)
                )
            ),
            all_requests_confirmed=~Exists(
                delivery_request_qs.exclude(
                    customer_resolution=DeliveryRequest.CUSTOMER_CONFIRMED
                )
            ),
        ).annotate(
            status=Case(
                When(
                    dailyreconciliationconfirmation__isnull=False,
                    then=Value('confirmed')
                ),
                When(
                    last_notification__isnull=False,
                    then=Value('notification_sent')
                ),
                When(
                    lacks_info=False,
                    then=Value('ready_for_notification')
                ),
                default=Value('new'),
                output_field=models.CharField()
            )
        )

    def with_worked_hours(self):
        worker_turnout_sq = RequestWorkerTurnout.objects.filter(
            requestworker__request__date=OuterRef('date'),
            requestworker__request__location=OuterRef('location'),
            workerturnout__hours_worked__isnull=False,
        ).values(
            'requestworker__request__date',
            'requestworker__request__location',
        ).annotate(
            Sum('workerturnout__hours_worked')
        ).values(
            'workerturnout__hours_worked__sum'
        )

        return self.annotate(
            worked_hours=Coalesce(
                Subquery(
                    worker_turnout_sq,
                    output_field=DecimalField(),
                ),
                ZERO_OO
            )
        )

    def with_confirmation(self):
        return self.annotate(
            confirmation=Subquery(
                DailyReconciliationConfirmation.objects.filter(
                    reconciliation=OuterRef('pk')
                ).annotate(
                    data=JSONObject(
                        timestamp='timestamp',
                        author_email='author__email',
                    )
                ).values(
                    'data'
                ),
            )
        )

    def with_request_count(self, paid_only=False):
        delivery_request_sq = DeliveryRequest.objects.filter(
            date=OuterRef('date'),
            location=OuterRef('location')
        )
        if paid_only:
            delivery_request_sq = delivery_request_sq.filter(
                status__in=DeliveryRequest.SUCCESS_STATUSES
            )
            annotation_name = 'requests_paid'
        else:
            annotation_name = 'requests_total'
        return self.annotate(**{
            annotation_name: Coalesce(
                Subquery(
                    delivery_request_sq.values(
                        'date',
                        'location'
                    ).annotate(
                        count=Count('pk')
                    ).values('count'),
                    output_field=IntegerField()
                ),
                0
            )
        })

    def with_worker_count(self):
        return self.annotate(
            worker_count=Coalesce(
                Subquery(
                    RequestWorker.objects.filter(
                        request__date=OuterRef('date'),
                        request__location=OuterRef('location'),
                        workerrejection__isnull=True,
                        requestworkerturnout__isnull=False,
                    ).values(
                        'request__date',
                        'request__location',
                    ).annotate(
                        count=Count('worker', distinct=True)
                    ).values('count'),
                    output_field=IntegerField()
                ),
                0
            )
        )

    def with_zone_name(self):
        return self.annotate(
            zone_name=Coalesce(
                Subquery(
                    LocationZoneGroup.objects.filter(
                        location=OuterRef('location')
                    ).order_by(
                        'zone_group'
                    ).values(
                        'zone_group__name'
                    )[:1],
                    output_field=CharField()
                ),
                'location__location_name'
            )
        )


class DailyReconciliation(models.Model):
    date = models.DateField(
        verbose_name='Дата',
    )

    location = models.ForeignKey(
        CustomerLocation,
        verbose_name='Объект (филиал)',
        on_delete=models.CASCADE
    )

    objects = DailyReconciliationQuerySet.as_manager()

    class Meta:
        unique_together = ['date', 'location']

    def __str__(self):
        return '{} {}/{}'.format(
            string_from_date(self.date),
            self.location.customer_id.cust_name,
            self.location.location_name
        )


class DailyReconciliationConfirmation(models.Model):
    timestamp = models.DateTimeField(
        verbose_name='Время подтверждения',
        default=timezone.now
    )
    author = models.ForeignKey(
        User,
        verbose_name='Автор',
        on_delete=models.PROTECT
    )

    reconciliation = models.OneToOneField(
        DailyReconciliation,
        verbose_name='Сверка',
        on_delete=models.PROTECT # Todo: ?
    )

    def __str__(self):
        return str(self.reconciliation)


def daily_reconciliation_message_upload_location(instance, filename):
    return 'daily_recon_email_attachments/{}/{}/{}'.format(
        instance.reconciliation.location_id,
        instance.reconciliation.date.isoformat(),
        filename
    )


class DailyReconciliationNotificationQuerySet(models.QuerySet):
    def with_is_confirmed(self):
        return self.annotate(
            is_confirmed=Exists(
                DailyReconciliationConfirmation.objects.filter(
                    reconciliation=OuterRef('reconciliation')
                )
            )
        )


class DailyReconciliationNotification(models.Model):
    timestamp = models.DateTimeField(
        default=timezone.now
    )
    author = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='sent_notifications'
    )

    reconciliation = models.ForeignKey(
        DailyReconciliation,
        verbose_name='Сверка',
        on_delete=models.PROTECT
    )
    hours = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        validators=[
            MinValueValidator(ZERO_OO)
        ]
    )
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[
            MinValueValidator(ZERO_OO)
        ]
    )
    is_ok = models.BooleanField()
    recipient_email = models.EmailField()
    recipient = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='received_notifications',
    )
    confirmation_key = models.UUIDField(
        null=True
    )
    attachment = models.FileField(
        max_length=255,
        upload_to=daily_reconciliation_message_upload_location
    )

    objects = DailyReconciliationNotificationQuerySet.as_manager()

    def __str__(self):
        return '{} {} {} ({})'.format(
            self.reconciliation,
            self.author.username,
            self.recipient.username,
            self.recipient_email
        )


# Mobile App part

class DeliveryWorkerFCMToken(models.Model):
    timestamp = models.DateTimeField(
        verbose_name='Время обновления',
        default=timezone.now
    )

    user = models.ForeignKey(
        User,
        verbose_name='Пользователь',
        on_delete=models.PROTECT,
    )
    app_id = models.TextField(
        verbose_name='Идентификатор установки',
    )
    token = models.TextField(
        verbose_name='Токен',
    )

    def __str__(self):
        return '{}: {} {}'.format(
            self.timestamp.strftime('%d.%m.%Y %H:%M:%S'),
            self.user,
            self.token
        )


class MobileAppStatus(models.Model):
    timestamp = models.DateTimeField(
        verbose_name='Время',
        default=timezone.now
    )

    user = models.ForeignKey(
        User,
        verbose_name='Пользователь',
        on_delete=models.PROTECT,
        db_index=False,
    )
    app_id = models.TextField(
        verbose_name='Идентификатор установки',
        blank=True,
        null=True
    )
    version_code = models.IntegerField(
        verbose_name='Код версии'
    )
    device_manufacturer = models.TextField(
        verbose_name='Производитель смартфона'
    )
    device_model = models.TextField(
        verbose_name='Модель смартфона'
    )
    location = models.OneToOneField(
        Location,
        null=True,
        default=None,
        on_delete=models.PROTECT
    )

    class Meta:
        indexes = [
            models.Index(
                fields=['user', 'timestamp'],
                name='mobileappstatus_user_ts_index',
            ),
        ]

    def __str__(self):
        return str(self.user)


class LastLocation(models.Model):
    worker = models.OneToOneField(
        Worker,
        on_delete=models.PROTECT
    )
    location = models.OneToOneField(
        Location,
        on_delete=models.PROTECT
    )


class OnlineStatusMark(models.Model):
    timestamp = models.DateTimeField(
        verbose_name='Время',
        default=timezone.now
    )
    author = models.ForeignKey(
        User,
        verbose_name='Автор',
        on_delete=models.PROTECT,
        related_name='online_marks_set',
    )

    user = models.ForeignKey(
        User,
        verbose_name='Пользователь',
        on_delete=models.PROTECT,
    )

    online = models.BooleanField(
        verbose_name='На линии',
    )

    def __str__(self):
        return f'{self.user} {self.timestamp} {self.online}'


class OnlineSignup(models.Model):
    date = models.DateField(
        verbose_name='Дата',
        default=timezone.localdate,
    )
    worker = models.ForeignKey(
        Worker,
        on_delete=models.PROTECT,
        verbose_name='Работник',
        db_index=False,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['worker', 'date'],
                name='online_signup_unique_worker_date',
            ),
        ]


# GT Customer

class DeliveryCustomerLegalEntity(models.Model):
    timestamp = models.DateTimeField(
        verbose_name='Время заполнения',
        default=timezone.now
    )

    customer = models.ForeignKey(
        Customer,
        verbose_name='Клиент',
        on_delete=models.PROTECT
    )

    is_legal_entity = models.BooleanField(
        verbose_name='Является ли организация юридическим лицом (False, если ИП)',
        blank=True,
        null=True
    )
    full_name = models.TextField(
        verbose_name='Полное наименование организации/ИП',
        blank=True,
        null=True
    )
    ceo = models.TextField(
        verbose_name='Генеральный директор',
        blank=True,
        null=True
    )
    email = models.TextField(
        verbose_name='Электронная почта',
        blank=True,
        null=True
    )
    phone = models.TextField(
        verbose_name='Телефон',
        blank=True,
        null=True
    )
    legal_address = models.TextField(
        verbose_name='Юридический адрес',
        blank=True,
        null=True
    )
    mail_address = models.TextField(
        verbose_name='Почтовый адрес',
        blank=True,
        null=True
    )
    tax_number = models.CharField(
        verbose_name='Идентификационный номер налогоплательщика (ИНН)',
        max_length=20,
        blank=True,
        null=True
    )
    reason_code = models.CharField(
        verbose_name='Код причины постановки на учет (КПП)',
        max_length=20,
        blank=True,
        null=True
    )
    bank_name = models.TextField(
        verbose_name='Наименование банка',
        blank=True,
        null=True
    )
    bank_identification_code = models.TextField(
        verbose_name='БИК',
        blank=True,
        null=True
    )
    bank_account = models.TextField(
        verbose_name='Расчетный счет',
        blank=True,
        null=True
    )
    correspondent_account = models.TextField(
        verbose_name='Корреспондентский счет',
        blank=True,
        null=True
    )

    registration_confirmed = models.BooleanField(
        verbose_name='Регистрация подтверждена',
        default=False
    )

    postpayment_allowed = models.BooleanField(
        verbose_name='Разрешена постоплата',
        default=False
    )

    def __str__(self):
        return '{} {}'.format(
            self.customer,
            self.full_name
        )


LEGAL_ENTITY_OPTIONAL_FIELDS = [
    'is_legal_entity',
    'full_name',
    'ceo',
    'email',
    'phone',
    'legal_address',
    'mail_address',
    'tax_number',
    'reason_code',
    'bank_name',
    'bank_identification_code',
    'bank_account',
    'correspondent_account',
]


def _delivery_invoices_upload_location(instance, filename):
    return 'delivery/invoices/{}/{}'.format(
        instance.id,
        filename
    )


class DeliveryInvoice(models.Model):
    timestamp = models.DateTimeField(
        verbose_name='Время импорта',
        default=timezone.now
    )
    author = models.ForeignKey(
        User,
        verbose_name='Автор',
        on_delete=models.PROTECT
    )
    customer = models.ForeignKey(
        Customer,
        verbose_name='Клиент',
        on_delete=models.PROTECT
    )

    amount = models.DecimalField(
        max_digits=30,
        decimal_places=2,
        verbose_name='Сумма',
        validators=[MinValueValidator(ZERO_OO)]
    )

    invoice_file = models.FileField(
        upload_to=_delivery_invoices_upload_location
    )

    def __str__(self):
        return '{} {} {}'.format(
            self.pk,
            self.customer.cust_name,
            string_from_date(self.timestamp.date())
        )


class ImportVisitTimestamp(models.Model):
    timestamp = models.DateTimeField(
        verbose_name='Время',
        default=timezone.now
    )

    customer = models.ForeignKey(
        Customer,
        verbose_name='Клиент',
        on_delete=models.PROTECT
    )


class ImportProcessedTimestamp(models.Model):
    timestamp = models.DateTimeField(
        verbose_name='Время',
        default=timezone.now
    )

    customer = models.ForeignKey(
        Customer,
        verbose_name='Клиент',
        on_delete=models.PROTECT
    )


# new models

class RequestWorkerQuerySet(models.QuerySet):

    def with_full_name(self):
        return self.annotate(
            full_name=PostgresConcatWS(
                Value(' '),
                F('worker__last_name'),
                F('worker__name'),
                NullIf(F('worker__patronymic'), Value(''))
            )
        )

    def filter_active(self):
        return self.exclude(
            request__status__in=DeliveryRequest.FINAL_STATUSES
        ).annotate(
            has_items=Exists(
                ItemWorker.objects.filter(
                    requestworker=OuterRef('pk'),
                    itemworkerrejection__isnull=True,
                )
            )
        ).filter(
            workerrejection__isnull=True,
            requestworkerturnout__isnull=True,
            has_items=True,
        )


class RequestWorker(models.Model):
    """
    Назначение грузчика на заявку
    """
    timestamp = models.DateTimeField(
        default=timezone.now
    )
    author = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
    )

    request = models.ForeignKey(
        DeliveryRequest,
        on_delete=models.PROTECT
    )
    worker = models.ForeignKey(
        Worker,
        on_delete=models.PROTECT
    )

    objects = RequestWorkerQuerySet.as_manager()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['request', 'worker'],
                name='unique_request_worker'
            ),
        ]

    def __str__(self):
        return f'{self.request.pk}/{self.worker}'


class WorkerConfirmation(models.Model):
    """
    Подтверждение заявки грузчиком
    """
    timestamp = models.DateTimeField(
        default=timezone.now
    )
    author = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
    )

    requestworker = models.OneToOneField(
        RequestWorker,
        on_delete=models.PROTECT
    )

    def __str__(self):
        return str(self.requestworker)


class WorkerRejection(models.Model):
    """
    Снятие грузчика с заявки
    """
    timestamp = models.DateTimeField(
        default=timezone.now
    )
    author = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
    )

    requestworker = models.OneToOneField(
        RequestWorker,
        on_delete=models.PROTECT
    )


class RequestWorkerTurnout(models.Model):
    """
    Связка грузчик-заявка-выход
    """
    timestamp = models.DateTimeField(
        default=timezone.now
    )

    requestworker = models.OneToOneField(
        RequestWorker,
        on_delete=models.PROTECT
    )
    workerturnout = models.OneToOneField(
        WorkerTurnout,
        on_delete=models.PROTECT
    )


class ItemWorkerQuerySet(models.QuerySet):

    @staticmethod
    def _get_photo_annotation_for_worker(model):
        # model is one of ItemWorkerStart, ItemWorkerFinish
        return Coalesce(
            Subquery(
                Photo.objects.filter(
                    content_type=ContentType.objects.get_for_model(model),
                    object_id=OuterRef(model._meta.model_name)
                ).annotate(
                    photo_fields=JSONObject(
                        id='id',
                        rejection_comment='photorejectioncomment__rejection_comment',
                    )
                ).order_by(
                ).values(
                    'object_id'
                ).annotate(
                    photos_list=ArrayAgg('photo_fields')
                ).values(
                    'photos_list'
                ),
                output_field=ArrayField(JSONField())
            ),
            []
        )

    def with_status(self):
        return self.annotate(
            has_valid_selfie=Exists(
                Photo.objects.filter(
                    content_type=ContentType.objects.get_for_model(ItemWorkerStart),
                    object_id=OuterRef('itemworkerstart'),
                    photorejectioncomment__isnull=True,
                )
            ),
        ).annotate(
            status=Case(
                When(
                    requestworker__workerrejection__isnull=False,
                    then=Value(ItemWorker.NOT_ASSIGNED),
                ),
                When(
                    itemworkerrejection__reason=ItemWorkerRejection.FAILURE,
                    then=Value(ItemWorker.FAILURE),
                ),
                When(
                    itemworkerrejection__reason=ItemWorkerRejection.DEFECT,
                    then=Value(ItemWorker.DEFECT),
                ),
                When(
                    itemworkerrejection__reason=ItemWorkerRejection.CANCELLED,
                    then=Value(ItemWorker.CANCELLED),
                ),
                When(
                    itemworkerfinish__itemworkerfinishconfirmation__isnull=False,
                    itemworkerfinish__photo__isnull=False,
                    itemworkerstart__itemworkerstartconfirmation__isnull=False,
                    then=Value(ItemWorker.COMPLETE)
                ),
                When(
                    itemworkerfinish__photo__isnull=False,
                    itemworkerstart__itemworkerstartconfirmation__isnull=False,
                    then=Value(ItemWorker.HAS_CHEQUE),
                ),
                When(
                    itemworkerfinish__isnull=False,
                    itemworkerstart__itemworkerstartconfirmation__isnull=False,
                    then=Value(ItemWorker.REJECTED_CHEQUE)
                ),
                When(
                    itemworkerstart__itemworkerstartconfirmation__isnull=False,
                    then=Value(ItemWorker.ARRIVED)
                ),
                When(
                    (
                        Q(itemworkerstart__itemworkerdiscrepancycheck__is_ok=False) |
                        Q(
                            itemworkerstart__itemworkerdiscrepancycheck__is_ok__isnull=True,
                            itemworkerstart__is_suspicious=True,
                        )
                    ) &
                    Q(has_valid_selfie=True),
                    then=Value(ItemWorker.ARRIVAL_SUSPICIOUS),
                ),
                When(
                    has_valid_selfie=True,
                    then=Value(ItemWorker.ARRIVAL_CHECKING)
                ),
                When(
                    itemworkerstart__isnull=False,
                    then=Value(ItemWorker.ARRIVAL_REJECTED)
                ),
                When(
                    requestworker__workerconfirmation__isnull=False,
                    then=Value(ItemWorker.CONFIRMED)
                ),
                default=Value(ItemWorker.NEW),
                output_field=IntegerField()
            )
        )

    def with_photos(self):
        return self.annotate(
            start_photos=self._get_photo_annotation_for_worker(ItemWorkerStart),
            finish_photos=self._get_photo_annotation_for_worker(ItemWorkerFinish),
        )


class ItemWorker(models.Model):
    """
    Назначение грузчика на адрес
    """
    COMPLETE = 8
    HAS_CHEQUE = 7
    REJECTED_CHEQUE = 6
    ARRIVED = 5
    ARRIVAL_CHECKING = 4
    ARRIVAL_SUSPICIOUS = 3
    ARRIVAL_REJECTED = 1
    CONFIRMED = 2
    NEW = 0
    CANCELLED = -1
    DEFECT = -2
    FAILURE = -3
    NOT_ASSIGNED = -4

    timestamp = models.DateTimeField(
        default=timezone.now
    )
    author = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
    )

    item = models.ForeignKey(
        DeliveryItem,
        on_delete=models.PROTECT
    )
    requestworker = models.ForeignKey(
        RequestWorker,
        on_delete=models.PROTECT
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['item', 'requestworker'],
                name='unique_item_requestworker'
            ),
        ]

    objects = ItemWorkerQuerySet.as_manager()

    def __str__(self):
        rw = self.requestworker
        return f'{rw.request.pk}/{self.item.pk}/{rw.worker}'


class ItemWorkerRejection(models.Model):
    """
    Выбраковка назначения на адрес
    """
    DEFECT = 'defect'
    FAILURE = 'failure'
    CANCELLED = 'cancelled'

    REASON_CHOICES = [
        (DEFECT, 'Брак'),
        (FAILURE, 'Срыв'),
        (CANCELLED, 'Отмена'),
    ]

    timestamp = models.DateTimeField(
        default=timezone.now
    )
    author = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
    )

    itemworker = models.OneToOneField(
        ItemWorker,
        on_delete=models.PROTECT
    )
    reason = models.CharField(
        max_length=9,
        choices=REASON_CHOICES
    )


class ItemWorkerStart(models.Model):
    """
    Фотоподтверждение прибытия на адрес (селфи)
    """
    timestamp = models.DateTimeField(
        default=timezone.now
    )
    author = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
    )

    itemworker = models.OneToOneField(
        ItemWorker,
        on_delete=models.PROTECT,
    )
    location = models.OneToOneField(
        Location,
        null=True,
        default=None,
        on_delete=models.PROTECT
    )
    is_suspicious = models.BooleanField(
        default=True
    )

    def __str__(self):
        return str(self.itemworker)


class ItemWorkerStartConfirmation(models.Model):
    """
    Подтверждение селфи
    """
    timestamp = models.DateTimeField(
        default=timezone.now
    )
    author = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
    )

    itemworkerstart = models.OneToOneField(
        ItemWorkerStart,
        on_delete=models.PROTECT
    )


class ItemWorkerFinish(models.Model):
    """
    Накладная
    """
    timestamp = models.DateTimeField(
        default=timezone.now
    )
    author = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
    )

    itemworker = models.OneToOneField(
        ItemWorker,
        on_delete=models.PROTECT,
    )
    location = models.OneToOneField(
        Location,
        null=True,
        default=None,
        on_delete=models.PROTECT
    )
    photo = models.OneToOneField(
        Photo,
        verbose_name='Фото',
        null=True,
        default=None,
        on_delete=models.PROTECT
    )


class ItemWorkerFinishConfirmation(models.Model):
    """
    Подтверждение накладной
    """
    timestamp = models.DateTimeField(
        default=timezone.now
    )
    author = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
    )

    itemworkerfinish = models.OneToOneField(
        ItemWorkerFinish,
        on_delete=models.PROTECT
    )


class ItemWorkerDiscrepancyCheck(models.Model):
    timestamp = models.DateTimeField(
        verbose_name='Время проверки',
        default=timezone.now,
    )
    author = models.ForeignKey(
        User,
        verbose_name='Автор',
        on_delete=models.PROTECT
    )
    itemworkerstart = models.OneToOneField(
        ItemWorkerStart,
        verbose_name='Прибытие',
        on_delete=models.PROTECT
    )
    is_ok = models.BooleanField(
        null=True,
        default=None,
        db_index=True,
    )
    comment = models.TextField(
        verbose_name='Комментарий',
        default=''
    )


class DeliveryFirstAddress(models.Model):
    item = models.OneToOneField(DeliveryItem, on_delete=models.CASCADE)
