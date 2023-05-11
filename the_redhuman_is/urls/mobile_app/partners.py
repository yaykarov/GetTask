from django.urls import path

from the_redhuman_is.services.app_flavors import is_app_flavor_master

from the_redhuman_is.views import partners


urlpatterns = []

if is_app_flavor_master():
    urlpatterns.append(
        path(
            'partners_list/',
            partners.list_partners,
            name='mobile_app_list_partners'
        )
    )

