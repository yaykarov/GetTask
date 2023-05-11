from django.conf.urls import include
from django.urls import path


urlpatterns = [
    path('auth/', include('the_redhuman_is.urls.backoffice_app.auth')),
    path('claims/', include('the_redhuman_is.urls.backoffice_app.claims')),
    path('common/', include('the_redhuman_is.urls.backoffice_app.common')),
    path('delivery/', include('the_redhuman_is.urls.backoffice_app.delivery')),
    path('expenses/', include('the_redhuman_is.urls.backoffice_app.expenses')),

    # External API
    path('analytics/', include('the_redhuman_is.urls.backoffice_app.analytics')),
    path('export/', include('the_redhuman_is.urls.backoffice_app.export')),
    path('rocketchat/', include('the_redhuman_is.urls.backoffice_app.rocketchat_webhook')),
    path('telephony/', include('the_redhuman_is.urls.backoffice_app.telephony')),
    path('talkbank/', include('the_redhuman_is.urls.backoffice_app.talkbank_webhook')),
]
