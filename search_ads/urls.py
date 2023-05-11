from django.conf.urls import url
from . import views
from . import dac_view

app_name = "search_ads"
urlpatterns = [
    url(r'^new_hr_report/', views.create_hr_report, name='new_hr_report'),
    url(r'^report_status/', views.get_report_status, name='report_status'),
    url(r'^get_search_results/', views.search, name='get_search_results'),
    url(r'^hr_reports/', views.show_hr_reports, name='hr_reports'),
    url(r'^new_hr_account/', views.new_hr_account, name='new_hr_account'),
    url(r'^hr_site_accounts/', views.hr_site_accounts, name='hr_site_accounts'),

    #автозаполнение
    url(r'^hr-manager-autocomplete/$', dac_view.HrManagerAutocomplete.as_view(), name='hr-manager-autocomplete'),
]