import django_filters
from bootstrap_daterangepicker.widgets import DateRangeWidget
from dal import autocomplete

from the_redhuman_is.models import Customer
from the_redhuman_is.models.reconciliation import Reconciliation
from utils.filter import BootstrapDateFromToRangeFilter, TypedChoiceFilter
from utils.functools import strtobool
from utils.locale import DATEPICKER_LOCALE


class ReconciliationFilter(django_filters.FilterSet):
    class Meta:
        model = Reconciliation
        fields = []
    filter_customer = django_filters.ModelChoiceFilter(
        label='Клиент',
        field_name='customer',
        queryset=Customer.objects.all(),
        widget=autocomplete.ModelSelect2(
            attrs={'class': 'form-control form-control-sm'},
            url='the_redhuman_is:customer-autocomplete'
        )
    )
    is_unpaid = TypedChoiceFilter(
        label='Оплата',
        field_name='payment_operation',
        lookup_expr='isnull',
        choices=(
            (False, 'Оплаченные'),
            (True, 'Не оплаченные'),
        ),
        coerce=strtobool,
        empty_label='Все'
    )
    is_closed = TypedChoiceFilter(
        label='Акт',
        choices=(
            (True, 'Подписан акт'),
            (False, 'Не подписан акт'),
        ),
        coerce=strtobool,
        empty_label='Все'
    )
    date_range = BootstrapDateFromToRangeFilter(
        label='За период',
        widget=DateRangeWidget(
            attrs={'autocomplete': 'off'},
            format='%d.%m.%Y',
            picker_options={'locale': DATEPICKER_LOCALE},
        ),
        method='filter_date_range',
    )

    @staticmethod
    def filter_date_range(queryset, name, value):
        if value is not None:
            return queryset.filter(first_day__gte=value.start, last_day__lte=value.stop)
        return queryset
