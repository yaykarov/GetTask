from django.urls import path

from the_redhuman_is.views.backoffice_app import claims

urlpatterns = [
    path(
        'turnout_autocomplete/',
        claims.WorkerTurnoutAutocomplete.as_view(),
        name='backoffice_claims_worker_turnout_autocomplete'
    ),

    path(
        'create/',
        claims.create_claim,
        name='backoffice_claims_create'
    ),
    path(
        'list/',
        claims.claim_list,
        name='backoffice_claims_list'
    ),
]
