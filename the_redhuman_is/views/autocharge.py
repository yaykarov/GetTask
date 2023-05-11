# -*- coding: utf-8 -*-

import json
import re

from django import forms

from django.db import transaction
from django.http import HttpResponse
from django.http import JsonResponse
from django.shortcuts import render

from ..auth import staff_account_required

from the_redhuman_is import models
from the_redhuman_is.models.turnout_calculators import PARAMETERS_CHOICES

from utils.date_time import string_from_date
from the_redhuman_is.views.utils import get_first_last_day


CALCULATOR_TYPE_CHOICES = [
    ('piecewise_linear', 'Линейный на интервалах'),
    ('turnout_output', 'Чистая сделка (ассортимент)'),
    ('by_turnouts', 'В зависимости от кол-ва выходов'),
    ('foreman', 'Бригадир - надбавка за штат'),
    ('foreman_output_sum', 'Бригадир - надбавка за сделку бригады'),
]

CALCULATOR_TYPES = dict(CALCULATOR_TYPE_CHOICES)


def _autocomplete_interval(interval):
    return {
        'id': interval.pk,
        'text': 'с {} по {}'.format(
            string_from_date(interval.first_day),
            string_from_date(interval.last_day) if interval.last_day else '-'
        )
    }


def service_calculator_autocomplete(request):
    service_pk = json.loads(request.GET['forward'])['service']
    customer_service = models.CustomerService.objects.get(pk=service_pk)
    results = []
    for calculator in customer_service.servicecalculator_set.all():
        results.append(
            _autocomplete_interval(calculator)
        )
    return JsonResponse(
        {
            'results': results
        }
    )


def position_calculator_autocomplete(request):
    forwarded = json.loads(request.GET['forward'])
    customer_pk = forwarded['p_customer']
    position_pk = forwarded['position']

    results = []
    if customer_pk and position_pk:
        calculators = models.PositionCalculator.objects.filter(
            customer__pk=customer_pk,
            position__pk=position_pk
        )

        for calculator in calculators:
            results.append(
                _autocomplete_interval(calculator)
            )

    return JsonResponse(
        {
            'results': results
        }
    )


class CalculatorForm(forms.Form):
    calculator_type = forms.CharField(
        label='Калькулятор',
        widget=forms.Select(
            choices=CALCULATOR_TYPE_CHOICES,
            attrs={'class': 'form-control form-control-sm'}
        )
    )


def _calculator_type(content_type):

    model_class = content_type.model_class() if content_type else models.SingleTurnoutCalculator

    if model_class == models.CalculatorHourly:
        return 'hourly'
    elif model_class == models.CalculatorBoxes:
        return 'by_boxes'
    elif model_class == models.CalculatorTurnouts:
        return 'by_turnouts'
    elif model_class == models.CalculatorHourlyInterval:
        return 'hourly_interval'
    elif model_class == models.CalculatorOutput:
        return 'turnout_output'
    elif model_class == models.CalculatorForeman:
        return 'foreman'
    elif model_class == models.CalculatorForemanOutputSum:
        return 'foreman_output_sum'
    elif model_class == models.SingleTurnoutCalculator:
        return 'piecewise_linear'

    raise Exception('Unknown content type')


def calculator_name(content_type, calculator):
    name = CALCULATOR_TYPES[_calculator_type(content_type)]
    if content_type.model_class() == models.CalculatorHourly:
        return '{} - {}'.format(calculator.tariff, name.lower())
    elif content_type.model_class() == models.SingleTurnoutCalculator:
        return calculator.description()
    else:
        return name


def _pairs_for_render(calculator, id_suffix):
    pairs = []
    i = 0
    if calculator:
        for condition in calculator.conditions.all():
            pairs.append(
                {
                    'id_suffix': '{}_{}'.format(id_suffix, i),
                    'key': condition.key,
                    'value': condition.value
                }
            )
            i += 1

    pairs.append(
        {
            'id_suffix': '{}_{}'.format(id_suffix, i),
            'key': '',
            'value': ''
        }
    )

    return pairs


def _intervals_for_render(calculator, id_suffix):
    intervals = []
    i = 0
    if calculator:
        for interval in calculator.intervals.all().order_by('begin'):
            intervals.append(
                {
                    'id_suffix': '{}_{}'.format(id_suffix, i),
                    'begin': interval.begin,
                    'k': interval.k,
                    'b': interval.b
                }
            )
            i += 1

    intervals.append(
        {
            'id_suffix': '{}_{}'.format(id_suffix, i),
            'begin': '',
            'k': '',
            'b': ''
        }
    )

    return intervals


def _render_hourly_calculator(request, calculator, id_suffix):
    return render(
        request,
        'the_redhuman_is/autocharge/subforms/hourly.html',
        {
            'id_suffix': id_suffix,
            'tariff': calculator.tariff if calculator else 0,
            'bonus': calculator.bonus if calculator else 0,
            'threshold': calculator.threshold if calculator else 11
        }
    )


def _render_turnouts_calculator(request, calculator, id_suffix):
    calc1_type, calc1_form = _render_specific_calculator(
        request,
        calculator.calc1_content_type if calculator else None,
        calculator.calc1 if calculator and calculator.calc1 else None,
        'piecewise_linear',
        id_suffix + '_1'
    )

    calc2_type, calc2_form = _render_specific_calculator(
        request,
        calculator.calc2_content_type if calculator else None,
        calculator.calc2 if calculator and calculator.calc2 else None,
        'piecewise_linear',
        id_suffix + '_2'
    )

    return render(
        request,
        'the_redhuman_is/autocharge/subforms/turnouts.html',
        {
            'id_suffix': id_suffix,
            'entry': calculator.threshold if calculator else 7,
            'calc1': calc1_form.content.decode('utf-8'),
            'calc2': calc2_form.content.decode('utf-8'),
        }
    )


def _render_foreman_calculator(request, calculator, id_suffix):
    calc1_type, calc1_form = _render_specific_calculator(
        request,
        calculator.calc1_content_type if calculator else None,
        calculator.calc1 if calculator and calculator.calc1 else None,
        'piecewise_linear',
        id_suffix + '_1'
    )

    calc2_form = _render_intervals_calculator(
        request,
        calculator.calc2 if calculator and calculator.calc2 else None,
        id_suffix + '_2',
        False
    )

    return render(
        request,
        'the_redhuman_is/autocharge/subforms/foreman_working.html',
        {
            'id_suffix': id_suffix,
            'calc1': calc1_form.content.decode('utf-8'),
            'calc2': calc2_form.content.decode('utf-8'),
        }
    )


# Todo: возможно, стоит выделить часть про linear_payment_coefficient
def _render_intervals_calculator(
        request,
        calculator,
        id_suffix,
        is_linear_payment=True):
    pairs = _pairs_for_render(calculator, id_suffix)

    perf = None
    coefficient = None
    if calculator and hasattr(calculator, 'performance_for_linear_payment'):
        perf = calculator.performance_for_linear_payment
        coefficient = calculator.coefficient

    return render(
        request,
        'the_redhuman_is/autocharge/subforms/intervals.html',
        {
            'id_suffix': id_suffix,
            'pairs': pairs,
            'performance_for_linear_payment': perf,
            'linear_payment_coefficient': coefficient,
            'is_linear_payment': is_linear_payment
        }
    )


def _render_hourly_interval_calculator(request, calculator, id_suffix):
    pairs = _pairs_for_render(calculator, id_suffix)

    return render(
        request,
        'the_redhuman_is/autocharge/subforms/intervals.html',
        {
            'id_suffix': id_suffix,
            'pairs': pairs
        }
    )


def _render_piecewise_linear_calculator(request, calculator, id_suffix):
    return render(
        request,
        'the_redhuman_is/autocharge/subforms/piecewise_linear.html',
        {
            'id_suffix': id_suffix,
            'parameter_choices': PARAMETERS_CHOICES,
            'selected_key_1': calculator.parameter_1 if calculator else 'hours',
            'selected_key_2': calculator.parameter_2 if calculator else 'hours',
            'intervals': _intervals_for_render(calculator, id_suffix)
        }
    )


def _render_turnout_output_calculator(request, calculator, id_suffix):
    customer_service = models.CustomerService.objects.get(pk=request.GET['service'])
    box_types = models.BoxType.objects.filter(customer=customer_service.customer)
    box_infos = []
    for box_type in box_types:
        price = 0
        try:
            if calculator:
                price = calculator.prices.get(box_type=box_type).price
        except models.BoxPrice.DoesNotExist:
            pass
        box_infos.append(
            {
                'price': price,
                'name': box_type.name,
                'box_type_pk': box_type.pk,
            }
        )

    return render(
        request,
        'the_redhuman_is/autocharge/subforms/turnout_output.html',
        {
            'id_suffix': id_suffix,
            'fixed_bonus': calculator.fixed_bonus if calculator else 0,
            'bonus_enabled': calculator.bonus_enabled if calculator else False,
            'is_side_job': calculator.is_side_job if calculator else False,
            'box_infos': box_infos
        }
    )


def _render_specific_calculator(request, content_type, calculator, target_type, id_suffix):
    if target_type:
        if target_type != _calculator_type(content_type):
            content_type = None
            calculator = None
    else:
        target_type = _calculator_type(content_type)

    if target_type == 'hourly':
        rendered = _render_hourly_calculator(request, calculator, id_suffix)
    elif target_type == 'by_boxes':
        rendered = _render_intervals_calculator(request, calculator, id_suffix)
    elif target_type == 'by_turnouts':
        rendered = _render_turnouts_calculator(request, calculator, id_suffix)
    elif target_type == 'hourly_interval':
        rendered = _render_hourly_interval_calculator(request, calculator, id_suffix)
    elif target_type == 'turnout_output':
        rendered = _render_turnout_output_calculator(request, calculator, id_suffix)
    elif target_type == 'foreman':
        rendered = _render_foreman_calculator(request, calculator, id_suffix)
    elif target_type == 'foreman_output_sum':
        rendered = _render_hourly_interval_calculator(request, calculator, id_suffix)
    elif target_type == 'piecewise_linear':
        rendered = _render_piecewise_linear_calculator(request, calculator, id_suffix)

    return target_type, rendered


def _amount_calculator(customer_service):
    calculator = models.ServiceCalculator.objects.filter(customer_service=customer_service)
    if calculator.exists():
        return calculator.get().calculator

    return None


# Todo: merge settings & specific_setting
@staff_account_required
def settings(request):
    from ..forms import ServiceCalculatorForm
    from ..forms import PositionCalculatorForm
    from ..forms import DaysIntervalForm

    if not request.user.is_superuser:
        raise Exception('Недостаточно прав доступа')

    return render(
        request,
        'the_redhuman_is/autocharge/settings.html',
        {
            'calculator_form': ServiceCalculatorForm(),
            'interval_form': DaysIntervalForm(),
            'calculators': models.ServiceCalculator.objects.all(),

            'position_calculator_form': PositionCalculatorForm(),
            'position_interval_form': DaysIntervalForm(
                field_prefix='position_'
            )
        }
    )


@staff_account_required
def specific_setting(request, pk):
    from ..forms import ServiceCalculatorForm
    from ..forms import DaysIntervalForm

    if not request.user.is_superuser:
        raise Exception('Недостаточно прав доступа')

    service_pk=request.GET.get('service_pk')

    if service_pk:
        service = models.CustomerService.objects.get(pk=service_pk)
        calculator = models.ServiceCalculator.objects.get(customer_service=service)
        calculators = models.ServiceCalculator.objects.filter(
            customer_service__customer=service.customer
        )
        single_customer = True
    else:
        calculator = models.ServiceCalculator.objects.get(
            calculator__pk=pk
        )
        calculators = models.ServiceCalculator.objects.all()
        single_customer = False

    return render(
        request,
        'the_redhuman_is/autocharge/settings.html',
        {
            'calculator_form': ServiceCalculatorForm(
                initial={
                    'customer': calculator.customer_service.customer,
                    'service': calculator.customer_service
                }
            ),
            'interval_form': DaysIntervalForm(),
            'single_customer': single_customer,
            'calculators': calculators
        }
    )


@staff_account_required
def calculator_form(request):
    calculator = None
    interval_pk = request.GET.get('interval')
    if interval_pk:
        service_calculator = models.ServiceCalculator.objects.get(
            pk=interval_pk
        )
        calculator = service_calculator.calculator

    customer_type, customer_form = _render_specific_calculator(
        request,
        calculator.customer_content_type if calculator else None,
        calculator.customer_calculator if calculator else None,
        None,
        'customer'
    )

    foreman_type, foreman_form = _render_specific_calculator(
        request,
        calculator.foreman_content_type if calculator else None,
        calculator.foreman_calculator if calculator else None,
        None,
        'foreman'
    )

    worker_type, worker_form = _render_specific_calculator(
        request,
        calculator.worker_content_type if calculator else None,
        calculator.worker_calculator if calculator else None,
        None,
        'worker'
    )

    return render(
        request,
        'the_redhuman_is/autocharge/calculator_form.html',
        {
            'customer_form': CalculatorForm(
                auto_id='customer_%s',
                initial={ 'calculator_type': customer_type }
            ),
            'customer_calc': customer_form.content.decode('utf-8'),

            'foreman_form': CalculatorForm(
                auto_id='foreman_%s',
                initial={ 'calculator_type': foreman_type }
            ),
            'foreman_calc': foreman_form.content.decode('utf-8'),

            'worker_form': CalculatorForm(
                auto_id='worker_%s',
                initial={ 'calculator_type': worker_type }
            ),
            'worker_calc':  worker_form.content.decode('utf-8'),
        }
    )


@staff_account_required
def position_calculator_form(request):
    calculator = None
    interval_pk = request.GET.get('interval')
    if interval_pk:
        calculator = models.PositionCalculator.objects.get(
            pk=interval_pk
        )

    calculator_type, calculator_form = _render_specific_calculator(
        request,
        calculator.calculator_content_type if calculator else None,
        calculator.calculator if calculator else None,
        None,
        'position'
    )

    return render(
        request,
        'the_redhuman_is/autocharge/position_calculator_form.html',
        {
            'position_form': CalculatorForm(
                auto_id='position_%s',
                initial={ 'calculator_type': calculator_type }
            ),
            'position_calc': calculator_form.content.decode('utf-8')
        }
    )


# GET params: interval, subform_id, calculator_type
@staff_account_required
def calculator_subform(request):
    service_calculator = models.ServiceCalculator.objects.get(
        pk=request.GET['interval']
    )
    amount_calculator = service_calculator.calculator

    subform_id = request.GET['subform_id']

    if 'customer' in subform_id:
        content_type = amount_calculator.customer_content_type if amount_calculator else None
        calculator = amount_calculator.customer_calculator if amount_calculator else None
    elif 'foreman' in subform_id:
        content_type = amount_calculator.foreman_content_type if amount_calculator else None
        calculator = amount_calculator.foreman_calculator if amount_calculator else None
    elif 'worker' in subform_id:
        content_type = amount_calculator.worker_content_type if amount_calculator else None
        calculator = amount_calculator.worker_calculator if amount_calculator else None
    else:
        raise Exception('Unknown subform_id <{}>!'.format(subform_id))

    target_type = request.GET['calculator_type']

    calculator_type, response = _render_specific_calculator(
        request, content_type, calculator, target_type, subform_id)
    return response


@staff_account_required
def position_calculator_subform(request):
    calculator = None
    content_type = None
    interval_pk = request.GET.get('interval')
    if interval_pk:
        position_calculator = models.PositionCalculator.objects.get(
            pk=interval_pk
        )
        calculator = position_calculator.calculator
        content_type = position_calculator.calculator_content_type

    target_type = request.GET['calculator_type']
    subform_id = request.GET['subform_id']

    calculator_type, response = _render_specific_calculator(
        request, content_type, calculator, target_type, subform_id)
    return response


def _hourly_calculator_params(subform_id, params):
    return (
        params['id_tariff_{}'.format(subform_id)],
        params['id_bonus_{}'.format(subform_id)],
        params['id_threshold_{}'.format(subform_id)]
    )


def _turnouts_calculator_params(subform_id, params):

    BOXES_RX1 = re.compile('^id_key_({}_1\S+)$'.format(subform_id))
    BOXES_RX2 = re.compile('^id_key_({}_2\S+)$'.format(subform_id))

    pairs1 = []
    pairs2 = []

    for key in params.keys():
        m = BOXES_RX1.match(key)
        if m:
            value_key = 'id_value_{}'.format(m.group(1))
            k = _get_float(params[key])
            v = _get_float(params[value_key])
            if k is not None and v is not None:
                pairs1.append((k, v))
        else:
            m = BOXES_RX2.match(key)
            if m:
                value_key = 'id_value_{}'.format(m.group(1))
                k = _get_float(params[key])
                v = _get_float(params[value_key])
                if k is not None and v is not None:
                    pairs2.append((k, v))

    params_ = {}

    params_['entry'] = params['id_entry_{}'.format(subform_id)]

    if 'id_tariff_{}_1'.format(subform_id) in params:
        params_['tariff1'] = params['id_tariff_{}_1'.format(subform_id)]
        params_['bonus1'] = params['id_bonus_{}_1'.format(subform_id)]
        params_['threshold1'] = params['id_threshold_{}_1'.format(subform_id)]

    if 'id_tariff_{}_2'.format(subform_id) in params:
        params_['tariff2'] = params['id_tariff_{}_2'.format(subform_id)]
        params_['bonus2'] = params['id_bonus_{}_2'.format(subform_id)]
        params_['threshold2'] = params['id_threshold_{}_2'.format(subform_id)]

    if len(pairs1) > 0:
        params_['pairs1'] = pairs1

    if len(pairs2) > 0:
        params_['pairs2'] = pairs2

    pflp1 = 'id_performance_for_linear_payment_{}_1'.format(subform_id)
    if pflp1 in params:
        params_['lpcoeff1'] = _get_float(
            params['id_linear_payment_coefficient_{}_1'.format(subform_id)]
        )
        params_['pflp1'] = _get_float(params[pflp1])

    pflp2 = 'id_performance_for_linear_payment_{}_2'.format(subform_id)
    if pflp2 in params:
        params_['lpcoeff2'] = _get_float(
            params['id_linear_payment_coefficient_{}_2'.format(subform_id)]
        )
        params_['pflp2'] = _get_float(params[pflp2])

    if 'id_parameter1_{}_1'.format(subform_id) in params:
        params_['parameter11'] = params['id_parameter1_{}_1'.format(subform_id)]
        params_['parameter21'] = params['id_parameter2_{}_1'.format(subform_id)]
        params_['intervals1'] = _get_intervals(subform_id + '_1', params)

    if 'id_parameter1_{}_2'.format(subform_id) in params:
        params_['parameter12'] = params['id_parameter1_{}_2'.format(subform_id)]
        params_['parameter22'] = params['id_parameter2_{}_2'.format(subform_id)]
        params_['intervals2'] = _get_intervals(subform_id + '_2', params)

    return params_


def _foreman_calculator_params(subform_id, params):
    pairs1 = []
    pairs2 = []

    BOXES_RX1 = re.compile('^id_key_({}_1\S+)$'.format(subform_id))
    BOXES_RX2 = re.compile('^id_key_({}_2\S+)$'.format(subform_id))

    for key in params.keys():

        m = BOXES_RX1.match(key)
        if m:
            value_key = 'id_value_{}'.format(m.group(1))
            k = _get_float(params[key])
            v = _get_float(params[value_key])
            if k is not None and v is not None:
                pairs1.append((k, v))
        else:
            m = BOXES_RX2.match(key)
            if m:
                value_key = 'id_value_{}'.format(m.group(1))
                k = _get_float(params[key])
                v = _get_float(params[value_key])
                if k is not None and v is not None:
                    pairs2.append((k, v))

    params_ = {}

    if 'id_tariff_{}_1'.format(subform_id) in params:
        params_['tariff1'] = params['id_tariff_{}_1'.format(subform_id)]
        params_['bonus1'] = params['id_bonus_{}_1'.format(subform_id)]
        params_['threshold1'] = params['id_threshold_{}_1'.format(subform_id)]

    if len(pairs1) > 0:
        params_['pairs1'] = pairs1

    if len(pairs2) > 0:
        params_['pairs2'] = pairs2

    if 'id_parameter1_{}_1'.format(subform_id) in params:
        params_['parameter11'] = params['id_parameter1_{}_1'.format(subform_id)]
        params_['parameter21'] = params['id_parameter2_{}_1'.format(subform_id)]
        params_['intervals1'] = _get_intervals(subform_id + '_1', params)

    return params_


def _get_float(value):
    try:
        value = float(value)
    except Exception as e:
        value = None

    return value


def _get_pairs(subform_id, params):
    pairs = []
    BOXES_RX = re.compile('^id_key_({}\S+)$'.format(subform_id))
    for key in params.keys():
        m = BOXES_RX.match(key)
        if m:
            value_key = 'id_value_{}'.format(m.group(1))
            k = _get_float(params[key])
            v = _get_float(params[value_key])
            if k is not None and v is not None:
                pairs.append((k, v))

    return pairs


def _get_intervals(subform_id, params):
    intervals = []
    INTERVALS_RX = re.compile('^id_begin_({}\S+)'.format(subform_id))
    for key in params.keys():
        m = INTERVALS_RX.match(key)
        if m:
            id_suffix = m.group(1)
            k_key = 'id_k_{}'.format(id_suffix)
            b_key = 'id_b_{}'.format(id_suffix)

            begin = _get_float(params[key])
            k = _get_float(params[k_key]) or 0
            b = _get_float(params[b_key]) or 0

            if begin is not None:
                intervals.append((begin, k, b))

    return intervals


def _by_boxes_calculator_params(subform_id, params):
    return (
        _get_pairs(subform_id, params),
        params.get('id_performance_for_linear_payment_{}'.format(subform_id), None),
        params.get('id_linear_payment_coefficient_{}'.format(subform_id), None)
    )


def _turnout_output_calculator_params(subform_id, params):
    PK_RX = re.compile('^id_pk_({}\S+)$'.format(subform_id))
    prices = []
    for key in params.keys():
        m = PK_RX.match(key)
        if m:
            price_key = 'id_price_{}'.format(m.group(1))
            pk = int(params[key])
            price = _get_float(params[price_key])
            prices.append((pk, price))

    fixed_bonus = params.get('id_fixed_bonus_{}'.format(subform_id))
    bonus_enabled = params.get('id_bonus_{}'.format(subform_id)) == 'true'
    is_side_job = params.get('id_is_side_job_{}'.format(subform_id)) == 'true'

    return fixed_bonus, bonus_enabled, is_side_job, prices


def _calculator_params(subform_id, params):
    calculator_type = params['{}_calculator_type'.format(subform_id)]

    if calculator_type == 'hourly':
        calculator_params = _hourly_calculator_params(subform_id, params)
    elif calculator_type == 'by_boxes':
        calculator_params = _by_boxes_calculator_params(subform_id, params)
    elif calculator_type == 'by_turnouts':
        calculator_params = _turnouts_calculator_params(subform_id, params)
    elif calculator_type == 'hourly_interval':
        calculator_params = _by_boxes_calculator_params(subform_id, params)
    elif calculator_type == 'turnout_output':
        calculator_params = _turnout_output_calculator_params(subform_id, params)
    elif calculator_type == 'foreman':
        calculator_params = _foreman_calculator_params(subform_id, params)
    elif calculator_type == 'foreman_output_sum':
        calculator_params = _get_pairs(subform_id, params)
    elif calculator_type == 'piecewise_linear':
        calculator_params = (
            params['id_parameter1_{}'.format(subform_id)],
            params['id_parameter2_{}'.format(subform_id)],
           _get_intervals(subform_id, params)
        )
    else:
        raise Exception('Unknown calculator type {}!'.format(calculator_type))

    return calculator_type, calculator_params


def _create_signle_turnout_calculator(p1, p2, intervals):
    calculator = models.SingleTurnoutCalculator.objects.create(
        parameter_1=p1,
        parameter_2=p2
    )
    for begin, k, b in intervals:
        calculator.intervals.add(
            models.CalculatorInterval.objects.create(
                begin=begin,
                b=b,
                k=k
            )
        )
    calculator.save()

    return calculator


def _save_calculator(calculator_type, params):
    if calculator_type == 'hourly':
        tariff, bonus, threshold = params
        return models.CalculatorHourly.objects.create(tariff=tariff, bonus=bonus, threshold=threshold)

    elif calculator_type == 'by_turnouts':
        calc1 = None
        calc2 = None

        if 'parameter11' in params and 'parameter12' in params:
            calc1 = _create_signle_turnout_calculator(
                params['parameter11'],
                params['parameter21'],
                params['intervals1']
            )
            calc2 = _create_signle_turnout_calculator(
                params['parameter12'],
                params['parameter22'],
                params['intervals2']
            )
        elif 'tariff1' in params and 'tariff2' in params:
            calc1 = models.CalculatorHourly.objects.create(
                tariff=params['tariff1'],
                bonus=params['bonus1'],
                threshold=params['threshold1'])
            calc2 = models.CalculatorHourly.objects.create(
                tariff=params['tariff2'],
                bonus=params['bonus2'],
                threshold=params['threshold2'])
        elif 'tariff1' in params:
            calc1 = models.CalculatorHourly.objects.create(
                tariff=params['tariff1'],
                bonus=params['bonus1'],
                threshold=params['threshold1'])
            calc2 = models.CalculatorBoxes.objects.create()
        elif 'tariff2' in params:
            calc2 = models.CalculatorHourly.objects.create(
                tariff=params['tariff2'],
                bonus=params['bonus2'],
                threshold=params['threshold2'])
            calc1 = models.CalculatorBoxes.objects.create()
        else:
            calc1 = models.CalculatorBoxes.objects.create()
            calc2 = models.CalculatorBoxes.objects.create()

        if 'pairs1' in params:
            for k, v in params['pairs1']:
                calc1.conditions.add(
                    models.Pair.objects.create(key=k, value=v)
                )
            calc1.performance_for_linear_payment = params['pflp1']
            calc1.coefficient = params['lpcoeff1']
            calc1.save()

        if 'pairs2' in params:
            for k, v in params['pairs2']:
                calc2.conditions.add(
                    models.Pair.objects.create(key=k, value=v)
                )
            calc2.performance_for_linear_payment = params['pflp2']
            calc2.coefficient = params['lpcoeff2']
            calc2.save()

        calculator = models.CalculatorTurnouts.objects.create(
            threshold=params['entry'],
            calc1=calc1,
            calc2=calc2
        )
        calculator.save()

        return calculator

    elif calculator_type == 'by_boxes':
        calculator = models.CalculatorBoxes.objects.create()
        pairs, perf_for_linear_payment, coefficient = params
        for k, v in pairs:
            calculator.conditions.add(
                models.Pair.objects.create(key=k, value=v)
            )
        calculator.performance_for_linear_payment = _get_float(
                perf_for_linear_payment)
        calculator.coefficient = _get_float(coefficient)
        calculator.save()
        return calculator

    elif calculator_type == 'hourly_interval':
        calculator = models.CalculatorHourlyInterval.objects.create()
        for k, v in params:
            calculator.conditions.add(
                models.Pair.objects.create(key=k, value=v)
            )
        calculator.save()
        return calculator

    elif calculator_type == 'turnout_output':
        fixed_bonus, bonus_enabled, is_side_job, boxes = params
        calculator = models.CalculatorOutput.objects.create(
            fixed_bonus=fixed_bonus,
            bonus_enabled=bonus_enabled,
            is_side_job=is_side_job
        )
        for pk, price in boxes:
            box_type = models.BoxType.objects.get(pk=pk)
            models.BoxPrice.objects.create(
                calculator=calculator,
                box_type=box_type,
                price=price
            )
        return calculator

    elif calculator_type == 'foreman_output_sum':
            calculator = models.CalculatorForemanOutputSum.objects.create()
            for k, v in params:
                calculator.conditions.add(
                    models.Pair.objects.create(key=k, value=v)
                )
            calculator.save()
            return calculator

    elif calculator_type == 'foreman':
            calc1 = None

            if 'parameter11' in params:
                calc1 = _create_signle_turnout_calculator(
                    params['parameter11'],
                    params['parameter21'],
                    params['intervals1']
                )
            elif 'tariff1' in params:
                calc1 = models.CalculatorHourly.objects.create(
                    tariff=params['tariff1'],
                    bonus=params['bonus1'],
                    threshold=params['threshold1']
                )
            else:
                calc1 = models.CalculatorBoxes.objects.create()

            calc2 = models.CalculatorForemanWorkers.objects.create()

            if 'pairs1' in params:
                for k, v in params['pairs1']:
                    calc1.conditions.add(
                        models.Pair.objects.create(key=k, value=v)
                    )

            if 'pairs2' in params:
                for k, v in params['pairs2']:
                    calc2.conditions.add(
                        models.Pair.objects.create(key=k, value=v)
                    )

            calculator = models.CalculatorForeman.objects.create(
                calc1=calc1,
                calc2=calc2)
            calculator.save()

            return calculator

    elif calculator_type == 'piecewise_linear':
        p1, p2, intervals = params
        return _create_signle_turnout_calculator(p1, p2, intervals)

    else:
        raise Exception('Unknown calculator type {}!'.format(calculator_type))


@staff_account_required
@transaction.atomic
def save_settings(request):
    if not request.user.is_superuser:
        raise Exception('Недостаточно прав доступа')

    customer_type, customer_params = _calculator_params('customer', request.POST)
    foreman_type, foreman_params = _calculator_params('foreman', request.POST)
    worker_type, worker_params = _calculator_params('worker', request.POST)

    service_calculator_pk = request.POST.get('interval')
    if service_calculator_pk:
        service_calculator = models.ServiceCalculator.objects.get(
            pk=service_calculator_pk
        )
        amount_calculator = service_calculator.calculator
        if amount_calculator.customer_calculator:
            amount_calculator.customer_calculator.delete()
        amount_calculator.customer_calculator = _save_calculator(customer_type, customer_params)

        if amount_calculator.foreman_calculator:
            amount_calculator.foreman_calculator.delete()
        amount_calculator.foreman_calculator = _save_calculator(foreman_type, foreman_params)

        if amount_calculator.worker_calculator:
            amount_calculator.worker_calculator.delete()
        amount_calculator.worker_calculator = _save_calculator(worker_type, worker_params)

        amount_calculator.save()
    else:
        amount_calculator = models.AmountCalculator.objects.create(
            customer_calculator=_save_calculator(customer_type, customer_params),
            foreman_calculator=_save_calculator(foreman_type, foreman_params),
            worker_calculator=_save_calculator(worker_type, worker_params)
        )

        # Todo: закрытие предыдущего интервала?
        # Todo: проверка на то, что интервалы не перекрываются?
        first_day, last_day = get_first_last_day(
            request,
            set_initial=False
        )
        customer_service = models.CustomerService.objects.get(pk=request.POST['service'])

        models.ServiceCalculator.objects.create(
            customer_service=customer_service,
            calculator=amount_calculator,
            first_day=first_day,
            last_day=last_day
        )

    return HttpResponse('ok')


@staff_account_required
@transaction.atomic
def save_position_calculator(request):
    if not request.user.is_superuser:
        raise Exception('Недостаточно прав доступа')

    calculator_type, calculator_params = _calculator_params('position', request.POST)

    position_calculator_pk = request.POST.get('interval')
    if position_calculator_pk:
        position_calculator = models.PositionCalculator.objects.get(
            pk=position_calculator_pk
        )
        position_calculator.calculator = _save_calculator(calculator_type, calculator_params)
        position_calculator.save()
    else:
        customer = models.Customer.objects.get(pk=request.POST['customer'])
        position = models.Position.objects.get(pk=request.POST['position'])
        first_day, last_day = get_first_last_day(
            request,
            set_initial=False,
        )

        models.PositionCalculator.objects.create(
            customer=customer,
            position=position,
            calculator=_save_calculator(calculator_type, calculator_params),
            first_day=first_day,
            last_day=last_day
        )

    return HttpResponse('ok')
