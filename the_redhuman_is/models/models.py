# -*- coding: utf-8 -*-
from datetime import (
    date,
    datetime,
    time,
    timedelta,
)

from django.apps import apps
from django.contrib.auth.models import User
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import (
    ObjectDoesNotExist,
    ValidationError,
)
from django.db import (
    models,
    transaction,
)
from django.db.models import (
    Case,
    DateField,
    DecimalField,
    Exists,
    ExpressionWrapper,
    F,
    OuterRef,
    ProtectedError,
    Q,
    QuerySet,
    Subquery,
    Sum,
    Value,
    When,
)
from django.db.models.functions import (
    Coalesce,
    Greatest,
)
from django.db.models.signals import (
    post_save,
    pre_delete,
    post_delete,
)
from django.dispatch import receiver
from django.utils import timezone

import finance
from finance import model_utils

from finance.model_utils import (
    ensure_account,
    ensure_accounts_chain,
    get_root_account,
)
from utils.date_time import (
    as_default_timezone,
    string_from_date,
)
from utils.numbers import ZERO_OO
from utils.phone import (
    is_it_russian_phone,
    normalized_phone,
)

from the_redhuman_is.models.contract import Contract
from the_redhuman_is.models.photo import (
    Photo,
    get_photos,
)
from the_redhuman_is.models.worker import (
    Country,
    Position,
    Worker,
)
from the_redhuman_is.models.legal_entity import LegalEntity


class CustomerQuerySet(QuerySet):

    def with_new_turnouts_amount(self):
        return self.annotate(
            new_turnouts_amount=Coalesce(
                Subquery(
                    CustomerLocation.objects.order_by(
                    ).filter(
                        customer_id=OuterRef('pk')
                    ).with_new_turnouts_amount(
                    ).values(
                        'customer_id'
                    ).annotate(
                        amount_sum=Sum('new_turnouts_amount')
                    ).values(
                        'amount_sum'
                    ),
                    output_field=DecimalField()
                ),
                ZERO_OO
            )
        )

    def with_turnouts_amount(self, field_name, filter_q):
        reconciliation_sq = apps.get_model('the_redhuman_is', 'Reconciliation').objects.filter(
            Q(location=OuterRef('turnout__timesheet__cust_location')) |
            Q(location__isnull=True),
            first_day__lte=OuterRef('turnout__timesheet__sheet_date'),
            last_day__gte=OuterRef('turnout__timesheet__sheet_date'),
            customer=OuterRef('turnout__timesheet__customer')
        ).filter(
            filter_q
        ).only('pk')

        return self.annotate(
            **{
                field_name: Coalesce(
                    Subquery(
                        apps.get_model('the_redhuman_is', 'TurnoutCustomerOperation').objects.filter(
                            turnout__timesheet__customer=OuterRef('pk'),
                        ).annotate(
                            has_reconciliation=Exists(
                                reconciliation_sq
                            )
                        ).filter(
                            has_reconciliation=True
                        ).values(
                            'turnout__timesheet__customer'
                        ).annotate(
                            amount_sum=Sum('operation__amount')
                        ).values(
                            'amount_sum'
                        ),
                        output_field=DecimalField()
                    ),
                    ZERO_OO
                )
            }
        )

    def with_all_closed_before(self):
        return self.annotate(
            last_closed_date=Subquery(
                apps.get_model('the_redhuman_is', 'Reconciliation').objects.filter(
                    customer=OuterRef('pk'),
                    is_closed=True
                ).order_by(
                    '-last_day'
                ).values(
                    'last_day'
                )[:1],
                output_field=DateField()
            ),
            first_unclosed_date=Subquery(
                apps.get_model('the_redhuman_is', 'Reconciliation').objects.filter(
                    customer=OuterRef('pk'),
                    is_closed=False
                ).order_by(
                    'first_day'
                ).values(
                    'first_day'
                )[:1],
                output_field=DateField()
            ),
            unclosed_recon_exists=Exists(
                apps.get_model('the_redhuman_is', 'Reconciliation').objects.filter(
                    customer=OuterRef('pk'),
                    is_closed=False
                )
            )
        ).annotate(
            all_closed_before=Case(
                When(unclosed_recon_exists=False, then=F('last_closed_date')),
                default=ExpressionWrapper(
                    F('first_unclosed_date') + timedelta(days=1),
                    output_field=DateField()
                ),
            )
        )

    def with_no_recons_after(self):
        return self.annotate(
            no_recons_after=ExpressionWrapper(
                Subquery(
                    apps.get_model('the_redhuman_is', 'Reconciliation').objects.filter(
                        customer=OuterRef('pk'),
                    ).order_by(
                        '-last_day'
                    ).values(
                        'last_day'
                    )[:1],
                    output_field=DateField()
                ) + timedelta(days=1),
                output_field=DateField()
            )
        )


class Customer(models.Model):
    cust_name = models.CharField(
        'Название',
        max_length=100
    )

    is_actual = models.BooleanField(
        default=True,
        verbose_name='Актуальный'
    )

    # Todo: remove
    debts_first_day = models.DateField(
        default=date(year=2000, month=1, day=1),
        verbose_name='Первый день, не закрытый актами'
    )

    objects = CustomerQuerySet.as_manager()

    def get_last_comment(self):
        return CustComments.objects.filter(customer=self).latest('date')

    def get_main_contact(self):
        return CustomerRepr.objects.get(customer_id=self, main=True)

    def days_after_last_order(self):
        last_order = CustomerOrder.objects.filter(customer=self).latest(
            'bid_date_time')
        delta = date.today() - last_order.bid_date_time
        return delta.days

    def days_after_last_comment(self):
        today = timezone.now()
        last_comment = CustComments.objects.filter(customer=self).latest('date')
        delta = today - last_comment.date
        return delta.days

    def total_shortfall(self):
        timesheets = TimeSheet.objects.filter(customer=self)
        total_shortfall = 0
        for timesheet in timesheets:
            get_shortfall = timesheet.get_shortfall()
            if get_shortfall is not None and get_shortfall > 0:
                total_shortfall += get_shortfall
        return total_shortfall

    def __str__(self):
        if self.cust_name:
            return self.cust_name
        return 'Без названия'

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

        accounts = getattr(self, 'customer_accounts', None)
        if accounts:
            accounts.save()


class CustomerLegalEntity(models.Model):
    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        verbose_name='Клиент',
        related_name='legal_entities'
    )
    legal_entity = models.ForeignKey(
        LegalEntity,
        on_delete=models.CASCADE,
        verbose_name='Юрлицо',
        related_name='customers'
    )

    first_day = models.DateField(
        verbose_name='Первый день периода'
    )
    last_day = models.DateField(
        verbose_name='Последний день периода',
        blank=True,
        null=True
    )

    def __str__(self):
        description = '{} - {}, c {}'.format(
            self.customer,
            self.legal_entity,
            string_from_date(self.first_day)
        )
        if self.last_day:
            description += ' по {}'.format(
                string_from_date(self.last_day)
            )
        return description


def customer_legal_entities(customer):
    return CustomerLegalEntity.objects.filter(customer=customer).order_by('first_day')


def intersected_legal_entities(customer, first_day, last_day):
    entities = customer_legal_entities(
        customer
    ).exclude(
        Q(last_day__lt=first_day)
    )
    if last_day:
        entities = entities.exclude(
            first_day__gt=last_day
        )

    return entities


@transaction.atomic
def add_customer_legal_entity(customer, legal_entity, first_day, last_day):
    intersected = intersected_legal_entities(
        customer,
        first_day,
        last_day
    ).exclude(
        last_day__isnull=True
    )
    if intersected.exists():
        raise Exception(
            'Попытка добавить юрлицо <{}> к клиенту <{}>: интервал с {} по {} пересекается ' \
            'с интервалом <{}>'.format(
                legal_entity,
                customer,
                string_from_date(first_day),
                string_from_date(last_day),
                intersected.first()
            )
        )

    entities = customer_legal_entities(customer)
    if entities.exists():
        last = entities.last()
        if not last.last_day:
            last.last_day = first_day - timedelta(days=1)
            last.save()

    return CustomerLegalEntity.objects.create(
        customer=customer,
        legal_entity=legal_entity,
        first_day=first_day,
        last_day=last_day
    )


class CustComments(models.Model):
    customer = models.ForeignKey(
        'Customer',
        on_delete=models.CASCADE
    )
    date = models.DateTimeField(
        'Дата создания',
        blank=True,
        null=True
    )
    author = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        verbose_name='Автор',
        null=True,
        blank=True,
    )
    text = models.TextField(
        max_length=100,
        verbose_name='Комментарий',
        blank=True,
        null=True,
    )
    task_date = models.DateTimeField(
        'Дата следующего контакта',
        blank=True,
        null=True
    )
    task_text = models.TextField(
        verbose_name='Задача',
        max_length=100,
        blank=True,
        null=True,
    )

    class Meta:
        ordering = ('-date',)

    def __str__(self):
        customer = Customer.objects.get(custcomments__id=self.pk)
        return '{0} {1} {2}'.format(self.author, customer, self.date)


class CustomerLocationQuerySet(models.QuerySet):

    def with_first_timesheet_date(self):
        return self.annotate(
            first_timesheet_date=Subquery(
                TimeSheet.objects.filter(
                    cust_location=OuterRef('pk')
                ).order_by(
                    'sheet_date'
                ).values('sheet_date')[:1],
                output_field=DateField()
            )
        )

    def with_last_reconciliation_date(self):
        """
        Date of last reconciliation is the greater of last days
        of the latest customer-wide reconciliation, IF earlier timesheets exist,
        and the latest location-specific reconciliation.
        """
        from .reconciliation import Reconciliation
        return self.with_first_timesheet_date(
        ).annotate(
            last_customer_reconciliation_date=Subquery(
                # only consider dates after the first active date
                Reconciliation.objects.filter(
                    location__isnull=True,
                    customer=OuterRef('customer_id'),
                    last_day__gte=OuterRef('first_timesheet_date'),
                ).order_by(
                    '-last_day'
                ).values('last_day')[:1],
                output_field=DateField()
            )
        ).annotate(
            last_location_reconciliation_date=Subquery(
                Reconciliation.objects.filter(
                    location=OuterRef('pk'),
                    customer=OuterRef('customer_id'),
                ).order_by(
                    '-last_day'
                ).values('last_day')[:1],
                output_field=DateField()
            )
        ).annotate(
            last_reconciliation_date=Greatest(
                F('last_customer_reconciliation_date'),
                F('last_location_reconciliation_date'),
                output_field=DateField()
            )
        )

    def with_new_turnouts_amount(self):
        TurnoutCustomerOperation = apps.get_model('the_redhuman_is', 'TurnoutCustomerOperation')
        return self.with_last_reconciliation_date(
        ).annotate(
            new_turnouts_amount=Coalesce(
                Subquery(
                    TurnoutCustomerOperation.objects.order_by(
                    ).filter(
                        turnout__timesheet__cust_location=OuterRef('pk'),
                        turnout__timesheet__sheet_date__gt=Coalesce(
                            OuterRef('last_reconciliation_date'),
                            Value(date(1970, 1, 1))
                        )
                    ).values(
                        'turnout__timesheet__cust_location'
                    ).annotate(
                        amount_sum=Sum('operation__amount')
                    ).values(
                        'amount_sum'
                    ),
                    output_field=DecimalField()
                ),
                ZERO_OO
            )
        )


class CustomerLocation(models.Model):
    customer_id = models.ForeignKey(Customer, on_delete=models.CASCADE)
    location_name = models.CharField(
        'Название',
        max_length=100
    )
    location_adress = models.TextField(
        'Адрес',
        blank=True,
        null=True
    )
    location_how_to_get = models.TextField(
        'Как добраться',
        blank=True,
        null=True
    )
    is_actual = models.BooleanField(
        default=True,
        verbose_name='Актуальный'
    )

    class Meta:
        ordering = ('-id',)

    def __str__(self):
        return '{} - {} - {}'.format(
            self.pk,
            self.customer_id,
            self.location_name
        )

    def full_name(self):
        return '{} - {}'.format(self.customer_id, self.location_name)

    objects = CustomerLocationQuerySet.as_manager()


class CustomerRepr(models.Model):
    customer_id = models.ForeignKey(
        Customer,
        on_delete=models.PROTECT
    )
    repr_last_name = models.CharField(
        'Фамилия',
        max_length=100,
        blank=True,
        null=True
    )
    repr_name = models.CharField(
        'Имя',
        max_length=100,
        blank=True,
        null=True
    )
    repr_patronymic = models.CharField(
        'Отчество',
        max_length=100,
        blank=True,
        null=True
    )
    position = models.CharField(
        'Должность',
        max_length=100,
        blank=True,
        null=True
    )
    tel_number = models.TextField(
        'Номер телефона',
        blank=True,
        null=True
    )
    email = models.EmailField(
        verbose_name='Почта',
        blank=True,
        null=True
    )
    main = models.BooleanField(
        'Основной',
        default=False
    )

    class Meta:
        ordering = ('repr_last_name', 'repr_name', 'repr_patronymic')

    def save(self, *args, **kwargs):
        if self.tel_number:
            self.tel_number = normalized_phone(self.tel_number)
        super().save(*args, **kwargs)

    def __str__(self):
        return '{0} {1} {2}'.format(
            self.repr_last_name,
            self.repr_name,
            self.repr_patronymic
        )


def timesheet_upload_location(instance, filename):
    # path = 'timesheets'
    # sheet_date = instance.sheet_date.strftime('%Y-%m-%d')
    # return os.path.join(path, sheet_date, '%s' % instance.cust_location, filename)
    return 'timesheets/%s/%s/%s' % (
        instance.sheet_date, instance.cust_location, filename)


_WARNING_INTERVAL = timedelta(seconds=30 * 60)


class CustomerOrder(models.Model):
    input_date = models.DateField(
        verbose_name='Дата занесения',
        default=timezone.now,
        blank=True,
        null=True
    )
    bid_date_time = models.DateField(
        verbose_name='Дата и время подачи',
        default=None,
        blank=True,
        null=True
    )
    # Todo: merge on_date & on_time?
    on_date = models.DateField(
        verbose_name='Дата выхода',
        default=None,
        blank=True,
        null=True
    )
    on_time = models.TimeField(
        verbose_name='Время выхода',
        default=None,
        blank=True,
        null=True,
    )
    bid_turn = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        choices=(
            ('День', 'День'),
            ('Ночь', 'Ночь'),
        ),
        default='Ночь',
        verbose_name='Смена'
    )
    customer = models.ForeignKey(
        Customer,
        on_delete=models.PROTECT,
        blank=True,
        null=True
    )
    cust_location = models.ForeignKey(
        CustomerLocation,
        on_delete=models.PROTECT,
        blank=True,
        null=True
    )
    timesheet = models.OneToOneField(
        'TimeSheet',
        blank=True,
        null=True,
        on_delete=models.PROTECT
    )
    number_of_workers = models.IntegerField(
        'Количество рабочих',
        default=0
    )

    class Meta:
        ordering = ('-on_date', 'bid_turn')

    def __str__(self):
        return '{}-{}-{}-{}-{}'.format(
            self.pk,
            self.on_date,
            self.on_time,
            self.bid_turn,
            self.cust_location
        )

    def workshift_start(self):
        return as_default_timezone(
            datetime.combine(
                self.on_date,
                self.on_time
            )
        )

    def time_before_workshift(self):
        return self.workshift_start() - timezone.now()

    def description(self):
        return '{}/{}/{}/{}'.format(
            self.customer,
            self.cust_location,
            self.bid_turn,
            self.workshift_start().strftime('%d.%m %H:%M'),
        )


class TimeSheet(models.Model):
    MAX_CLOSING_DELAY = timedelta(seconds=24 * 60 * 60)

    sheet_date = models.DateField('Дата', blank=True, null=True)
    sheet_turn = models.CharField(
        verbose_name='Смена',
        max_length=100,
        default='Новый',
        choices=(
            ('День', 'День'),
            ('Ночь', 'Ночь'),
        )
    )
    customer = models.ForeignKey(
        Customer,
        on_delete=models.PROTECT,
        related_name='timesheets'
    )
    cust_location = models.ForeignKey(
        CustomerLocation,
        on_delete=models.PROTECT
    )
    foreman = models.ForeignKey(
        Worker,
        on_delete=models.PROTECT
    )
    customer_repr = models.ForeignKey(
        CustomerRepr,
        on_delete=models.PROTECT
    )
    # Todo: where is it used?
    turnouts_number = models.IntegerField(
        'Количество рабочих',
        blank=True,
        null=True
    )
    is_executed = models.BooleanField(default=False, verbose_name='Закрыт')

    image = models.ImageField(
        upload_to=timesheet_upload_location,
        null=True,
        blank=True,
        width_field='width_field',
        height_field='height_field',
        verbose_name='Перед сменой')
    image2 = models.ImageField(
        upload_to=timesheet_upload_location,
        null=True,
        blank=True,
        width_field='width_field',
        height_field='height_field',
        verbose_name='Перед сменой')

    image3 = models.ImageField(
        upload_to=timesheet_upload_location,
        null=True,
        blank=True,
        width_field='width_field',
        height_field='height_field',
        verbose_name='После смены')
    image4 = models.ImageField(
        upload_to=timesheet_upload_location,
        null=True,
        blank=True,
        width_field='width_field',
        height_field='height_field',
        verbose_name='После смены')
    height_field = models.IntegerField(default=0)
    width_field = models.IntegerField(default=0)

    class Meta:
        ordering = ('-sheet_date',)

    def __str__(self):
        return '{}-{}-{}'.format(
            self.pk,
            self.sheet_date,
            self.cust_location
        )

    def save(self, *args, **kwargs):
        from the_redhuman_is.services.reconciliations import assert_can_reconcile_turnout
        assert_can_reconcile_turnout(
            self.cust_location,
            self.customer,
            self.sheet_date,
            'табель'
        )
        super().save(*args, **kwargs)

    def get_shortfall(self):
        workers = self.customerorder.number_of_workers
        if workers is None:
            workers = 0
        shortfall = workers - WorkerTurnout.objects.filter(
            timesheet=self
        ).count()
        return shortfall

    def time_to_close(self):
        shift_finish_timepoint = self.customerorder.workshift_start() + TimeSheet.MAX_CLOSING_DELAY
        return shift_finish_timepoint - timezone.now()

    # returns (expired, timedelta)
    def creation_delay(self):
        if hasattr(self, 'creation_timepoint'):
            deadline = self.customerorder.workshift_start() + timedelta(hours=2)
            if self.creation_timepoint.timepoint > deadline:
                return (
                    True,
                    self.creation_timepoint.timepoint - deadline
                )
            else:
                return False, timedelta()

        else:
            return False, None

    # returns (expired, timedelta)
    def closing_delay(self):
        if hasattr(self, 'processing_timepoint'):
            # должно быть закрыто к следующему утру
            deadline = as_default_timezone(
                datetime.combine(
                    self.customerorder.on_date + timedelta(days=1),
                    time(hour=11, minute=0)
                )
            )
            if self.processing_timepoint.timepoint > deadline:
                return (
                    True,
                    self.processing_timepoint.timepoint - deadline
                )
            else:
                return False, timedelta()
        else:
            return False, None


class TimesheetCreationTimepoint(models.Model):
    timesheet = models.OneToOneField(
        TimeSheet,
        verbose_name='Табель',
        related_name='creation_timepoint',
        on_delete=models.CASCADE
    )
    timepoint = models.DateTimeField(
        default=timezone.now,
        verbose_name='Момент создания'
    )

    def __str__(self):
        return '{} {}'.format(
            self.timesheet,
            self.timepoint.strftime('%H:%M %d.%m.%Y')
        )


class TimesheetProcessingTimepoint(models.Model):
    timesheet = models.OneToOneField(
        TimeSheet,
        verbose_name='Табель',
        related_name='processing_timepoint',
        on_delete=models.CASCADE
    )
    timepoint = models.DateTimeField(
        default=timezone.now,
        verbose_name='Момент закрытия'
    )

    def __str__(self):
        return '{} {}'.format(
            self.timesheet,
            self.timepoint.strftime('%H:%M %d.%m.%Y')
        )


class CustomerOrderSoftNotification(models.Model):
    customer_order = models.ForeignKey(
        CustomerOrder,
        on_delete=models.CASCADE,
        related_name='soft_notification',
    )


class CustomerOrderHardNotification(models.Model):
    customer_order = models.ForeignKey(
        CustomerOrder,
        on_delete=models.CASCADE,
        related_name='hard_notification',
    )


class TimesheetSoftNotification(models.Model):
    timesheet = models.OneToOneField(
        TimeSheet,
        related_name='soft_notification',
        on_delete=models.CASCADE
    )


def _register_timesheet_creation(timesheet):
    photos = get_photos(timesheet)
    if photos or timesheet.image or timesheet.image2:
        creation_timepoint = TimesheetCreationTimepoint.objects.filter(
            timesheet=timesheet
        )
        if not creation_timepoint.exists():
            TimesheetCreationTimepoint.objects.create(timesheet=timesheet)


def _post_save_timesheet(sender, instance, created, *args, **kwargs):
    _register_timesheet_creation(instance)

    if instance.is_executed:
        processing_timepoint = TimesheetProcessingTimepoint.objects.filter(
            timesheet=instance
        )
        if not processing_timepoint.exists():
            TimesheetProcessingTimepoint.objects.create(timesheet=instance)


def _post_save_photo(sender, instance, created, *args, **kwargs):
    if instance.content_type == ContentType.objects.get_for_model(TimeSheet):
        timesheet = TimeSheet.objects.get(pk=instance.object_id)
        _register_timesheet_creation(timesheet)


def orders_for_soft_notification():
    orders_filter = CustomerOrder.objects.filter(
        timesheet__isnull=True,
        soft_notification__isnull=True
    )
    orders = []
    for order in orders_filter:
        if timedelta() < order.time_before_workshift() < _WARNING_INTERVAL:
            orders.append(order)
    return orders


def orders_for_hard_notification():
    orders_filter = CustomerOrder.objects.filter(
        timesheet__isnull=True,
        hard_notification__isnull=True
    )
    orders = []
    for order in orders_filter:
        if -order.time_before_workshift() > _WARNING_INTERVAL:
            orders.append(order)
    return orders


def timesheets_for_notification():
    timesheets_filter = TimeSheet.objects.filter(
        is_executed=False,
        soft_notification__isnull=True
    )
    SHIFT_LENGTH = timedelta(seconds=11.5 * 60 * 60)
    timesheets = []
    for timesheet in timesheets_filter:
        length = -timesheet.customerorder.time_before_workshift()
        if length > SHIFT_LENGTH:
            timesheets.append(timesheet)
    return timesheets


class NoWorkerPhoneException(Exception):
    pass


class WorkerTurnout(models.Model):
    timesheet = models.ForeignKey(
        TimeSheet,
        on_delete=models.PROTECT,
        verbose_name='Табель',
        related_name='worker_turnouts',
    )
    worker = models.ForeignKey(
        Worker,
        on_delete=models.PROTECT,
        verbose_name='Работник',
        related_name='worker_turnouts',
    )
    worker_code_name = models.CharField(
        'Кодовое имя работника',
        max_length=200,
        blank=True,
        null=True,
    )
    # Todo: not nullable
    contract = models.ForeignKey(
        Contract,
        on_delete=models.PROTECT,
        verbose_name='Договор',
        related_name='worker_turnouts',
        blank=True,
        null=True,
    )
    hours_worked = models.DecimalField(
        'Отработано часов',
        max_digits=6,
        decimal_places=2,
        blank=True, null=True
    )
    date = models.DateField(
        'Дата создания',
        auto_now_add=True
    )
    is_payed = models.BooleanField('Оплачен', default=False)

    # Todo: move performance to some other model?
    performance = models.DecimalField(
        'Выработка',
        max_digits=6,
        decimal_places=1,
        blank=True,
        null=True
    )

    class Meta:
        ordering = ('-id',)

    def __str__(self):
        return '№{0} - {1} - {2} - {3}'.format(
            self.pk, self.date, self.hours_worked, self.worker)

    def save(self, *args, **kwargs):
        from the_redhuman_is.services.reconciliations import assert_can_reconcile_turnout
        assert_can_reconcile_turnout(
            self.timesheet.cust_location,
            self.timesheet.customer,
            self.timesheet.sheet_date,
            'выход работника'
        )

        phone = normalized_phone(self.worker.tel_number, strict=True)
        if not is_it_russian_phone(phone):
            raise NoWorkerPhoneException(
                'Attempt to save turnout with worker without phone.'
            )

        super().save(*args, **kwargs)

    def is_first(self):
        turnouts_before = self.worker.worker_turnouts.filter(
            timesheet__sheet_date__lt=self.timesheet.sheet_date
        )
        return not turnouts_before

    # Todo: remove this
    def make_multiple_dict(self):
        assert False


# Todo: remove this
class Rko(models.Model):
    date = models.DateField(
        verbose_name='Дата',
        auto_now_add=True,
    )
    worker = models.ForeignKey(
        Worker,
        on_delete=models.CASCADE,
    )
    is_actual = models.BooleanField(
        verbose_name='Непроведенный',
        default=True
    )

    class Meta:
        ordering = ('-id',)

    def __str__(self):
        return '№{0} от {1} для {2}'.format(self.pk, self.date, self.worker)

    def make_dict(self):
        assert False


class Act(models.Model):
    date = models.DateField(
        verbose_name='Дата',
        auto_now_add=True
    )

    # Todo: not nullable
    turnout = models.ForeignKey(
        WorkerTurnout,
        on_delete=models.PROTECT,
        verbose_name='Выход для Акта',
        blank=True,
        null=True,
    )
    # Todo: not nullable
    rko = models.ForeignKey(
        Rko,
        on_delete=models.PROTECT,
        verbose_name='РКО',
        blank=True,
        null=True,
    )

    class Meta:
        ordering = ('-id',)

    def __str__(self):
        return '№{0} - {1} - Табель {2}'.format(
            self.pk,
            self.date,
            self.turnout
        )


# Todo: remove
class RecruitmentOrder(models.Model):
    date = models.DateField(
        verbose_name='Дата создания',
        auto_now_add=True)
    customer_order = models.ForeignKey(
        CustomerOrder,
        on_delete=models.CASCADE,
        related_name='order'
    )
    is_actual = models.BooleanField(
        verbose_name='Актуальная',
        default=True
    )

    def __str__(self):
        return '{0} > {1} > Заявка: {2}'.format(
            self.pk,
            self.date,
            self.customer_order
        )


# Todo: remove
class WorkersForOrder(models.Model):
    order = models.ForeignKey(
        RecruitmentOrder,
        on_delete=models.CASCADE,
        blank=True, null=True
    )
    worker = models.ForeignKey(
        Worker,
        on_delete=models.CASCADE,
        blank=True,
        null=True
    )
    author = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        verbose_name='Автор',
        null=True,
        blank=True,
    )

    def __str__(self):
        return '{0} > {1}'.format(self.pk, self.worker)


class CustomerAccount(models.Model):
    customer = models.ForeignKey(
        Customer,
        on_delete=models.PROTECT
    )
    user = models.OneToOneField(
        User,
        on_delete=models.PROTECT,
    )

    def __str__(self):
        return f'{self.customer} ({self.user})'


class LocationAccount(models.Model):
    location = models.ForeignKey(
        CustomerLocation,
        on_delete=models.PROTECT,
    )
    user = models.OneToOneField(
        User,
        on_delete=models.PROTECT,
    )

    def __str__(self):
        return f'{self.location} ({self.user})'


class WorkerOperatingAccount(models.Model):
    worker = models.OneToOneField(
        Worker,
        on_delete=models.CASCADE,
        verbose_name='Работник',
        related_name='worker_account'
    )
    account = models.OneToOneField(
        finance.models.Account,
        on_delete=models.PROTECT,
        verbose_name='Расчетный счет',
        related_name='worker_account'
    )

    def __str__(self):
        return str(self.account)


def create_worker_operating_account(worker):
    account_70 = model_utils.get_account('70')
    account = ensure_account(
        name=str(worker),
        parent=account_70
    )
    WorkerOperatingAccount.objects.create(
        worker=worker,
        account=account
    )


@receiver(post_delete, sender=WorkerOperatingAccount)
def delete_worker_account(sender, instance, **kwargs):
    if instance is not None:
        try:
            instance.account.delete()
        except ProtectedError:
            pass


class CustomerOperatingAccounts(models.Model):
    customer = models.OneToOneField(
        Customer,
        on_delete=models.CASCADE,
        verbose_name='Клиент',
        related_name='customer_accounts'
    )

    account_10_root = models.ForeignKey(
        finance.models.Account,
        on_delete=models.PROTECT,
        verbose_name='10 Корень',
        related_name='account_10_root_accounts'
    )
    account_20_root = models.ForeignKey(
        finance.models.Account,
        on_delete=models.PROTECT,
        verbose_name='20 Корень',
        related_name='account_20_root_accounts'
    )
    account_20_other = models.ForeignKey(
        finance.models.Account,
        on_delete=models.PROTECT,
        verbose_name='20 Прочее',
        related_name='account_20_other_accounts'
    )
    account_20_foreman = models.ForeignKey(
        finance.models.Account,
        on_delete=models.PROTECT,
        verbose_name='20 Бригадиры',
        related_name='account_20_foremans',
    )
    account_62_root = models.ForeignKey(
        finance.models.Account,
        on_delete=models.PROTECT,
        verbose_name='62 Корень',
        related_name='account_62_root_accounts'
    )
    account_76_sales = models.ForeignKey(
        finance.models.Account,
        on_delete=models.PROTECT,
        verbose_name='76 Непроактированные продажи',
        related_name='account_76_sales_accounts'
    )
    account_76_debts = models.ForeignKey(
        finance.models.Account,
        on_delete=models.PROTECT,
        verbose_name='76 Непроактированные долги',
        related_name='account_76_debts_accounts'
    )
    account_76_fines = models.ForeignKey(
        finance.models.Account,
        on_delete=models.PROTECT,
        verbose_name='76 Штрафы',
        related_name='account_76_fines_accounts'
    )
    account_90_1_root = models.ForeignKey(
        finance.models.Account,
        on_delete=models.PROTECT,
        verbose_name='90 1 Корень',
        related_name='account_90_1_root_accounts'
    )
    account_90_1_disciplinary_deductions = models.ForeignKey(
        finance.models.Account,
        on_delete=models.PROTECT,
        verbose_name='90 1 Вычеты дисциплинарные',
        related_name='account_90_1_disciplinary_deduction_accounts',
    )
    account_90_1_fine_based_deductions = models.ForeignKey(
        finance.models.Account,
        on_delete=models.PROTECT,
        verbose_name='90 1 Вычеты на основании штрафов',
        related_name='account_90_1_fine_based_deduction_accounts',
    )

    account_90_2_root = models.ForeignKey(
        finance.models.Account,
        on_delete=models.PROTECT,
        verbose_name='90 2 Корень',
        related_name='account_90_2_root_accounts',
    )
    account_90_3_root = models.ForeignKey(
        finance.models.Account,
        on_delete=models.PROTECT,
        verbose_name='90 3 Корень',
        related_name='account_90_3_root_accounts',
    )
    account_90_9_root = models.ForeignKey(
        finance.models.Account,
        on_delete=models.PROTECT,
        verbose_name='90 9 Корень',
        related_name='account_90_9_root_accounts',
    )

    def __str__(self):
        return str(self.customer)

    def save(self, *args, **kwargs):
        name = self.customer.cust_name

        accounts_to_update = [
            self.account_10_root,
            self.account_20_root,
            self.account_62_root,
            self.account_76_sales,
            self.account_76_debts,
            self.account_76_fines,
            self.account_90_1_root,
            self.account_90_2_root,
            self.account_90_3_root,
            self.account_90_9_root,
        ]

        for account in accounts_to_update:
            account.name = name
            account.save()

        super().save(*args, **kwargs)


@transaction.atomic
def create_customer_operating_accounts(customer):
    root_10 = get_root_account('10')
    root_20 = get_root_account('20')
    root_62 = get_root_account('62')
    root_76 = get_root_account('76')
    root_76_sales = ensure_account(root_76, 'Непроактированные продажи')
    root_76_debts = ensure_account(root_76, 'Непроактированные долги')
    root_76_fines = ensure_account(root_76, 'Штрафы')
    root_90 = get_root_account('90')

    def _90_x_subaccount(name):
        accounts = finance.models.Account.objects.filter(
            parent=root_90,
            name__istartswith=name
        )
        if accounts.count() != 1:
            raise Exception('Problems with 90/{} account.'.format(name))
        return accounts.get()

    root_90_1 = _90_x_subaccount('1')
    root_90_2 = _90_x_subaccount('2')
    root_90_9 = _90_x_subaccount('9')

    account_name = str(customer)
    account_10_root = ensure_account(root_10, account_name)

    account_20_root = ensure_account(root_20, account_name)
    account_20_other = ensure_account(account_20_root, 'Прочее')
    account_20_foreman = ensure_account(account_20_root, 'Бригадиры')

    account_62_root = ensure_account(root_62, account_name)

    account_76_sales = ensure_account(root_76_sales, account_name)
    account_76_debts = ensure_account(root_76_debts, account_name)
    account_76_fines = ensure_account(root_76_fines, account_name)

    account_90_1_root = ensure_account(root_90_1, account_name)

    account_90_1_disciplinary_deductions = ensure_account(
        account_90_1_root,
        'Вычеты дисциплинарные'
    )
    account_90_1_fine_based_deductions = ensure_account(
        account_90_1_root,
        'Вычеты на основании штрафов'
    )

    account_90_2_root = ensure_account(root_90_2, account_name)

    account_90_3_root = ensure_accounts_chain(root_90, ['3. НДС', account_name])

    account_90_9_root = ensure_account(root_90_9, account_name)

    CustomerOperatingAccounts.objects.create(
        customer=customer,
        account_10_root=account_10_root,
        account_20_root=account_20_root,
        account_20_other=account_20_other,
        account_20_foreman=account_20_foreman,
        account_62_root=account_62_root,
        account_76_sales=account_76_sales,
        account_76_debts=account_76_debts,
        account_76_fines=account_76_fines,
        account_90_1_root=account_90_1_root,
        account_90_1_disciplinary_deductions=account_90_1_disciplinary_deductions,
        account_90_1_fine_based_deductions=account_90_1_fine_based_deductions,
        account_90_2_root=account_90_2_root,
        account_90_3_root=account_90_3_root,
        account_90_9_root=account_90_9_root
    )

    for account in [account_20_other, account_20_foreman]:
        cost_type = IndustrialCostType.objects.get(name=account.name)

        get_or_create_customer_industrial_accounts(customer, cost_type)


# Todo: remove
class RkoOperation(models.Model):
    rko = models.ForeignKey(
        Rko,
        on_delete=models.PROTECT,
        verbose_name='Расходный кассовый ордер'
    )
    operation = models.ForeignKey(
        finance.models.Operation,
        on_delete=models.PROTECT,
        verbose_name='Операция'
    )

    def __str__(self):
        return '{} <-> {}'.format(self.rko, self.operation)


class Service(models.Model):
    name = models.CharField('Услуга', max_length=200)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ('-id',)

    def __str__(self):
        return '{} {}'.format(self.pk, self.name)


class CustomerService(models.Model):
    customer = models.ForeignKey(
        Customer,
        on_delete=models.PROTECT,
        verbose_name='Клиент'
    )
    service = models.ForeignKey(
        Service,
        on_delete=models.PROTECT,
    )
    active = models.BooleanField(default=True)

    account_20_root = models.ForeignKey(
        finance.models.Account,
        on_delete=models.PROTECT,
        verbose_name='20 Корень',
        related_name='account_20_root_service',
    )
    account_20_general_work = models.ForeignKey(
        finance.models.Account,
        on_delete=models.PROTECT,
        verbose_name='20/расходы на обычных работников',
        related_name='account_20_general_work_service'
    )
    account_20_selfemployed_work = models.ForeignKey(
        finance.models.Account,
        on_delete=models.PROTECT,
        verbose_name='20/расходы на самозанятых работников',
        related_name='account_20_selfemployed_work_service',
    )
    account_20_general_taxes = models.ForeignKey(
        finance.models.Account,
        on_delete=models.PROTECT,
        verbose_name='20/налоги на обычных работников',
        related_name='account_20_general_taxes_service',
    )
    account_20_selfemployed_taxes = models.ForeignKey(
        finance.models.Account,
        on_delete=models.PROTECT,
        verbose_name='20/налоги на самозанятых работников',
        related_name='account_20_selfemployed_taxes_service',
    )

    account_76 = models.ForeignKey(
        finance.models.Account,
        on_delete=models.PROTECT,
        verbose_name='76 Счет',
        related_name='account_76_service'
    )
    account_90_1 = models.ForeignKey(
        finance.models.Account,
        on_delete=models.PROTECT,
        verbose_name='90.1 Счет',
        related_name='account_90_1_service'
    )

    class Meta:
        ordering = ('-id',)

    def __str__(self):
        return '{} -> {}'.format(self.customer, self.service)

    def save(self, *args, **kwargs):
        name = self.service.name

        accounts_to_update = [
            self.account_20_root,
            self.account_76,
            self.account_90_1,
        ]

        for account in accounts_to_update:
            account.name = name
            account.save()

        super().save(*args, **kwargs)


@transaction.atomic
def create_customer_service(customer, service):
    accounts = CustomerOperatingAccounts.objects.get(customer=customer)

    account_name = str(service)

    account_20_root = ensure_account(accounts.account_20_root, account_name)
    account_20_general_work = ensure_account(account_20_root, 'ЗП (обычные)')
    account_20_selfemployed_work = ensure_account(account_20_root, 'ЗП (самозанятые)')
    account_20_general_taxes = ensure_account(account_20_root, 'Налоги (обычные)')
    account_20_selfemployed_taxes = ensure_account(account_20_root, 'Налоги (самозанятые)')
    account_76 = ensure_account(accounts.account_76_sales, account_name)
    account_90_1 = ensure_account(accounts.account_90_1_root, account_name)

    return CustomerService.objects.create(
        customer=customer,
        service=service,
        account_20_root=account_20_root,
        account_20_general_work=account_20_general_work,
        account_20_selfemployed_work=account_20_selfemployed_work,
        account_20_general_taxes=account_20_general_taxes,
        account_20_selfemployed_taxes=account_20_selfemployed_taxes,
        account_76=account_76,
        account_90_1=account_90_1,
    )


class TurnoutService(models.Model):
    turnout = models.OneToOneField(
        WorkerTurnout,
        on_delete=models.CASCADE,
        verbose_name='Выход'
    )
    customer_service = models.ForeignKey(
        CustomerService,
        on_delete=models.PROTECT,
    )

    class Meta:
        ordering = ('-id',)

    def __str__(self):
        return '{} -> {}'.format(self.turnout, self.customer_service.service)


# Менеджеры

class DevelopmentManager(models.Model):
    worker = models.ForeignKey(
        Worker,
        on_delete=models.PROTECT,
    )
    customer = models.ForeignKey(
        Customer,
        on_delete=models.PROTECT,
    )

    def __str__(self):
        return str(self.worker)


class MaintenanceManager(models.Model):
    worker = models.ForeignKey(
        Worker,
        on_delete=models.PROTECT,
    )
    customer = models.ForeignKey(
        Customer,
        on_delete=models.PROTECT,
    )

    def __str__(self):
        return str(self.worker)


class DevelopmentManagerPosition(models.Model):
    position = models.ForeignKey(
        Position,
        on_delete=models.PROTECT,
    )

    def __str__(self):
        return str(self.position.pk)


class MaintenanceManagerPosition(models.Model):
    position = models.ForeignKey(
        Position,
        on_delete=models.PROTECT,
    )

    def __str__(self):
        return str(self.position.pk)


# Банки

class Bank(models.Model):
    name = models.CharField('Название', max_length=200)
    account_51 = models.ForeignKey(
        finance.models.Account,
        on_delete=models.PROTECT,
        verbose_name='51 Счет',
        related_name='bank_51_account',
    )
    account_90_2 = models.ForeignKey(
        finance.models.Account,
        on_delete=models.PROTECT,
        verbose_name='90.2 Счет',
        related_name='bank_90_2_account',
    )

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        parent_account_51 = finance.models.Account.objects.get(
            name__istartswith='51.', parent__isnull=True)
        parent_account_90 = finance.models.Account.objects.get(
            name__istartswith='90.', parent__isnull=True)
        parent_account_90_2 = parent_account_90.children.get(
            name__istartswith='2.')
        self.account_51 = finance.models.Account.objects.create(
            parent=parent_account_51, name=self.name)
        self.account_90_2 = finance.models.Account.objects.create(
            parent=parent_account_90_2, name=self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class BankService(models.Model):
    type = models.CharField(
        max_length=100,
        choices=(
            ('Перевод', 'Перевод'),
            ('Перевод поставщику', 'Перевод поставщику'),
            ('Кассовая операция', 'Кассовая операция'),
        ),
        default='Перевод',
        verbose_name='Тип'
    )
    debit = models.ForeignKey(
        finance.models.Account,
        on_delete=models.PROTECT,
    )

    def __str__(self):
        return self.type


class BankServiceParams(models.Model):
    bank = models.ForeignKey(
        Bank,
        on_delete=models.PROTECT,
    )
    service = models.ForeignKey(
        BankService,
        on_delete=models.PROTECT,
    )
    account = models.ForeignKey(
        finance.models.Account,
        on_delete=models.PROTECT,
    )
    calc_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.PROTECT,
        related_name='service_params_calculator'
    )
    calc_object_id = models.PositiveIntegerField()
    calculator = GenericForeignKey(
        'calc_content_type',
        'calc_object_id'
    )

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.account = finance.models.Account.objects.create(
            parent=self.bank.account_90_2, name=self.service.type)
        super().save(*args, **kwargs)

    # Todo: very bad pattern - make a method in a calculator?
    def comission_type(self):
        if '1' in self.calc_content_type.name:
            return 'От исходящей суммы'
        elif '2' in self.calc_content_type.name:
            return 'От входящей суммы'
        else:
            return 'Фикс'


class CommissionOperation(models.Model):
    operation = models.ForeignKey(
        finance.models.Operation,
        on_delete=models.PROTECT,
        related_name='co_operations'
    )
    commission = models.ForeignKey(
        finance.models.Operation,
        on_delete=models.PROTECT,
        related_name='co_commissions'
    )


class BankCalculatorCommissionFix(models.Model):
    val = models.FloatField('Фикс')

    def get_amount(self, operation):
        return self.val


# Todo: bad name
class BankCalculatorCommission1(models.Model):
    val = models.FloatField('От исходящей суммы')

    def get_amount(self, operation):
        amount = operation.amount * self.val
        return amount


# Todo: bad name
class BankCalculatorCommission2(models.Model):
    val = models.FloatField('От входящей суммы')

    def get_amount(self, operation):
        amount = operation.amount / (1 - self.val) * self.val
        return amount


class CustomerFineDeduction(models.Model):
    fine = models.ForeignKey(
        finance.models.Operation,
        on_delete=models.PROTECT,
        related_name='fines'
    )
    deduction = models.ForeignKey(
        finance.models.Operation,
        on_delete=models.PROTECT,
        related_name='deductions'
    )

    def __str__(self):
        return '{} {}'.format(self.pk, self.fine.comment)


# Виды расходов, Администрация
class AdministrationCostType(models.Model):
    name = models.CharField('Название', max_length=200)
    account_26 = models.ForeignKey(
        finance.models.Account,
        on_delete=models.PROTECT,
    )
    account_90_2 = models.ForeignKey(
        finance.models.Account,
        on_delete=models.PROTECT,
        related_name='admin_cost_type_90_2',
    )
    account_90_9 = models.ForeignKey(
        finance.models.Account,
        on_delete=models.PROTECT,
        related_name='admin_cost_type_90_9',
    )

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        parent_account_26 = finance.models.Account.objects.get(
            name__istartswith='26.', parent=None)

        root_90_2 = finance.models.Account.objects.filter(
            name='Общехозяйственные расходы',
            parent__name__startswith='2').first()
        if root_90_2 is None:
            raise Exception('Нет корневого счета в 90.2')

        root_90_9 = finance.models.Account.objects.filter(
            name='Общехозяйственные расходы',
            parent__name__startswith='9').first()
        if root_90_9 is None:
            raise Exception('Нет корневого счета в 90.9')

        if parent_account_26 is None:
            parent_account_26 = finance.models.Account.objects.create(
                name='26. Общехозяйственные расходы')

        if self.pk is None:
            self.account_90_2 = finance.models.Account.objects.create(
                name=self.name,
                parent=root_90_2
            )
            self.account_90_9 = finance.models.Account.objects.create(
                name=self.name,
                parent=root_90_9
            )
            self.account_26 = finance.models.Account.objects.create(
                parent=parent_account_26,
                name=self.name
            )

        super().save(*args, **kwargs)


# Виды производственных расходов и доходов
class IndustrialCostType(models.Model):
    name = models.CharField('Название', max_length=200)

    # Сделано для перевода существующих привязок к распределению по статьям
    # (если установлен этот флаг - используется существующий счет
    # CustomerOperatingAccounts.account_20_other, а не создается новый субсчет
    # счета CustomerOperatingAccounts.account_20_root)
    is_old_other = models.BooleanField(default=False, null=False)

    def __str__(self):
        return self.name


@receiver(post_save, sender=IndustrialCostType)
def _industrial_cost_type_post_save(sender, instance, **kwargs):
    accounts = finance.models.Account.objects.filter(
        Q(account_20_industrial_accounts__cost_type=instance) |
        Q(account_90_1_industrial_accounts__cost_type=instance)
    )
    for account in accounts:
        account.name = instance.name
        account.save()


# Привязка по производственным статьям расходов и доходов
class CustomerIndustrialAccounts(models.Model):
    customer = models.ForeignKey(
        Customer,
        on_delete=models.PROTECT,
        related_name='industrial_accounts'
    )
    cost_type = models.ForeignKey(
        IndustrialCostType,
        on_delete=models.PROTECT,
        verbose_name='Статьи расходов',
        related_name='customer_accounts',
    )

    account_20 = models.ForeignKey(
        finance.models.Account,
        on_delete=models.PROTECT,
        related_name='account_20_industrial_accounts'
    )
    account_90_1 = models.ForeignKey(
        finance.models.Account,
        on_delete=models.PROTECT,
        related_name='account_90_1_industrial_accounts',
    )

    def __str__(self):
        return '{} {}/{}'.format(
            self.pk,
            self.customer,
            self.cost_type.name
        )


@transaction.atomic
def get_or_create_customer_industrial_accounts(customer, cost_type):
    accounts_set = CustomerIndustrialAccounts.objects.filter(
        customer=customer,
        cost_type=cost_type
    )
    if accounts_set.exists():
        return accounts_set.get()

    operating_accounts_set = customer.customer_accounts

    if cost_type.is_old_other:
        account_20 = operating_accounts_set.account_20_other
    else:
        account_20 = ensure_account(
            operating_accounts_set.account_20_root,
            name=cost_type.name
        )

    account_90_1 = ensure_account(
        operating_accounts_set.account_90_1_root,
        name=cost_type.name
    )

    return CustomerIndustrialAccounts.objects.create(
        cost_type=cost_type,
        customer=customer,
        account_20=account_20,
        account_90_1=account_90_1
    )


# По сути - вариант субсчета счета 10. Материалы
class MaterialType(models.Model):
    name = models.CharField('Название', max_length=200)

    def __str__(self):
        return '{} {}'.format(
            self.pk,
            self.name
        )


@receiver(post_save, sender=MaterialType)
def _industrial_cost_type_post_save(sender, instance, **kwargs):
    accounts = finance.models.Account.objects.filter(
        account_10_subaccounts__material_type=instance
    )
    for account in accounts:
        account.name = instance.name
        account.save()


class Customer10SubAccount(models.Model):
    customer = models.ForeignKey(
        Customer,
        on_delete=models.PROTECT,
        related_name='customer_10_sub_accounts'
    )
    material_type = models.ForeignKey(
        MaterialType,
        on_delete=models.PROTECT,
    )

    account_10 = models.ForeignKey(
        finance.models.Account,
        on_delete=models.PROTECT,
        related_name='account_10_subaccounts'
    )


@transaction.atomic
def get_or_create_customer_10_subaccount(customer, material_type):
    accounts = Customer10SubAccount.objects.filter(
        customer=customer,
        material_type=material_type
    )
    if accounts.exists():
        return accounts.get()

    account_10 = ensure_account(
        customer.customer_accounts.account_10_root,
        name=material_type.name
    )

    return Customer10SubAccount.objects.create(
        customer=customer,
        material_type=material_type,
        account_10=account_10
    )


# Кредиторы
class Creditor(models.Model):
    name = models.CharField('Название', max_length=200)
    account_67 = models.ForeignKey(
        finance.models.Account,
        on_delete=models.PROTECT,
    )

    def save(self, *args, **kwargs):
        parent_account_67 = finance.models.Account.objects.filter(
            name__istartswith='67.',
            parent__isnull=True
        ).first()

        if parent_account_67 is None:
            parent_account_67 = finance.models.Account.objects.create(
                name='67. Расчеты по кредитам и займам')

        self.account_67 = finance.models.Account.objects.create(
            parent=parent_account_67, name=self.name)
        super().save(*args, **kwargs)


class PeriodCloseDocument(models.Model):
    begin = models.DateField(
        verbose_name='Дата начала периода'
    )
    end = models.DateField(
        verbose_name='Дата конца периода'
    )
    create_timepoint = models.DateTimeField(
        verbose_name='Время создания',
        default=timezone.now,
    )
    author = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
    )
    created = models.BooleanField(
        verbose_name='Процесс создания периода завершен',
        default=False,
    )

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise Exception('Нельзя изменить созданный документ')

        super().save(*args, **kwargs)

    def __str__(self):
        return '№{} с {} по {} ({})'.format(
            self.pk,
            string_from_date(self.begin),
            string_from_date(self.end),
            self.author.username
        )


class SheetPeriodClose(models.Model):
    close_document = models.ForeignKey(
        PeriodCloseDocument,
        on_delete=models.CASCADE,
        related_name='sheet_close_operations'
    )
    close_operation = models.ForeignKey(
        finance.models.Operation,
        on_delete=models.PROTECT,
        related_name='sheet_close_operation',
    )


class PhotoLoadSession(models.Model):
    CONTENT_TYPES = (
        ('contract', 'Фото договора'),
        ('timesheet', 'Фото табеля'),
        ('worker', 'Фото рабочего'),
    )
    content_type = models.CharField(
        max_length=20,
        choices=CONTENT_TYPES,
        verbose_name='Вид изображения')

    OBJECT_STATUSES = (
        ('new', 'Новая'),
        ('work', 'В работе'),
        ('comment', 'Есть комментарий'),
        ('complete', 'Закрыта'),
    )
    status = models.CharField(
        max_length=20,
        verbose_name='Статус',
        choices=OBJECT_STATUSES,
    )
    sender = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        verbose_name='Отправитель',
        related_name='senders'
    )
    handler = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        verbose_name='Обработчик',
        related_name='handlers',
        blank=True,
        null=True,
    )
    date_create = models.DateTimeField(auto_now_add=True)
    date_edit = models.DateTimeField(auto_now=True)

    @property
    def get_content_type(self):
        return self.get_content_type_display()

    @property
    def get_status(self):
        return self.get_status_display()

    def __str__(self):
        return 'Session {}'.format(self.pk)


class PhotoSessionComments(models.Model):
    date = models.DateTimeField(
        verbose_name='Дата создания',
        auto_now_add=True,
    )
    comment = models.TextField(
        verbose_name='Комментарий'
    )
    sender = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        verbose_name='Отправитель'
    )
    session = models.ForeignKey(
        PhotoLoadSession,
        on_delete=models.PROTECT,
        related_name='comments'
    )

    class Meta:
        ordering = ['date']


class PhotoSessionCitizenship(models.Model):
    session = models.OneToOneField(
        PhotoLoadSession,
        on_delete=models.PROTECT,
    )
    citizenship = models.ForeignKey(
        Country,
        on_delete=models.PROTECT,
        verbose_name='Гражданство',
    )

    def __str__(self):
        return '{} - {}'.format(
            self.session.pk,
            self.citizenship
        )


class PhotoSessionRejectedPhotos(models.Model):
    session = models.OneToOneField(
        PhotoLoadSession,
        on_delete=models.PROTECT,
    )

    def __str__(self):
        return 'RejectedPhotos for session {}'.format(self.session.pk)


class WorkerBonus(models.Model):
    operation = models.OneToOneField(
        finance.models.Operation,
        on_delete=models.PROTECT,
    )


class WorkerDeduction(models.Model):
    operation = models.OneToOneField(
        finance.models.Operation,
        on_delete=models.PROTECT,
    )


class SalaryPayment(models.Model):
    operation = models.OneToOneField(
        finance.models.Operation,
        on_delete=models.PROTECT,
    )


class AccountablePerson(models.Model):
    worker = models.OneToOneField(
        Worker,
        on_delete=models.PROTECT,
        verbose_name='Подотчетное лицо'
    )
    account_71 = models.ForeignKey(
        finance.models.Account,
        on_delete=models.PROTECT,
        blank=True,
        null=True,
    )

    def save(self, *args, **kwargs):
        if self.account_71 is None:
            root_71 = get_root_account('71')
            account_71 = finance.models.Account.objects.filter(
                name=str(self.worker),
                parent=root_71
            ).first()
            if account_71:
                account_71.closed = False
                account_71.save()
                self.account_71 = account_71
            else:
                self.account_71 = finance.models.Account.objects.create(
                    name=str(self.worker),
                    parent=root_71
                )

        super().save(*args, **kwargs)

    def __str__(self):
        return str(self.worker)


@receiver(pre_delete, sender=AccountablePerson)
def _accountable_person_pre_delete(sender, instance, **kwargs):
    instance.account_71.closed = True
    instance.account_71.save()


class DocumentWithAccountablePerson(models.Model):
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.PROTECT,
    )
    object_id = models.PositiveIntegerField()
    document = GenericForeignKey('content_type', 'object_id')

    accountable_person = models.ForeignKey(
        AccountablePerson,
        on_delete=models.PROTECT,
        verbose_name='Подотчетное лицо'
    )

    def __str__(self):
        return '{}({}) {}'.format(
            self.content_type,
            self.object_id,
            self.accountable_person.worker
        )


def set_accountable_person(target, accountable_person):
    link = DocumentWithAccountablePerson.objects.filter(
        content_type=ContentType.objects.get_for_model(type(target)),
        object_id=target.id
    )
    if link.exists():
        link = link.get()
        link.accountable_person = accountable_person
        link.save()
    else:
        link = DocumentWithAccountablePerson.objects.create(
            content_type=ContentType.objects.get_for_model(type(target)),
            object_id=target.id,
            accountable_person=accountable_person
        )

    return link


def get_accountable_person(target):
    link = DocumentWithAccountablePerson.objects.filter(
        content_type=ContentType.objects.get_for_model(type(target)),
        object_id=target.id
    )
    if link.exists():
        return link.get().accountable_person

    return None


def get_documents(accountable_person, model):
    return model.objects.filter(
        documentwithaccountableperson__accountable_person=accountable_person
    )


class AccountableDocumentOperation(models.Model):
    document = models.OneToOneField(
        DocumentWithAccountablePerson,
        on_delete=models.PROTECT,
        verbose_name='Документ'
    )
    operation = models.OneToOneField(
        finance.models.Operation,
        on_delete=models.PROTECT,
        verbose_name='Операция'
    )

    def __str__(self):
        return '{} {}'.format(
            self.document,
            self.operation
        )


models.signals.post_save.connect(_post_save_timesheet, sender=TimeSheet)
models.signals.post_save.connect(_post_save_photo, sender=Photo)


def get_user_location(user):
    try:
        return user.locationaccount.location
    except ObjectDoesNotExist:
        return None


class UniqueRecord(models.Model):
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.PROTECT,
    )
    object_id = models.BigIntegerField()
    record = GenericForeignKey('content_type', 'object_id')

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['content_type'],
                name='unique_record_model_constraint',
            )
        ]
