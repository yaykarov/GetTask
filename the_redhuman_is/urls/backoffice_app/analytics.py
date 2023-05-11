from django.urls import path
from the_redhuman_is.views.backoffice_app.analytics import (
    calls,
    requests,
)

urlpatterns = [
    path(
        'delivery_requests/',
        requests.list_requests,
        name='analytics_list_requests',
    ),
    path(
        'calls/',
        calls.list_calls,
        name='analytics_list_calls',
    ),
    path(
        'hours_summary/',
        requests.hours_summary,
        name='analytics_hours_summary',
    ),
    path(
        'calls_turnout_summary/',
        calls.calls_turnout_summary,
        name='analytics_calls_turnout_summary',
    ),
]
