import json

from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt

from the_redhuman_is.services import rocketchat


# Todo: errors?
@csrf_exempt
def on_new_message(request):
    rocketchat.on_new_agent_message(json.loads(request.body))

    return HttpResponse()
