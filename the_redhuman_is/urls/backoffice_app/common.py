from django.urls import path

from the_redhuman_is.views.backoffice_app import autocomplete
from the_redhuman_is.views.backoffice_app import common


urlpatterns = [
    # autocomplete
    path(
        'customer_autocomplete/',
        autocomplete.CustomerAutocomplete.as_view(),
        name='backoffice_common_customer_autocomplete'
    ),
    path(
        'worker_by_customer_autocomplete/',
        autocomplete.WorkerByCustomerAutocomplete.as_view(),
        name='backoffice_common_worker_by_customer_autocomplete'
    ),
    path(
        'administration_cost_type_autocomplete/',
        autocomplete.AdministrationCostTypeAutocomplete.as_view(),
        name='backoffice_common_administration_cost_type_autocomplete'
    ),
    path(
        'industrial_cost_type_autocomplete/',
        autocomplete.IndustrialCostTypeAutocomplete.as_view(),
        name='backoffice_common_industrial_cost_type_autocomplete'
    ),
    path(
        'material_autocomplete/',
        autocomplete.MaterialAutocomplete.as_view(),
        name='backoffice_common_material_autocomplete'
    ),

    # just commonly used part
    path(
        'menu/',
        common.menu,
        name='backoffice_common_menu'
    ),
]
