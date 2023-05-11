from the_redhuman_is.views.backoffice_app.auth import bo_api

from the_redhuman_is.views.delivery import requests_count_report_data


@bo_api(['GET'])
def request_count(request):
    return requests_count_report_data(request)
