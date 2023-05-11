# -*- coding: utf-8 -*-

from django.conf.urls import url

from the_redhuman_is.views.contracts import ContractorAutocomplete
from the_redhuman_is.views.contracts import ContractorProxyAutocomplete
from the_redhuman_is.views.contracts import attach_image
from the_redhuman_is.views.contracts import contractor_workers
from the_redhuman_is.views.contracts import contractors_summary
from the_redhuman_is.views.contracts import contracts_list
from the_redhuman_is.views.contracts import download_images_for_contracts
from the_redhuman_is.views.contracts import export_csv
from the_redhuman_is.views.contracts import fire
from the_redhuman_is.views.contracts import notification_of_contract_images
from the_redhuman_is.views.contracts import notification_of_termination_images
from the_redhuman_is.views.contracts import notifications_list
from the_redhuman_is.views.contracts import set_contractor
from the_redhuman_is.views.contracts import set_dates


urlpatterns = [
    url(r'^$', contracts_list, name='contracts_list'),
    url(r'^download-notices/(contract|terminate)/$',
        notifications_list,
        name='download_notices'),
    url(r'^download-images-for-contracts/$',
        download_images_for_contracts,
        name='download_images_for_contracts'),
    url(r'^set-dates/$',
        set_dates,
        name='contracts_set_dates'
    ),
    url(r'^fire/$',
        fire,
        name='contracts_fire'
    ),
    url(r'^set-contractor/$',
        set_contractor,
        name='contracts_set_contractor'
    ),
    url(r'^notice/attach-image/$', attach_image, name='attach_notice_image'),
    url(r'^notification_of_contract/(?P<pk>\d+)/photos/$', notification_of_contract_images, name='notification_of_contract_photos'),
    url(r'^notification_of_termination/(?P<pk>\d+)/photos/$', notification_of_termination_images, name='notification_of_termination_photos'),
    url(r'^contractors_summary/$', contractors_summary, name='contractors_summary'),
    url(r'^contractor_workers/$', contractor_workers, name='contractor_workers'),
    url(r'^export_csv/$', export_csv, name='export_contracts_csv'),

    url(r'^contractor-proxy-autocomplete/$', ContractorProxyAutocomplete.as_view(), name='contractor_proxy_autocomplete'),
    url(r'^contractor-autocomplete/$', ContractorAutocomplete.as_view(), name='contractor_autocomplete'),
]
