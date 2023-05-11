# -*- coding: utf-8 -*-

import datetime
from dataclasses import dataclass
from decimal import Decimal
from typing import (
    List,
    Optional,
    Tuple,
)

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from django.db.models import (
    F,
    Q,
    Sum,
)

from the_redhuman_is.models.delivery import (
    DeliveryRequest,
    ItemWorker,
)
from the_redhuman_is.models.models import (
    Customer,
    CustomerService,
    TimeSheet,
    WorkerTurnout,
)
from the_redhuman_is.models.worker import Position
from utils.date_time import string_from_date
from utils.numbers import ZERO_OO


VAT_FACTOR = Decimal('1.2')
PROFIT_FACTOR = Decimal('0.85')


def _amount_calculator(day, customer_service):
    return AmountCalculator.objects.get(
        Q(servicecalculator__last_day__isnull=True) |
        Q(servicecalculator__last_day__gte=day),
        servicecalculator__customer_service=customer_service,
        servicecalculator__first_day__lte=day,
    )


class PricingError(Exception):
    pass


def estimate_customer_price(date, service_id, hours):
    hours = float(hours)
    price = CalculatorInterval.objects.filter(
        singleturnoutcalculator__in=ServiceCalculator.objects.filter(
            Q(last_day__isnull=True) |
            Q(last_day__gte=date),
            customer_service=service_id,
            first_day__lte=date,
        ).values(
            'calculator__customer_object_id'
        )
    ).filter(
        begin__lte=hours
    ).annotate(
        price=F('k') * hours + F('b')
    ).order_by(
        'begin'
    ).values_list(
        'price',
        flat=True
    ).last()
    if price is None:
        raise PricingError
    return Decimal(str(price)).quantize(ZERO_OO)


class AmountCalculator(models.Model):
    customer_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.PROTECT,
        related_name='customer_amount_calculator'
    )
    customer_object_id = models.PositiveIntegerField()
    customer_calculator = GenericForeignKey(
        'customer_content_type',
        'customer_object_id'
    )

    worker_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.PROTECT,
        related_name='worker_amount_calculator'
    )
    worker_object_id = models.PositiveIntegerField()
    worker_calculator = GenericForeignKey(
        'worker_content_type',
        'worker_object_id'
    )

    foreman_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.PROTECT,
        related_name='foreman_amount_calculator'
    )
    foreman_object_id = models.PositiveIntegerField()
    foreman_calculator = GenericForeignKey(
        'foreman_content_type',
        'foreman_object_id'
    )

    def customer_calculator_name(self):
        from ..views.autocharge import calculator_name
        return calculator_name(self.customer_content_type, self.customer_calculator)

    def worker_calculator_name(self):
        from ..views.autocharge import calculator_name
        return calculator_name(self.worker_content_type, self.worker_calculator)

    def foreman_calculator_name(self):
        from ..views.autocharge import calculator_name
        return calculator_name(self.foreman_content_type, self.foreman_calculator)


class ServiceCalculator(models.Model):
    customer_service = models.ForeignKey(
        CustomerService,
        verbose_name='Услуга',
        on_delete=models.CASCADE
    )
    calculator = models.ForeignKey(
        AmountCalculator,
        verbose_name='Группа калькуляторов',
        on_delete=models.CASCADE
    )

    first_day = models.DateField(
        verbose_name='Первый день',
    )
    last_day = models.DateField(
        verbose_name='Последний день',
        blank=True,
        null=True
    )

    def __str__(self):
        return '{}/{}/с {} по {}'.format(
            self.customer_service.customer.cust_name,
            self.customer_service.service.name,
            string_from_date(self.first_day),
            string_from_date(self.last_day) if self.last_day else '-'
        )


class PositionCalculator(models.Model):
    customer = models.ForeignKey(
        Customer,
        verbose_name='Клиент',
        on_delete=models.PROTECT,
    )
    position = models.ForeignKey(
        Position,
        verbose_name='Должность',
        on_delete=models.PROTECT,
    )

    calculator_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.PROTECT,
        related_name='position_calculator'
    )
    calculator_object_id = models.PositiveIntegerField()
    calculator = GenericForeignKey(
        'calculator_content_type',
        'calculator_object_id'
    )

    first_day = models.DateField(
        verbose_name='Первый день',
    )
    last_day = models.DateField(
        verbose_name='Последний день',
        blank=True,
        null=True
    )

    def __str__(self):
        return '{}/{}/с {} по {}'.format(
            self.customer.cust_name,
            self.position.name,
            string_from_date(self.first_day),
            string_from_date(self.last_day) if self.last_day else '-'
        )


def _hours_worked(turnout):
    if turnout.hours_worked:
        return float(turnout.hours_worked)
    return 0.0


def _performance(turnout):
    if turnout.performance:
        return float(turnout.performance)
    return 0.0


# Todo: get rid of this!
def _fm_hours(turnout):
    hours = _hours_worked(turnout)
    performance = min(_performance(turnout), 100)
    if performance >= 85:
        return hours
    else:
        return hours * performance / 100.0


def _total_day_hours(turnout):
    if hasattr(turnout, 'turnoutservice'):
        turnouts = WorkerTurnout.objects.filter(
            timesheet__sheet_date=turnout.timesheet.sheet_date,
            timesheet__cust_location=turnout.timesheet.cust_location,
            turnoutservice__customer_service=turnout.turnoutservice.customer_service
        )
        total_hours = turnouts.aggregate(
            Sum('hours_worked')
        )['hours_worked__sum'] or 0
    else:
        total_hours = turnout.hours_worked
    return total_hours


_PARAMETERS = {
    'hours':           ('Отработано часов', 'За часы', _hours_worked),
    'fm_hours':        ('Отработано часов ФМ', 'За часы ФМ', _fm_hours),
    'total_day_hours': ('Отработано в сутки', 'За часы в сутки', _total_day_hours),
    'performance':     ('Выработка', 'За выработку', _performance),
    'tariffs_01_04_21':('Формула ПРР', 'Формула ПРР', None),
}

PARAMETERS_CHOICES = [(key, name) for key, (name, description, func) in _PARAMETERS.items()]


def _get_parameter_value(turnout, parameter):
    name, description, func = _PARAMETERS[parameter]
    return func(turnout)


class ConditionalCalculator(models.Model):
    parameter = models.CharField(
        'Параметр условия',
        max_length=100
    )
    threshold = models.FloatField('Граница условия')

    calc_lt_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.PROTECT,
        related_name='calc_lt'
    )
    calc_lt_object_id = models.PositiveIntegerField()
    calc_lt = GenericForeignKey(
        'calc_lt_content_type',
        'calc_lt_object_id'
    )

    calc_gte_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.PROTECT,
        related_name='calc_gte'
    )
    calc_gte_object_id = models.PositiveIntegerField()
    calc_gte = GenericForeignKey(
        'calc_gte_content_type',
        'calc_gte_object_id'
    )

    def get_amount(self, turnout):
        if _get_parameter_value(turnout, self.parameter) < self.threshold:
            return self.calc_lt.get_amount(turnout)
        else:
            return self.calc_gte.get_amount(turnout)


class CalculatorInterval(models.Model):
    begin = models.FloatField('Начало интервала')

    # v = k*x + b, линейная функция на интервале
    k = models.FloatField('Коэффициент')
    b = models.FloatField('Константа')


class SingleTurnoutCalculator(models.Model):
    parameter_1 = models.CharField(
        'Параметр расчета 1 (условие)',
        max_length=100
    )
    parameter_2 = models.CharField(
        'Параметр расчета 2 (формула)',
        max_length=100
    )
    intervals = models.ManyToManyField(CalculatorInterval)

    def get_amount(self, turnout: WorkerTurnout) -> Decimal:
        if self.parameter_2 == 'tariffs_01_04_21':
            try:
                request = turnout.requestworkerturnout.requestworker.request
            except AttributeError:
                raise NotImplementedError(
                    'Расчет по моделям первой версии больше не поддерживается.'
                )
            return get_delivery_request_sum(
                request,
                turnout
            )

        x1 = _get_parameter_value(turnout, self.parameter_1)
        interval = self.intervals.filter(begin__lte=x1).order_by('begin').last()
        amount = 0.0
        if interval is not None:
            x2 = _get_parameter_value(turnout, self.parameter_2)
            amount = interval.k * x2 + interval.b

        return Decimal(amount)

    def description(self):
        name, description, func = _PARAMETERS[self.parameter_1]
        text = description + ':'
        intervals = self.intervals.all().order_by('begin')
        if intervals.exists():
            first = True
            for interval in self.intervals.all().order_by('begin'):
                if not first:
                    text = text.format(interval.begin)
                text += ' [' + str(interval.begin) + ', {}) = '
                if interval.k != 0.0 and interval.b != 0.0:
                    text += '{}*X + {};'.format(interval.k, interval.b)
                elif interval.k != 0:
                    text += '{}*X;'.format(interval.k)
                else:
                    text += str(interval.b) + ';'

                first = False
            text = text.format('&infin;')
        else:
            text += '0'

        return text

    def __str__(self):
        name, description, func = _PARAMETERS[self.parameter_1]
        return '{} {}'.format(
            self.pk,
            name
        )


def clone_single_turnout_calculator(calculator):
    cloned = SingleTurnoutCalculator.objects.create(
        parameter_1=calculator.parameter_1,
        parameter_2=calculator.parameter_2,
    )

    for interval in calculator.intervals.all():
        cloned.intervals.add(
            CalculatorInterval.objects.create(
                begin=interval.begin,
                b=interval.b,
                k=interval.k
            )
        )

    cloned.save()

    return cloned


def clone_amount_calculator(amount_calculator):
    def _clone_calc(content_type, calc):
        if content_type != ContentType.objects.get_for_model(
            SingleTurnoutCalculator
        ):
            raise Exception(
                f'Calculator cloning is not implemented for content type {content_type}'
            )

        return clone_single_turnout_calculator(calc)

    ac = amount_calculator

    return AmountCalculator.objects.create(
        customer_calculator=_clone_calc(ac.customer_content_type, ac.customer_calculator),
        foreman_calculator=_clone_calc(ac.foreman_content_type, ac.foreman_calculator),
        worker_calculator=_clone_calc(ac.worker_content_type, ac.worker_calculator),
    )


class Pair(models.Model):
    key = models.FloatField('Ключ')
    value = models.FloatField('Значение')

    def __str__(self):
        return '{} -> {}'.format(self.key, self.value)


def _get_value(conditions, threshold):
    if threshold is None:
        threshold = 0
    filtered = conditions.filter(key__lte=threshold)
    if filtered.exists():
        return Decimal(filtered.order_by('key').last().value)
    return Decimal(0)


class CalculatorHourly(models.Model):
    tariff = models.FloatField('Ставка в час')
    bonus = models.FloatField('Премия', default=0)
    threshold = models.IntegerField('Бонус при часах', default=11)

    def get_amount(self, turnout):
        hours_worked = turnout.hours_worked if turnout.hours_worked else 0
        amount = hours_worked * Decimal(self.tariff)
        if hours_worked >= self.threshold:
            amount += Decimal(self.bonus)
        return amount

    def __str__(self):
        return '{}'.format(self.pk)


class CalculatorBoxes(models.Model):
    conditions = models.ManyToManyField(Pair)

    performance_for_linear_payment = models.IntegerField('Граница чистой сделки', null=True)
    coefficient = models.DecimalField(
        'Плата за коробку', null=True, decimal_places=2, max_digits=8
    )

    def get_amount(self, turnout):
        performance = turnout.performance if turnout.performance else 0
        if self.performance_for_linear_payment and self.coefficient:
            if performance > self.performance_for_linear_payment:
                return performance * self.coefficient
        return _get_value(self.conditions, performance)

    def __str__(self):
        return '{}'.format(self.pk)


class CalculatorForemanWorkers(models.Model):
    conditions = models.ManyToManyField(Pair)

    def get_amount(self, turnout):
        num_workers = WorkerTurnout.objects.filter(
            timesheet=turnout.timesheet).exclude(worker=turnout.worker).count()
        return _get_value(self.conditions, num_workers)

    def __str__(self):
        return '{}'.format(self.pk)


class CalculatorHourlyInterval(models.Model):
    conditions = models.ManyToManyField(Pair)

    def get_amount(self, turnout):
        return _get_value(self.conditions, turnout.hours_worked)

    def __str__(self):
        return '{}'.format(self.pk)


class CalculatorTurnouts(models.Model):
    threshold = models.IntegerField('Выходы')

    calc1_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.PROTECT,
        related_name='calc1'
    )
    calc1_object_id = models.PositiveIntegerField()
    calc1 = GenericForeignKey(
        'calc1_content_type',
        'calc1_object_id'
    )

    calc2_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.PROTECT,
        related_name='calc2'
    )
    calc2_object_id = models.PositiveIntegerField()
    calc2 = GenericForeignKey(
        'calc2_content_type',
        'calc2_object_id'
    )

    def get_amount(self, turnout):
        turnouts = WorkerTurnout.objects.filter(
            worker=turnout.worker,
            timesheet__customer=turnout.timesheet.customer
        ).count()

        if turnouts < self.threshold:
            return self.calc1.get_amount(turnout)
        else:
            return self.calc2.get_amount(turnout)

    def __str__(self):
        return '{}'.format(self.pk)


class CalculatorForeman(models.Model):
    calc1_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.PROTECT,
        related_name='foreman_calc1'
    )
    calc1_object_id = models.PositiveIntegerField()
    calc1 = GenericForeignKey(
        'calc1_content_type',
        'calc1_object_id'
    )

    calc2_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.PROTECT,
        related_name='foreman_calc2'
    )
    calc2_object_id = models.PositiveIntegerField()
    calc2 = GenericForeignKey(
        'calc2_content_type',
        'calc2_object_id'
    )

    def get_amount(self, turnout):
        return self.calc1.get_amount(turnout) + self.calc2.get_amount(turnout)

    def __str__(self):
        return '{}'.format(self.pk)


class CalculatorForemanOutputSum(models.Model):
    conditions = models.ManyToManyField(Pair)

    # Исторически сложившаяся ситуация
    # для дневного + ночного табеля с этим бригадиром
    # считаем суммарную выработку, и по ней оплачиваем
    # ночной табель. Дневной табель не оплачиваем.
    def get_amount(self, foreman_turnout):
        current_timesheet = foreman_turnout.timesheet
        if current_timesheet.sheet_turn == 'День':
            return 0

        timesheets = TimeSheet.objects.filter(
            foreman=current_timesheet.foreman,
            sheet_date=current_timesheet.sheet_date
        ).distinct()

        customer_calculator_pk = AmountCalculator.objects.get(
            foreman_object_id=self.pk
        ).customer_object_id

        prices = CalculatorOutput.objects.get(
            pk=customer_calculator_pk
        ).prices

        # выработка, выраженная в деньгах
        output_sum = 0
        for timesheet in timesheets:
            for turnout in timesheet.worker_turnouts.all():
                for output in TurnoutOutput.objects.filter(turnout=turnout):
                    price = prices.get(
                        box_type=output.box_type
                    ).price
                    output_sum += output.amount * price
        return _get_value(self.conditions, output_sum)

    def __str__(self):
        return '{}'.format(self.pk)


class BoxType(models.Model):
    customer = models.ForeignKey(
        Customer,
        verbose_name='Клиент',
        on_delete=models.PROTECT,
    )

    name = models.CharField(
        'Тип',
        max_length=200)

    def __str__(self):
        return '{} {}'.format(self.pk, self.name)


class TurnoutOutput(models.Model):
    turnout = models.ForeignKey(
        WorkerTurnout,
        verbose_name='Выход',
        related_name='output',
        on_delete=models.CASCADE
    )
    box_type = models.ForeignKey(
        BoxType,
        verbose_name='Тип',
        on_delete=models.PROTECT
    )
    amount = models.IntegerField('Количество')
    errors = models.IntegerField('Ошибки')

    def __str__(self):
        return '{} {} {}'.format(self.pk, self.box_type, self.amount)


def set_turnout_output(turnout, box_type, amount, errors=0):
    output = TurnoutOutput.objects.filter(
        turnout=turnout,
        box_type=box_type
    )
    if output.exists():
        output = output.get()
        output.amount = amount
        output.errors = errors
        output.save()
    else:
        TurnoutOutput.objects.create(
            turnout=turnout,
            box_type=box_type,
            amount=amount,
            errors=errors
        )


# Калькулятор чистой сделки с особыми условиями для новичков
# Если отработал меньше 4 смен - оплата 0
# Если отработал [4, 6] смен - оплата по сделке
# Если отработал 7+ смен - оплата по сделке + бонус за первые 3 смены,
#     если собрано не менее 300 коробок
class CalculatorOutput(models.Model):
    # Deprecated, todo: remove
    bonus_enabled = models.BooleanField(default=False)

    is_side_job = models.BooleanField(default=False)

    fixed_bonus = models.DecimalField(
        'Бонус за выход',
        decimal_places=2,
        max_digits=8,
        default=0
    )

    def get_amount(self, turnout):
        if self.is_side_job:
            amount = Decimal(self._side_job_amount(turnout))
            if amount > 0:
                amount += self.fixed_bonus
            return amount

        if not self.bonus_enabled:
            amount = self._turnout_output_sum(turnout)
            if amount > 0:
                amount += self.fixed_bonus
            return amount

        # Обработка бонуса
        s = self.fixed_bonus

        worker = turnout.worker
        turnouts = worker.worker_turnouts.filter(
            timesheet__customer=turnout.timesheet.customer,
            timesheet__sheet_date__lte=turnout.timesheet.sheet_date
        ).order_by(
            'timesheet__sheet_date'
        )

        # после 11.06 бонус отменен
        deadline = datetime.date(year=2019, month=6, day=11)
        if turnouts.first().timesheet.sheet_date > deadline:
            return self._turnout_output_sum(turnout)

        if turnouts.count() < 4:
            pass
        elif turnouts.count() == 4:
            for turnout in turnouts:
                s += self._turnout_output_sum(turnout)
        elif turnouts.count() == 7:
            turnouts = list(turnouts)
            s += self._turnout_output_sum(turnout)
            for turnout in turnouts[:3]:
                output = 0
                if hasattr(turnout, 'output'):
                    for item in turnout.output.all():
                        output += item.amount

                turnout_sum = self._turnout_output_sum(turnout)
                if output >= 300 and turnout_sum < 1200:
                    s += (1200 - turnout_sum)

        else:
            s = self._turnout_output_sum(turnout)

        return s

    def _side_job_amount(self, turnout):
        worker = turnout.worker
        if not hasattr(turnout, 'turnoutservice'):
            return 0

        side_job_service = turnout.turnoutservice

        # Новичкам подрабатывать можно только 3 дня.
        # Дальше рабочий должен переходить либо на вахтовый вариант
        # либо на обычный

        turnouts = worker.worker_turnouts.filter(
            timesheet__customer=turnout.timesheet.customer,
            timesheet__sheet_date__lte=turnout.timesheet.sheet_date
        ).order_by(
            'timesheet__sheet_date'
        )

        if turnouts.count() > 3:
            if turnout not in list(turnouts)[:3]:
                return 0

        if not hasattr(turnout, 'output'):
            return 0

        if not hasattr(self, 'prices'):
            return 0

        vegetables = 0
        vegetables_output = turnout.output.filter(
            box_type__name='Овощи'
        )
        if vegetables_output.exists():
            vegetables = vegetables_output.get().amount

        other = turnout.output.exclude(
            box_type__name='Овощи'
        ).aggregate(
            Sum('amount')
        )['amount__sum'] or 0

        if vegetables >= 300 or other >= 400:
            return max(
                1000,
                self._turnout_output_sum(turnout)
            )

        return 0

    def _turnout_output_sum(self, turnout):
        s = Decimal(0)
        if hasattr(turnout, 'output') and hasattr(self, 'prices'):
            for item in turnout.output.all():
                try:
                    price = self.prices.get(box_type=item.box_type).price
                    s += (item.amount * price)
                except ObjectDoesNotExist:
                    pass
        return s

    def __str__(self):
        return '{}'.format(self.pk)


class BoxPrice(models.Model):
    calculator = models.ForeignKey(
        CalculatorOutput,
        verbose_name='Калькулятор',
        related_name='prices',
        on_delete=models.CASCADE
    )
    box_type = models.ForeignKey(
        BoxType,
        verbose_name='Тип товара',
        on_delete=models.CASCADE
    )
    price = models.DecimalField(
        'Плата за коробку',
        decimal_places=4,
        max_digits=8)

    def __str__(self):
        return '{} {} {}'.format(self.pk, self.box_type, self.price)


NIGHT_SURCHARGE = Decimal(2).quantize(ZERO_OO)
DAYTIME = slice(datetime.time(7, 0), datetime.time(22, 0))


def _is_nighttime(timepoint):
    return (
        timepoint is not None and
        not DAYTIME.start <= timepoint < DAYTIME.stop
    )


def get_delivery_request_hours(
        request: DeliveryRequest,
        base_hours: Optional[Decimal] = None,
) -> Tuple[Decimal, Decimal, Decimal]:
    """
    base_hours is actual work hours on location
    """
    return calculate_delivery_request_hours(
        hours=request.delivery_service.hours,
        travel_hours=request.delivery_service.travel_hours,
        confirmed_timepoint=request.confirmed_timepoint,
        base_hours=base_hours,
    )


def calculate_delivery_request_hours(
        hours: int,
        travel_hours: int,
        confirmed_timepoint: Optional[datetime.time],
        base_hours: Optional[Decimal] = None,
) -> Tuple[Decimal, Decimal, Decimal]:

    minimum_hours = Decimal(hours - travel_hours).quantize(ZERO_OO)
    if base_hours is not None:
        base_hours = max(base_hours.quantize(ZERO_OO), minimum_hours)
    else:
        base_hours = minimum_hours

    travel_hours = Decimal(travel_hours).quantize(ZERO_OO)

    if _is_nighttime(confirmed_timepoint):
        night_surcharge = NIGHT_SURCHARGE
    else:
        night_surcharge = ZERO_OO

    return base_hours, travel_hours, night_surcharge


def get_delivery_request_bonus(request: DeliveryRequest) -> Optional[Decimal]:
    if request.delivery_service is None:
        return None
    return sum(get_delivery_request_hours(request)[1:])


def get_delivery_request_sum(request: DeliveryRequest, turnout: WorkerTurnout) -> Decimal:
    _MAX_CANCELLED_AMOUNT = Decimal('700.00')
    _FIRST_TURNOUT_MSK_THRESHOLD = Decimal('500.00')
    _FIRST_TURNOUT_MSK_BONUS = Decimal('100.00')

    amount = estimate_delivery_request_sum(
        EstimateSumRequest(
            hours=turnout.hours_worked,
            zone=request.delivery_service.zone,
            status=request.status,
            date=request.date,
            items=[
                EstimateSumItem(
                    mass=mass,
                    has_elevator=has_elevator,
                    floor=floor,
                    carrying_distance=carrying_distance,
                )
                for mass, has_elevator, floor, carrying_distance in ItemWorker.objects.filter(
                    requestworker__request=request,
                    requestworker__worker=turnout.worker,
                    itemworkerrejection__isnull=True,
                ).values_list(
                    'item__mass',
                    'item__has_elevator',
                    'item__floor',
                    'item__carrying_distance',
                )
            ]
        )
    )
    if (
            request.delivery_service.zone == 'msk' and
            amount < _FIRST_TURNOUT_MSK_THRESHOLD and
            not WorkerTurnout.objects.filter(
                worker=turnout.worker,
                timesheet__sheet_date=turnout.timesheet.sheet_date,
                requestworkerturnout__requestworker__request__delivery_service__zone='msk',
                hours_worked__isnull=False,  # always ok?
                pk__lt=turnout.pk,
            ).exists()
    ):
        amount += _FIRST_TURNOUT_MSK_BONUS

    if request.status == DeliveryRequest.CANCELLED_WITH_PAYMENT:
        amount = min(amount, _MAX_CANCELLED_AMOUNT)

    return amount


@dataclass
class EstimateSumItem:
    __slots__ = ['mass', 'has_elevator', 'floor', 'carrying_distance']
    mass: float
    has_elevator: Optional[bool]
    floor: Optional[int]
    carrying_distance: Optional[int]


@dataclass
class EstimateSumRequest:
    __slots__ = ['hours', 'zone', 'status', 'date', 'items']
    hours: Decimal
    zone: str
    status: str
    date: datetime.date
    items: List[EstimateSumItem]


def estimate_delivery_request_sum(request: EstimateSumRequest) -> Decimal:
    amount = ZERO_OO
    labor_units = request.hours
    route_bonus = 150
    mass_bonus = 200

    if not request.items:
        return ZERO_OO

    if request.zone[:3] in ('msk', 'spb'):
        INCREASED_AMOUNT_DEC_2021_MSK_FIRST_DAY = datetime.date(day=27, month=12, year=2021)
        INCREASED_AMOUNT_DEC_2021_MSK_LAST_DAY = datetime.date(day=31, month=12, year=2021)
        INCREASED_AMOUNT_JAN_2022_MSK_FIRST_DAY = datetime.date(day=20, month=1, year=2022)

        INCREASED_AMOUNT_DEC_2021_SPB_DAY = datetime.date(day=31, month=12, year=2021)
        if (
                request.zone[:3] == 'msk' and
                labor_units == 3 and
                (
                        INCREASED_AMOUNT_JAN_2022_MSK_FIRST_DAY <= request.date or
                        INCREASED_AMOUNT_DEC_2021_MSK_FIRST_DAY <= request.date
                        <= INCREASED_AMOUNT_DEC_2021_MSK_LAST_DAY
                )
        ):
            amount += 500
        elif (
            request.zone[:3] == 'spb' and
            labor_units == 3 and
            request.date == INCREASED_AMOUNT_DEC_2021_SPB_DAY
        ):
            amount += 500
        else:
            amount += 400
            
        labor_units -= 3
        route_bonus = 200
        
        if request.zone[:3] == 'msk':
            SPECIAL_DAY = datetime.date(day=28, month=6, year=2021)
            if request.date == SPECIAL_DAY:
                amount += 200

    elif request.zone[:5] in ('adler', 'sochi', 'krasn'):
        mass_bonus = 0
        amount = 250
        labor_units -= 1
        
    else:
        INCREASED_AMOUNT_FIRST_DAY = datetime.date(day=7, month=9, year=2021)
        INCREASED_AMOUNT_FIRST_DAY_SAMARA = datetime.date(day=19, month=11, year=2021)
        
        if request.zone[:6] == 'samara' and request.date >= INCREASED_AMOUNT_FIRST_DAY_SAMARA:
            amount += 400
        elif request.date >= INCREASED_AMOUNT_FIRST_DAY:
            amount += 350
        else:
            amount += 300

        labor_units -= 2

    labor_units = max(labor_units, ZERO_OO)

    if request.status != DeliveryRequest.CANCELLED_WITH_PAYMENT:
        # route or heavy
        if len(request.items) == 1:
            if request.items[0].mass >= 500:
                amount += mass_bonus
        else:
            amount += route_bonus

        # elevator and carrying
        for item in request.items:
            if item.has_elevator is False:
                if item.floor is not None and item.floor > 4:
                    amount += 50 * min(11, (item.floor - 4))

            if item.carrying_distance is not None and item.carrying_distance > 50:
                amount += 50 * (min(200, item.carrying_distance - 50) // 50)

    return amount + labor_units * 200
