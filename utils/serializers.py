from django.core.exceptions import ValidationError
from django.core.validators import (
    MaxLengthValidator,
    MinLengthValidator,
)
from django.utils.translation import gettext_lazy as _
from rest_framework.fields import (
    CharField,
    DecimalField,
    Field,
    ListField,
)
from rest_framework.serializers import Serializer

from utils.phone import PhonePrefixLengthValidator


class GeopositionField(Serializer):
    lat = DecimalField(max_digits=9, decimal_places=7, max_value=90, min_value=-90)
    lon = DecimalField(max_digits=10, decimal_places=7, max_value=180, min_value=-180)

    def to_internal_value(self, data):
        ret = super(GeopositionField, self).to_internal_value(data)
        return ret['lat'], ret['lon']

    def to_representation(self, instance):
        instance = {
            'lat': instance[0],
            'lon': instance[1],
        }
        return super(GeopositionField, self).to_representation(instance)


class GeopositionListField(ListField):
    child = GeopositionField()


class OnlyDigitsValidator:
    message = 'Строка должна содержать только цифры.'
    code = 'invalid'

    def __call__(self, value):
        if not value.isdigit():
            raise ValidationError(self.message, code=self.code)


class PhoneListField(ListField):
    child = CharField(
        validators=[
            MinLengthValidator(11),
            MaxLengthValidator(12),
            OnlyDigitsValidator(),
            PhonePrefixLengthValidator()
        ],
    )


class ChoiceReprField(Field):
    default_error_messages = {
        'invalid_choice': _('"{input}" is not a valid choice.')
    }

    def __init__(self, choices, **kwargs):
        self._choices = {k: v for k, v in choices}
        self._choices_from = {v: k for k, v in choices}
        self.allow_blank = kwargs.pop('allow_blank', False)
        super().__init__(**kwargs)

    def to_representation(self, value):
        return self._choices[value]

    def to_internal_value(self, data):
        try:
            return self._choices_from[data]
        except KeyError:
            self.fail('invalid_choice', input=data)
