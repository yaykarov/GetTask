from bootstrap_daterangepicker import widgets
from crispy_forms.layout import Submit


class SubmitNoValue(Submit):
    template = 'submit.html'


class DatePickerWidget(widgets.DatePickerWidget):

    def format_value(self, value):
        if isinstance(value, tuple):
            return (
                self._format_date_value(value[0]) +
                self.separator +
                self._format_date_value(value[1])
            )
        else:
            return self._format_date_value(value)
