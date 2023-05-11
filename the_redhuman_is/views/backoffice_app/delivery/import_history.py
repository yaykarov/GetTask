from the_redhuman_is.views.backoffice_app.auth import bo_api

from the_redhuman_is.views.delivery import imports_report_data


@bo_api(['GET'])
def import_history(request):
    return imports_report_data(request)
