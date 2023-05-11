from django.conf.urls import url

from applicants import views

from applicants.views import ApplicantCreateView
from applicants.views import ApplicantDetailView
from applicants.views import ApplicantUpdateView
from applicants.views import ApplicantsListView
from applicants.views import ImportApplicant
from applicants.views import ManagerAutocomplete
from applicants.views import SourceAutocomplete
from applicants.views import StatusAutocomplete

app_name = 'applicants'

urlpatterns = [
    url(r'^list/$', ApplicantsListView.as_view(), name='list'),
    url(r'^add/$', ApplicantCreateView.as_view(), name='create'),
    url(r'^detail/(?P<pk>\d+)/$', ApplicantDetailView.as_view(), name='detail'),
    url(r'^update/(?P<pk>\d+)/$', ApplicantUpdateView.as_view(), name='update'),
    url(r'^upload/$', ImportApplicant.as_view(), name='import'),

    url(r'^unassigned_list/$', views.unassigned_list, name='unassigned_list'),
    url(r'^unassigned_count/$', views.unassigned_count, name='unassigned_count'),
    url(r'^assign/(?P<pk>\d+)/$', views.assign, name='assign'),

    url(r'^history/(?P<pk>\d+)/$', views.history, name='history' ),

    url(r'^statuses/$', StatusAutocomplete.as_view(), name='status-autocomplete'),
    url(r'^managers/$', ManagerAutocomplete.as_view(), name='manager_autocomplete'),
    url(r'^sources/$', SourceAutocomplete.as_view(), name='source_autocomplete'),

    url(r'^funnel/$', views.funnel, name='funnel'),
    url(r'^conveyor_report/$', views.conveyor_report, name='conveyor_report'),
    url(r'^conveyor_details/$', views.conveyor_details, name='conveyor_details'),
]
