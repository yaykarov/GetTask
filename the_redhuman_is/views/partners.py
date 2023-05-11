from django.http import JsonResponse

from the_redhuman_is import models


def list_partners(request):
    partners = models.MobileAppPartner.objects.all(
    ).values(
        'name',
        'api_entry'
    )

    return JsonResponse({
        'partners': list(partners)
    })
