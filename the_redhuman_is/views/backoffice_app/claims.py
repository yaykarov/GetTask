from dal.autocomplete import Select2QuerySetView

from rest_framework.views import APIView

from the_redhuman_is.views.backoffice_app.auth import bo_api

from the_redhuman_is.views.claims import (
    create,
    claim_list as old_claim_list,
    worker_turnouts,
)

from utils.date_time import string_from_date


class WorkerTurnoutAutocomplete(Select2QuerySetView, APIView):
    def get_queryset(self):
        return worker_turnouts(self)

    def get_result_label(self, result):
        return '{}, {}'.format(
            string_from_date(result.timesheet.sheet_date),
            result.timesheet.sheet_turn
        )


@bo_api(['POST'])
def create_claim(request):
    return create(request)


@bo_api(['GET'])
def claim_list(request):
    return old_claim_list(request)
