from django.urls import path

from the_redhuman_is.views.backoffice_app import expenses


urlpatterns = [
    path(
        'provider_autocomplete/',
        expenses.ProviderAutocomplete.as_view(),
        name='backoffice_expenses_provider_autocomplete'
    ),
    path(
        'expense_autocomplete/',
        expenses.ExpenseByCustomerAutocomplete.as_view(),
        name='backoffice_expenses_expense_autocomplete'
    ),

    path(
        'provider/update/',
        expenses.update_provider,
        name='backoffice_expenses_update_provider'
    ),
    path(
        'provider/detail/',
        expenses.provider_detail,
        name='backoffice_expenses_provider_detail'
    ),
    path(
        'expense/detail/',
        expenses.expense_detail,
        name='backoffice_expenses_expense_detail'
    ),
    path(
        'expense/create/',
        expenses.create_expense,
        name='backoffice_expenses_expense_create'
    ),
    path(
        'expense/update/',
        expenses.update_expense,
        name='backoffice_expenses_expense_update'
    ),
    path(
        'actual_expenses/',
        expenses.actual_expenses,
        name='backoffice_expenses_actual_expenses'
    ),
]
