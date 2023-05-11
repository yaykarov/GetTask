import json

from django.http import HttpRequest, HttpResponse
from django.views.decorators.csrf import csrf_exempt

from the_redhuman_is.models.paysheet import TalkBankWebhookRequest
from the_redhuman_is.services.paysheet.talk_bank import (
    on_talkbank_income_registered,
    on_talkbank_income_registration_failed,
)


@csrf_exempt
def on_income_registered(request: HttpRequest) -> HttpResponse:
    TalkBankWebhookRequest.objects.create(request_body=request.body.decode('utf-8'))

    root_data = json.loads(request.body)

    try:
        if root_data.get('type') == 'income.income_register':
            data = root_data.get('data')
            client_id = data.get('client_id')
            income_registration_request_id = data.get('id')
            if data.get('status') == 'sent':
                _ = data.get('receipt_id')
                url = data.get('link')
                on_talkbank_income_registered(
                    tb_client_id=client_id,
                    income_registration_request_id=income_registration_request_id,
                    receipt_url=url,
                )
            elif data.get('status') == 'failed':
                on_talkbank_income_registration_failed(
                    tb_client_id=client_id,
                    income_registration_request_id=income_registration_request_id,
                    errors=json.dumps(data.get('errors')),
                )
    except Exception:
        pass

    return HttpResponse()
