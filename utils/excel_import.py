import re
from collections import defaultdict, namedtuple
from datetime import (
    date,
    datetime,
    time,
)

import openpyxl.utils
from django.core.exceptions import ValidationError
from django.utils import timezone
from rest_framework.fields import empty


class Field:
    validators = []
    index = None
    title = None
    null_values = {None, '', '-'}

    def validate_empty_values(self, row):
        if self.index is None:
            return True, self.default

        value = row[self.index]
        if value in self.null_values:
            if self.default is not empty:
                return True, self.default
            else:
                raise ValidationError('Значение не может быть пустым.')

        return False, value

    def to_internal_value(self, value):
        return value

    def run_validators(self, value):
        errors = []
        for validator in self.validators:
            try:
                validator(value)
            except ValidationError as ex:
                errors.append(ex)
        if errors:
            raise ValidationError(errors)

    def run_validation(self, row):
        is_empty, value = self.validate_empty_values(row)
        if is_empty:
            return value
        value = self.to_internal_value(value)
        self.run_validators(value)
        if callable(self.formatter):
            value = self.formatter(value)
        return value

    def __init__(self, titles, default=empty, required=True, validators=None, formatter=None):
        if not isinstance(titles, list):
            titles = [titles]
        self.titles = titles
        self.required = required  # is column required
        self.default = default  # replace None values
        self.validators = validators or self.validators
        self.formatter = formatter


class CharField(Field):
    def to_internal_value(self, value):
        value = super(CharField, self).to_internal_value(value)
        return str(value).strip()


class DateField(Field):

    def to_internal_value(self, value):
        value = super(DateField, self).to_internal_value(value)
        if isinstance(value, date):
            if isinstance(value, datetime):
                return value.date()
            return value
        value = value.strip()
        for input_format in self.input_formats:
            try:
                value = datetime.strptime(value, input_format).date()
                return value
            except ValueError:
                pass
        else:
            today = timezone.localdate()
            raise ValidationError(
                'Дата должна быть в одном из форматов: ' +
                ', '.join(
                    today.strftime(input_format) for input_format in self.input_formats
                )
            )

    def __init__(self, *args, input_formats=None, **kwargs):
        self.input_formats = input_formats or ['%d.%m.%Y']
        super(DateField, self).__init__(*args, **kwargs)


class IntegerField(Field):
    def to_internal_value(self, value):
        value = super(IntegerField, self).to_internal_value(value)
        try:
            return int(value)
        except ValueError:
            raise ValidationError('Значение должно быть целым числом.')


class FloatField(Field):
    def to_internal_value(self, value):
        value = super(FloatField, self).to_internal_value(value)
        try:
            return float(value)
        except ValueError:
            raise ValidationError('Значение должно быть целым или дробным числом.')


_INTERVAL_RX = re.compile(r'^(\d\d):(\d\d)-(\d\d):(\d\d)$')


def parse_interval(time_str):
    m = _INTERVAL_RX.match(time_str)
    if m:
        # Todo: timezone?
        begin = time(hour=int(m.group(1)), minute=int(m.group(2)))
        end = time(hour=int(m.group(3)), minute=int(m.group(4)))
        return begin, end
    else:
        raise ValidationError('Значение должно быть в формате 10:00-16:45.')


class TimeIntervalField(CharField):
    def to_internal_value(self, value):
        value = super(TimeIntervalField, self).to_internal_value(value)
        return parse_interval(value)


class BooleanTextField(CharField):
    options = {
        'да': True,
        'нет': False,
    }

    def to_internal_value(self, value):
        value = super(BooleanTextField, self).to_internal_value(value).lower()
        try:
            return self.options[value]
        except KeyError:
            raise ValidationError('Значение должно быть либо "да", либо "нет".')


class Parser:

    Result = namedtuple('Result', ['data', 'errors'])

    def __init__(self, worksheet):
        self._rows = worksheet.iter_rows(values_only=True)
        column_titles = defaultdict(list)

        titles = next(self._rows)
        self.source_column_count = len(titles)

        for idx, title in enumerate(titles):
            title = title.strip()
            if title != '':
                column_titles[title].append(idx)

        self.columns = {}
        for field_name in dir(self):
            field = getattr(self, field_name)
            if not isinstance(field, Field):
                continue
            self.columns[field_name] = field

            for title_variant in field.titles:
                if title_variant in column_titles:
                    if len(column_titles[title_variant]) > 1:
                        raise ValidationError(f'В файле дублируется столбец "{title_variant}".')
                    field.title = title_variant
                    field.index = column_titles[title_variant][0]
                    break
            else:
                if field.required:
                    raise ValidationError(
                        f'В файле нет столбца с заголовком "{field.titles[0]}".'
                    )
                field.title = field.titles[0]
                field.index = None

    def parse_row(self):
        row = next(self._rows)
        result = self.Result({}, defaultdict(list))
        for field_name, field in self.columns.items():
            try:
                result.data[field_name] = field.run_validation(row)
            except ValidationError as ex:
                result.errors[field_name].append(
                    f'{field.title}'
                    f' (столбец {openpyxl.utils.get_column_letter(field.index + 1)}):'
                    f' {ex.message}'
                )
        return result

    def parse_rows(self):
        while True:
            try:
                yield self.parse_row()
            except StopIteration:
                return
