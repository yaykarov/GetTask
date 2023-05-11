from django.urls import (
    path,
    include,
)

urlpatterns = [
    path('auth/', include('the_redhuman_is.urls.customer_api.auth')),
    path('delivery/', include('the_redhuman_is.urls.customer_api.delivery')),
]
