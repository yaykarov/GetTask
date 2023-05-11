from django.http import HttpResponse

from urllib.parse import quote_plus


def xlsx_content_response(workbook, filename):
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response[
        'Content-Disposition'
    ] = "attachment; filename*=UTF-8''{}".format(quote_plus(filename))

    workbook.save(response)

    return response
