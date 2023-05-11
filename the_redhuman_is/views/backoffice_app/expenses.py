from the_redhuman_is.dac_view import (
    expenses_by_customer,
    providers,
)

from the_redhuman_is import models

from the_redhuman_is.views.backoffice_app.auth import bo_api
from the_redhuman_is.views.backoffice_app.autocomplete import Select2QuerySetAPIView

from the_redhuman_is.views.expenses import (
    actual_expenses as old_actual_expenses,
    create_expense as old_create_expense,
    expense_detail as old_expense_detail,
    provider_detail as old_provider_detail,
    update as old_update_expense,
    update_provider as old_update_provider,
)


class ProviderAutocomplete(Select2QuerySetAPIView):
    queryset = models.Provider.objects.all().order_by('name')

    def get_queryset(self):
        return providers(self)


class ExpenseByCustomerAutocomplete(Select2QuerySetAPIView):
    queryset = models.Expense.objects.all(
    ).order_by(
        'pk'
    ).select_related(
        'provider'
    )

    def get_queryset(self):
        return expenses_by_customer(self)

    def get_result_label(self, item):
        return 'Расход №{}, {}, {}р. {}'.format(
            item.pk,
            item.provider.name,
            item.amount,
            item.comment
        )


@bo_api(['POST'])
def update_provider(request):
    return old_update_provider(request)


@bo_api(['GET'])
def provider_detail(request):
    return old_provider_detail(request)


@bo_api(['POST'])
def create_expense(request):
    return old_create_expense(request)


@bo_api(['POST'])
def update_expense(request):
    return old_update_expense(request)


@bo_api(['GET'])
def actual_expenses(request):
    return old_actual_expenses(request)


@bo_api(['GET'])
def expense_detail(request):
    return old_expense_detail(request)
