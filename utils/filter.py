from collections import OrderedDict
from typing import (
    Optional,
    Tuple,
)

import rest_framework_filters as filters
import django_filters
from django.core.exceptions import ValidationError
from django.forms import (
    BooleanField,
    Field,
)
from django.utils.translation import gettext_lazy as _
from django_filters import Filter
from django_filters.constants import EMPTY_VALUES
from django_filters.fields import ChoiceField
from bootstrap_daterangepicker.fields import DateRangeField
from django_filters.widgets import BooleanWidget
from rest_framework.exceptions import ValidationError as RestValidationError
from rest_framework.settings import api_settings

from utils.functools import (
    nothing,
    strtobool,
)


class BootstrapDateRangeField(DateRangeField):
    def to_python(self, value):
        value = super(BootstrapDateRangeField, self).to_python(value)
        if value == (None, None):
            return None
        return slice(*value)


class BootstrapDateFromToRangeFilter(django_filters.DateFromToRangeFilter):
    field_class = BootstrapDateRangeField

    def __init__(self, *args, **kwargs):
        super(BootstrapDateFromToRangeFilter, self).__init__(*args, **kwargs)
        self.field.input_formats = [self.field.widget.format]


class TypedChoiceField(django_filters.fields.ChoiceField):
    def __init__(self, *args, coerce=nothing, **kwargs):
        self._coerce = coerce
        super().__init__(**kwargs)

    def to_python(self, value):
        if value in self.empty_values:
            return None
        try:
            return self._coerce(value)
        except (ValueError, TypeError, ValidationError):
            raise ValidationError(
                self.error_messages['invalid_choice'],
                code='invalid_choice',
                params={'value': value},
            )

    def valid_value(self, value):
        """Check to see if the provided value is a valid choice."""
        for k, v in self.choices:
            if isinstance(v, (list, tuple)):
                for k2, v2 in v:
                    if value == k2:
                        return True
            else:
                if value == k:
                    return True
        return False


class TypedChoiceFilter(django_filters.ChoiceFilter):
    field_class = TypedChoiceField


class ChoiceInFilter(filters.BaseInFilter, filters.ChoiceFilter):
    pass


class ConvertCSVField(Field):
    default_error_messages = {
        'invalid_choice': _(
            'Select a valid choice. %(value)s is not one of the available choices.'
        ),
    }

    def __init__(self, *, choices, **kwargs):
        super().__init__(**kwargs)
        if isinstance(choices, dict):
            self.choices = choices
        else:
            self.choices = {k: v for k, v in choices}

    def to_python(self, value):
        value = str(value)
        if value not in self.choices:
            raise ValidationError(
                self.error_messages['invalid_choice'],
                code='invalid_choice',
                params={'value': value},
            )
        else:
            return self.choices[value]


class ChoiceInConvertFilter(ChoiceInFilter):
    field_class = ConvertCSVField


class CompactMultipleChoiceField(Field):
    default_error_messages = {
        #  look at parent class for translation how-to
        'invalid': 'Value must be integer or comma-separated list of integers.'
    }

    def to_python(self, value):
        if value in self.empty_values:
            return None
        try:
            value = [int(e) for e in value.split(',')]
        except ValueError:
            raise ValidationError(self.error_messages['invalid'], code='invalid')
        return value


class CompactChoiceFilter(Filter):
    field_class = CompactMultipleChoiceField

    def filter(self, qs, value):
        if value in EMPTY_VALUES:
            return qs
        lookup = '%s__%s' % (self.field_name, 'in')
        qs = self.get_method(qs)(**{lookup: value})
        return qs


class StrictBooleanWidget(BooleanWidget):
    def value_from_datadict(self, data, files, name):
        return data.get(name, None)


class StrictBooleanField(BooleanField):
    def to_python(self, value):
        try:
            return strtobool(value)
        except ValueError:
            raise ValidationError('Допустимые значения: true, false или null.')

    def validate(self, value):
        if value is None and self.required:
            raise ValidationError(self.error_messages['required'], code='required')


class BooleanFilter(filters.BooleanFilter):
    field_class = StrictBooleanField

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('widget', StrictBooleanWidget)

        super().__init__(*args, **kwargs)


class FilterSet(filters.FilterSet):
    @classmethod
    def get_filter_subset(cls, params, rel=None):
        """
        Same as parent class but keeps a filter if it's required.
        """
        filter_names = {cls.get_param_filter_name(param, rel) for param in params}
        filter_names = {f for f in filter_names if f is not None}
        return OrderedDict(
            (k, v) for k, v in cls.base_filters.items() if k in filter_names or v.field.required
        )

    @property
    def form(self):
        return super(django_filters.FilterSet, self).form

    @property
    def qs(self):
        if not hasattr(self, '_qs'):
            if not self.is_valid():
                if '__all__' in self.errors:
                    self.errors[api_settings.NON_FIELD_ERRORS_KEY] = self.errors.pop('__all__')
                raise RestValidationError(self.errors)
            qs = self.queryset.all()
            self._qs = self.filter_queryset(qs)
        return self._qs


class ConsistentOrderingFilter(django_filters.OrderingFilter):
    """
    Adds discriminator as a final sorting argument
    to produce deterministic output.
    """

    default_discriminator = ('pk',)

    def __init__(self, discriminator: Optional[Tuple[str]], *args, **kwargs):
        if discriminator is None:
            self.discriminator = self.default_discriminator
        else:
            self.discriminator = discriminator
        super(ConsistentOrderingFilter, self).__init__(*args, **kwargs)

    def filter(self, qs, value):
        if value in EMPTY_VALUES:
            ordering = []
        else:
            ordering = [self.get_ordering_value(param) for param in value]

        ordering.extend(self.discriminator)

        return qs.order_by(*ordering)
