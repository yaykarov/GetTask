# -*- coding: utf-8 -*-

from django.conf.urls import url
from django.urls import path

from the_redhuman_is.views import absent
from the_redhuman_is.views import banks
from the_redhuman_is.views import catalogs
from the_redhuman_is.views import customer_summary
from the_redhuman_is.views import delivery
from the_redhuman_is.views import generic
from the_redhuman_is.views import operating_account
from the_redhuman_is.views import reports
from the_redhuman_is.views import self_employment
from the_redhuman_is.views import staff_turnover
from the_redhuman_is.views import utils

from the_redhuman_is import _0_views
from the_redhuman_is import _1_orders_views
from the_redhuman_is import _2_0_staff_views
from the_redhuman_is import _2_1_worker_detail_views
from the_redhuman_is import _3_cashier_views
from the_redhuman_is import _4_customer_views
from the_redhuman_is import _5_finance_views
from the_redhuman_is import _6_recruitment_views
from the_redhuman_is import dac_view


urlpatterns = [
    # Меню
    url(r'^$', generic.main, name='main'),
    url(r'^base/$', _0_views.base, name='base'),
    url(r'^check-auth/$', generic.check_auth, name='check_auth'),

    url(r'^orders-dashboard/$', _0_views.orders_dashboard,
        name='orders_dashboard'),

    path('customers/', _0_views.customer_list, name='customer_list'),
    path(
        'customer/<int:pk>/contract_scans/',
        _0_views.customer_contract_scans,
        name='customer_contract_scans'
    ),
    path(
        'customer/<int:pk>/add_contract_scans/',
        _0_views.add_customer_contract_scans,
        name='customer_add_contract_scans'
    ),

    url(r'^cashier-workspace/$', _0_views.cashier_workspace,
        name='cashier_workspace'),

    # Deprecated
    url(r'^recruitment/$', _0_views.recruitment, name='recruitment'),

    url(r'^logout/$', generic.logout, name='logout'),

    # Deprecated?
    url(r'^landing_login/$', generic.landing_login, name='landing_login'),

    # Заявки
    url(r'^manage-order/$', _1_orders_views.manage_order, name='manage_order'),
    url(r'^new-orders/$', _1_orders_views.new_orders, name='new_orders'),
    url(r'^list-orders/$', _1_orders_views.list_orders, name='list_orders'),
    url(r'^unexecuted-orders/$', _1_orders_views.unexecuted_orders, name='unexecuted_orders'),
    url(r'^executed-orders/$', _1_orders_views.executed_orders, name='executed_orders'),
    url(r'^unexecuted_timesheets/$', _1_orders_views.unexecuted_timesheets, name='unexecuted_timesheets'),
    url(r'^unexecuted-timesheets-hours-not/$', _1_orders_views.unexecuted_timesheets_hours_not, name='unexecuted_timesheets_hours_not'),
    url(r'^empty-timesheets/$', _1_orders_views.empty_timesheets, name='empty_timesheets'),
    url(r'^execute_timesheets/$', _1_orders_views.execute_timesheets, name='execute_timesheets'),
    url(r'^timesheet/(?P<pk>[0-9]+)/add-hours/$', _1_orders_views.add_hours, name='add_hours'),

    # Табели (детализация)
    url(r'^new-timesheet/(?P<pk>[0-9]+)/$', _1_orders_views.new_timesheet, name='new_timesheet'),
    url(r'^new-timesheet-to-close/(?P<pk>[0-9]+)/$', _1_orders_views.new_timesheet_to_close, name='new_timesheet_to_close'),
    url(r'^timesheets/$', _1_orders_views.timesheets, name='timesheets'),
    url(r'^timesheets/range/', _1_orders_views.range_timesheets, name='range_timesheets'),
    url(r'^timesheets/locations/', _1_orders_views.timesheet_locations, name='timesheet_locations'),
    url(r'^timesheet/(?P<pk>\d+)/$', _1_orders_views.timesheet, name='timesheet'),
    url(r'^timesheet/(?P<pk>\d+)/edit/$', _1_orders_views.edit_timesheet, name='edit_timesheet'),
    url(
        r'^timesheet/(?P<timesheet_pk>\d+)/remove_worker/(?P<worker_pk>\d+)/$',
        _1_orders_views.remove_worker,
        name='timesheet_remove_worker'
    ),
    url(r'^timesheet/(?P<pk>[0-9]+)/image/$', _1_orders_views.timesheet_image, name='timesheet_image'),
    url(r'^timesheet/(?P<pk>[0-9]+)/image2/$', _1_orders_views.timesheet_image2, name='timesheet_image2'),
    url(r'^timesheet/(?P<pk>[0-9]+)/image3/$', _1_orders_views.timesheet_image3, name='timesheet_image3'),
    url(r'^timesheet/(?P<pk>[0-9]+)/image4/$', _1_orders_views.timesheet_image4, name='timesheet_image4'),
    url(r'^timesheet/(?P<pk>[0-9]+)/open/$', _1_orders_views.open_timesheet, name='timesheet_open'),
    url(r'^timesheet/(?P<pk>[0-9]+)/close/$', _1_orders_views.close_timesheet, name='timesheet_close'),

    url(r'^new-contracts/$', _1_orders_views.new_contracts, name='new_contracts'),

    # Списки рабочих
    url(r'^list-workers/$', _2_0_staff_views.list_workers, name='list_workers'),
    url(r'^notice-download-status/$',
        _2_0_staff_views.notice_download_status,
        name='notice_download_status'),

    # Детализация рабочего
    url(r'^new-worker/$', _2_1_worker_detail_views.new_worker, name='new_worker'),
    url(r'^worker/(?P<pk>[0-9]+)/$', _2_1_worker_detail_views.worker_detail, name='worker_detail'),
    path('worker/my/', _2_1_worker_detail_views.my_page, name='my_page'),
    url(r'^worker/(?P<pk>[0-9]+)/edit/(?P<msg>.+)?$', _2_1_worker_detail_views.worker_edit, name='worker_edit'),  # fixme
    url(r'^worker/(?P<pk>[0-9]+)/delete/$', _2_1_worker_detail_views.worker_del, name='worker_del'),
    url(r'^worker/(?P<pk>[0-9]+)/new-passport/$', _2_1_worker_detail_views.new_passport, name='new_passport'),
    url(r'^worker/(?P<pk>[0-9]+)/edit-passport/$', _2_1_worker_detail_views.edit_passport, name='edit_passport'),
    url(r'^worker/(?P<pk>[0-9]+)/new-registration/$', _2_1_worker_detail_views.new_registration, name='new_registration'),
    url(r'^worker/(?P<pk>[0-9]+)/edit-registration/$', _2_1_worker_detail_views.edit_registration, name='edit_registration'),
    url(r'^worker/(?P<pk>[0-9]+)/new-patent/$', _2_1_worker_detail_views.new_patent, name='new_patent'),
    url(r'^worker/(?P<pk>[0-9]+)/edit-patent/$', _2_1_worker_detail_views.edit_patent, name='edit_patent'),
    url(r'^worker/(?P<worker_pk>[0-9]+)/snils/$', _2_1_worker_detail_views.snils, name='worker_snils'),
    url(r'^worker/(?P<worker_pk>[0-9]+)/save_snils/$', _2_1_worker_detail_views.save_snils, name='worker_save_snils'),
    url(r'^worker/(?P<worker_pk>[0-9]+)/self_employment_data/$', _2_1_worker_detail_views.self_employment_data, name='worker_self_employment_data'),
    path('worker/<int:worker_pk>/save_self_employment_data/', _2_1_worker_detail_views.save_self_employment_data, name='worker_save_self_employment_data'),
    url(r'^new-contract/(?P<pk>[0-9]+)/$', _2_1_worker_detail_views.new_contract, name='new_contract'),
    url(r'^edit-contract/(?P<pk>[0-9]+)/$', _2_1_worker_detail_views.edit_contract, name='edit_contract'),
    url(r'^contract/(?P<pk>[0-9]+)/image/$', _2_1_worker_detail_views.contract_image, name='contract_image'),
    url(r'^contract/(?P<pk>[0-9]+)/image2/$', _2_1_worker_detail_views.contract_image2, name='contract_image2'),
    url(r'^contract/(?P<pk>[0-9]+)/image3/$', _2_1_worker_detail_views.contract_image3, name='contract_image3'),

    url(r'^med_card/(?P<pk>[0-9]+)/image/$', _2_1_worker_detail_views.med_card_image, name='med_card_image'),
    url(r'^med_card/(?P<pk>[0-9]+)/image2/$', _2_1_worker_detail_views.med_card_image2, name='med_card_image2'),
    url(r'^med_card/(?P<pk>[0-9]+)/image3/$', _2_1_worker_detail_views.med_card_image3, name='med_card_image3'),

    url(r'^worker/(?P<pk>[0-9]+)/add_med_card/$', _2_1_worker_detail_views.worker_add_med_card, name='worker_add_med_card'),
    url(r'^worker/(?P<pk>[0-9]+)/edit_med_card/$', _2_1_worker_detail_views.worker_edit_med_card, name='worker_edit_med_card'),

    url(r'^worker/(?P<pk>[0-9]+)/return_deposit/$', _2_1_worker_detail_views.return_deposit, name='worker_return_deposit'),
    url(
        r'^worker/(?P<worker_pk>\d+)/link_applicant/(?P<applicant_pk>\d+)/$',
        _2_1_worker_detail_views.link_applicant,
        name='worker_link_applicant'
    ),
    url(
        r'^worker/(?P<worker_pk>\d+)/remove_applicant_link/',
        _2_1_worker_detail_views.remove_applicant_link,
        name='worker_remove_applicant_link'
    ),
    url(
        r'^worker/(?P<worker_pk>\d+)/create_user/',
        _2_1_worker_detail_views.create_user,
        name='worker_create_user'
    ),
    url(
        r'^worker/search/',
        _2_1_worker_detail_views.search_worker,
        name='worker_search'
    ),

    url(r'^photo/(?P<pk>[0-9]+)/$', _2_1_worker_detail_views.get_photo,
        name='get_photo'),

    url(r'^self_employment/$', self_employment.SelfEmploymentView.as_view(), name='self_employment_list'),
    url(r'^self_employment/data/$', self_employment.selfemployment_json_data, name='self_employment_data'),
    url(r'^self_employment/toggle/$', self_employment.selfemployment_json_toggle, name='self_employment_toggle'),

    # Касса
    url(r'^download-acts/(?P<pk>[0-9]+)/$', _3_cashier_views.download_acts, name='download_acts'),
    url(r'^create-operation/(?P<item>[0-9]+)/$', _3_cashier_views.create_operation, name='create_operation'),
    url(r'^to-pay-salary/(?P<pk>[0-9]+)/(?P<msg>[\w\s]+)?$', _3_cashier_views.to_pay_salary, name='to_pay_salary'),  # fixme
    url(r'^to-pay-salary/$', operating_account.salary_proxy, name='to_pay_salary_proxy'),
    url(r'^all-acts-status-change/(?P<pk>[0-9]+)/$', _3_cashier_views.all_acts_status_change, name='all_acts_status_change'),
    url(r'^choose-operation/$', _3_cashier_views.choose_operation, name='choose_operation'),
    url(r'^acts/$', _3_cashier_views.acts, name='acts'),
    url(r'^add-act-into-rko/(?P<pk>[0-9]+)/(?P<pk_rko>[0-9]+)/$', _3_cashier_views.add_act_into_rko, name='add_act_into_rko'),
    url(r'^download-rko/(?P<pk>[0-9]+)/$', _3_cashier_views.download_rko, name='download_rko'),
    url(r'^form-acts/(?P<pk>[0-9]+)/$', _3_cashier_views.form_acts, name='form_acts'),
    url(r'^form-po/(?P<pk>[0-9]+)/$', _3_cashier_views.form_po, name='form_po'),
    url(r'^create-rko/(?P<pk>[0-9]+)/$', _3_cashier_views.create_rko, name='create_rko'),

    # Клиенты
    url(r'^new-customer/$', _4_customer_views.new_customer, name='new_customer'),
    url(r'^customer/(?P<pk>[0-9]+)/$', _4_customer_views.customer_detail, name='customer_detail'),
    url(r'^customer/(?P<pk>[0-9]+)/new_comment/$', _4_customer_views.new_comment, name='new_comment'),
    url(r'^customer/(?P<pk>[0-9]+)/edit/$', _4_customer_views.customer_edit, name='customer_edit'),
    url(r'^customer/(?P<pk>[0-9]+)/new-locations/$', _4_customer_views.new_locations, name='new_locations'),
    url(r'^customer/(?P<pk>[0-9]+)/new-representatives/$', _4_customer_views.new_representatives, name='new_representatives'),
    url(r'^customer/(?P<pk>[0-9]+)/add_service/$', _4_customer_views.add_service, name='customer_add_service'),
    url(r'^customer/(?P<pk>[0-9]+)/add_mmanager/$', _4_customer_views.add_mmanager, name='customer_add_mmanager'),
    url(r'^customer/(?P<pk>[0-9]+)/add_dmanager/$', _4_customer_views.add_dmanager, name='customer_add_dmanager'),
    url(r'^customer/(?P<pk>[0-9]+)/set_deposit_amount/', _4_customer_views.set_deposit_amount, name='customer_set_deposit_amount'),
    url(r'^customer/(?P<pk>[0-9]+)/clear_deposit_setting/', _4_customer_views.clear_deposit_setting, name='customer_clear_deposit_setting'),
    url(r'^customer/service_assortment_list/(?P<pk>\d+)/$', _4_customer_views.service_assortment_list, name='customer_service_assortment_list'),
    url(r'^customer_service/(?P<pk>\d+)/add_assortment/$', _4_customer_views.service_add_assortment, name='service_add_assortment'),
    url(r'^customer/(?P<pk>[0-9]+)/set_debts_first_day/$', _4_customer_views.set_debts_first_day, name='customer_set_debts_first_day'),
    url(
        r'^customer/(?P<pk>\d+)/add_legal_entity/$',
        _4_customer_views.add_legal_entity,
        name='customer_add_legal_entity'
    ),

    # Учет
    url(r'^account/(?P<pk>[0-9]+)/$', _5_finance_views.account_detail, name='account_detail'),
    url(r'^accs-to-all/$', _5_finance_views.accs_to_all, name='accs_to_all'),
    url(r'^70-detalisation/$', _5_finance_views.detalisation_70, name='detalisation_70'),
    url(r'^make-payroll/$', _5_finance_views.make_payroll, name='make_payroll'),
    url(r'^expense_page/$', _5_finance_views.expense_page, name='expense_page'),
    url(r'^expense_page/make/', _5_finance_views.make_expense, name='make_expense'),
    url(r'^expense_page/user_operations/$', _5_finance_views.get_user_operations, name='get_user_operations'),
    url(r'^expense_page/edit/', _5_finance_views.user_operation_edit, name='edit_expense'),

    # Закрытие месяца
    url(r'^period_close/document/$', _5_finance_views.period_close_document, name='period_close_document'),
    path(r'period_close/ajax/action/', _5_finance_views.ajax_close_document_actions, name='period_close_document_action_ajax'),
    path(r'period_close/ajax/data/', _5_finance_views.ajax_get_close_documents, name='period_get_close_documents_ajax'),

    # Подбор
    url(r'^recruitment-at-work/$', _6_recruitment_views.recruitment_at_work, name='recruitment_at_work'),
    url(r'^recruitment-order/(?P<pk>[0-9]+)/$', _6_recruitment_views.recruitment_order, name='recruitment_order'),
    url(r'^add-worker-into-order/(?P<pk_o>[0-9]+)/(?P<pk_w>[0-9]+)/$', _6_recruitment_views.add_worker_into_order, name='add_worker_into_order'),
    url(r'^clarify-worker-data/(?P<pk>[0-9]+)/$', _6_recruitment_views.clarify_worker_data, name='clarify_worker_data'),

    # Автозаполнение
    url(r'^worker-autocomplete/$', dac_view.WorkerAutocomplete.as_view(), name='worker-autocomplete'),
    url(r'^all-worker-autocomplete/$', dac_view.AllWorkersAutocomplete.as_view(), name='all-worker-autocomplete'),
    url(r'^accountable-person-autocomplete/$', dac_view.AccountablePersonAutocomplete.as_view(), name='accountable-person-autocomplete'),
    url(r'^worker-with-contract-autocomplete/$', dac_view.WorkerWithContractAutocomplete.as_view(), name='worker_with_contract_autocomplete'),
    url(r'^worker-without-contract-autocomplete/$', dac_view.WorkerWithoutContractAutocomplete.as_view(), name='worker_without_contract_autocomplete'),
    url(
        r'^worker-by-customer-autocomplete/$',
        dac_view.WorkerWithCustomerAutocomplete.as_view(),
        name='worker-by-customer-autocomplete'
    ),

    url(r'^foreman-autocomplete/$', dac_view.ForemanAutocomplete.as_view(), name='foreman-autocomplete'),

    url(r'^customer-autocomplete/$', dac_view.CustomerAutocomplete.as_view(), name='customer-autocomplete'),
    url(r'^customer-repr-autocomplete/$', dac_view.CustomerReprAutocomplete.as_view(), name='customer-repr-autocomplete'),
    url(r'^customer-location-autocomplete/$', dac_view.CustomerLocationAutocomplete.as_view(), name='customer-location-autocomplete'),
    url(r'^actual-customer-location-autocomplete/$', dac_view.ActualCustomerLocationAutocomplete.as_view(), name='actual-location-autocomplete'),
    url(r'^customer-service-autocomplete/$', dac_view.CustomerServiceAutocomplete.as_view(), name='customer-service-autocomplete'),

    url(r'^service-autocomplete/$', dac_view.ServiceAutocomplete.as_view(), name='service-autocomplete'),

    url(r'^metro-autocomplete-from-list/$', dac_view.MetroAutocomplete.as_view(), name='metro-autocomplete-from-list'),
    url(r'^country-autocomplete/$', dac_view.CountryAutocomplete.as_view(), name='country-autocomplete'),
    url(r'^position-autocomplete/$', dac_view.PositionAutocomplete.as_view(), name='position-autocomplete'),

    url(r'^position-d-minus-autocomplete/$', dac_view.PositionDMinusAutocomplete.as_view(), name='position-d-minus-autocomplete'),
    url(r'^position-m-minus-autocomplete/$', dac_view.PositionMMinusAutocomplete.as_view(), name='position-m-minus-autocomplete'),

    url(r'^m_manager_position-autocomplete/$', dac_view.MManagerPositionAutocomplete.as_view(), name='m_manager_position-autocomplete'),
    url(r'^d_manager_position-autocomplete/$', dac_view.DManagerPositionAutocomplete.as_view(), name='d_manager_position-autocomplete'),

    url(r'^m_manager-autocomplete/$', dac_view.MaintenanceManagerAutocomplete.as_view(), name='m_manager-autocomplete'),
    url(r'^d_manager-autocomplete/$', dac_view.DevelopmentManagerAutocomplete.as_view(), name='d_manager-autocomplete'),

    url(r'^finance-account-autocomplete/$', dac_view.FinanceAccountAutocomplete.as_view(), name='finance-account-autocomplete'),
    url(r'^finance-account-for-paysheet-autocomplete/$', dac_view.FinanceAccountForPaysheetAutocomplete, name='finance-account-for-paysheet-autocomplete'),
    url(r'^bank-service-autocomplete/$', dac_view.BankServiceAutocomplete.as_view(), name='bank-service-autocomplete'),
    url(r'^vacant-location-autocomplete/$',
        dac_view.VacantCustomerLocationAutocomplete.as_view(),
        name='vacant-customer-location-autocomplete'
    ),
    url(
        r'^legal-entity-autocomplete/$',
        dac_view.LegalEntityAutocomplete.as_view(),
        name='legal-entity-autocomplete'
    ),
    url(
        r'^administration-cost-type-autocomplete/$',
        dac_view.AdministrationCostTypeAutocomplete.as_view(),
        name='administration-cost-type-autocomplete'
    ),
    url(
        r'^industrial-cost-type-autocomplete/$',
        dac_view.IndustrialCostTypeAutocomplete.as_view(),
        name='industrial-cost-type-autocomplete'
    ),
    url(
        r'^provider-autocomplete/$',
        dac_view.ProviderAutocomplete.as_view(),
        name='provider-autocomplete'
    ),
    url(
        r'^expense-autocomplete/$',
        dac_view.ExpenseAutocomplete.as_view(),
        name='expense-autocomplete'
    ),
    url(
        r'^expense-by-customer-autocomplete/$',
        dac_view.ExpenseByCustomerAutocomplete.as_view(),
        name='expense-by-customer-autocomplete',
    ),
    url(
        r'^material-autocomplete/$',
        dac_view.MaterialAutocomplete.as_view(),
        name='material-autocomplete',
    ),

    # Экспорт
    url(r'^export-deeds/xls/$', _5_finance_views.export_deeds_xls, name='export_deeds_xls'),
    url(r'^export-rkos-xls/xls/$', _5_finance_views.export_rkos_xls, name='export_rkos_xls'),
    url(r'export_workers/$', _2_0_staff_views.export_workers, name='export_workers'),

    # New finances
    url(
        r'^operating_account/tree/$',
        operating_account.tree,
        name='operating_account_tree'
    ),
    url(
        r'^operating_account/cache_clear/$',
        operating_account.cache_clear,
        name='operating_account_cache_clear'
    ),
    url(
        r'^operating_account/tree_json/(?P<pk>-?[0-9]+)/$',
        operating_account.tree_json,
        name='operating_account_tree_json'
    ),
    url(
        r'^operating_account/(?P<pk>[0-9]+)/detail/$',
        operating_account.detail,
        name='operating_account_detail'
    ),
    url(
        r'^operating_account/(?P<pk>[0-9]+)/detail/json/$',
        operating_account.detail_json,
        name='operating_account_detail_json'
    ),
    url(
        r'^operating_account/detail/',
        operating_account.total_detail,
        name='account_total_detail'
    ),
    url(
        r'^operating_account/add_operation/$',
        operating_account.add_operation,
        name='operating_account_add_operation'
    ),

    # Catalogs
    url(r'^catalogs/$', catalogs.index, name='catalogs'),

    url(r'^catalogs/metro/$', catalogs.metro, name='catalog_metro'),
    url(r'^catalogs/metro_new/$', catalogs.metro_new, name='catalog_metro_new'),
    url(r'^catalogs/ajax_metro_new/$', catalogs.ajax_metro_new, name='ajax_metro_new'),
    url(r'^catalogs/manage_metro_new/', catalogs.manage_metro_new, name='manage_metro_new'),
    url(r'^catalogs/metro/create/$', catalogs.metro_create, name='metro_create'),
    url(r'^catalogs/metro/manage_metro/$', catalogs.manage_metro, name='manage_metro'),

    url(r'^catalogs/country/$', catalogs.country, name='catalog_country'),
    url(r'^catalogs/country/create/$', catalogs.country_create, name='country_create'),
    url(r'^catalogs/country/manage_country/$', catalogs.manage_country, name='manage_country'),

    url(r'^catalogs/position/$', catalogs.position, name='catalog_position'),
    url(r'^catalogs/position/create/$', catalogs.position_create, name='position_create'),
    url(r'^catalogs/metro/manage_position/$', catalogs.manage_position, name='manage_position'),

    url(r'^catalogs/maintenance_manager_position/$', catalogs.m_manager_position, name='m_manager_position'),
    url(r'^catalogs/maintenance_manager_position/manage/$', catalogs.manage_m_manager_position, name='manage_m_manager_position'),

    url(r'^catalogs/development_manager_position/$', catalogs.d_manager_position, name='d_manager_position'),
    url(r'^catalogs/development_manager_position/manage/$', catalogs.manage_d_manager_position, name='manage_d_manager_position'),

    url(r'^catalogs/creditor/$', catalogs.creditor, name='catalog_creditor'),
    url(r'^catalogs/creditor/manage_creditor/$', catalogs.manage_creditor, name='manage_creditor'),

    url(r'^catalogs/administration_cost_type/$', catalogs.administration_cost_type, name='catalog_administration_cost_type'),
    url(r'^catalogs/administration_cost_type/manage_administration_cost_type/$', catalogs.manage_administration_cost_type, name='manage_administration_cost_type'),

    url(r'^catalogs/industrial_cost_type/$', catalogs.industrial_cost_type, name='catalog_industrial_cost_type'),
    url(r'^catalogs/industrial_cost_type/manage_industrial_cost_type/$', catalogs.manage_industrial_cost_type, name='manage_industrial_cost_type'),
    url(r'^catalogs/accountable_persons/', catalogs.accountable_persons, name='accountable_persons'),
    url(r'^catalogs/manage_accountable_persons/', catalogs.manage_accountable_persons, name='manage_accountable_persons'),

    url(r'^catalogs/applicant/status/$', catalogs.applicant_status,
        name='catalog_applicant_status'),

    url(r'^catalogs/applicant/status/ajax/$', catalogs.applicant_status_ajax,
        name='catalog_applicant_status_ajax'),

    url(r'^catalogs/applicant/status/manage/$',
        catalogs.applicant_status_manage,
        name='catalog_applicant_status_manage_ajax'),
    url(r'^catalogs/applicant/status/delete/$',
        catalogs.applicant_status_delete,
        name='catalog_applicant_status_delete_ajax'),

    url(r'^catalogs/applicant/sources/$', catalogs.applicant_sources,
        name='catalog_applicant_sources'),
    url(r'^catalogs/applicant/sources/manage/$',
        catalogs.applicant_sources_manage,
        name='catalog_applicant_sources_manage'),

    url(r'^catalogs/applicant/locations/$', catalogs.applicant_locations,
        name='catalog_applicant_locations'),
    url(r'^catalogs/applicant/locations/manage/$',
        catalogs.applicant_locations_manage,
        name='catalog_applicant_locations_manage'),

    url(r'^catalogs/legal_entities/$', catalogs.legal_entities, name='catalog_legal_entities'),
    url(r'^catalogs/legal_entity/create/$', catalogs.create_legal_entity, name='catalog_create_legal_entity'),
    url(r'^catalogs/legal_entity/(?P<pk>\d+)/delete/$', catalogs.delete_legal_entity, name='catalog_delete_legal_entity'),

    # Banks
    url(r'^banks/$', banks.index, name='banks'),
    url(r'^banks/manage_bank/$', banks.manage_bank, name='manage_bank'),

    url(r'^banks/service_types/$', banks.service_type, name='bank_service_type'),
    url(r'^banks/manage_service_type', banks.manage_service_type, name='manage_bank_service_type'),

    url(r'^banks/services/(?P<bank_pk>[0-9]+)/$', banks.service, name='bank_service'),
    url(r'^banks/manage_service/(?P<bank_pk>[0-9]+)/', banks.manage_service, name='manage_bank_service'),
    url(r'^banks/edit_service/', banks.edit_service, name='edit_bank_service'),

    # Worker Documents
    url(r'^workers_documents/$', view=_0_views.workers_documents, name='workers_documents'),
    url(r'^worker_photos/(?P<pk>[0-9]+)/$', view=_0_views.worker_photos, name='worker_photos'),
    url(r'^med_card_photos/(?P<pk>[0-9]+)/$', view=_0_views.med_card_photos, name='med_card_photos'),
    url(r'^contracts_photos/(?P<pk>[0-9]+)/$', view=_0_views.contracts_photos, name='contracts_photos'),

    url(r'^ajax/worker/$', view=_0_views.ajax_worker, name='ajax_worker'),
    url(r'^ajax/worker_contract/$', view=_0_views.ajax_worker_contract,
        name='ajax_worker_contract'),
    url(r'^ajax/worker_passport/$', view=_0_views.ajax_worker_passport,
        name='ajax_worker_passport'),
    url(r'^ajax/worker_patent/$', view=_0_views.ajax_worker_patent,
        name='ajax_worker_patent'),
    url(r'^ajax/worker_reg/$', view=_0_views.ajax_worker_registration,
        name='ajax_worker_reg'),
    url(r'^ajax/worker_documents/$', view=_0_views.ajax_workers_documents,
        name='ajax_workers_documents'),

    # Ведомости
    url(r'^worker-by-prepayment-autocomplete/(?P<pk>[0-9]+)/$',
        dac_view.WorkerByPrepaymentAutocomplete.as_view(),
        name='worker-by-prepayment-autocomplete'),

    # Отчеты
    url(r'^calendar/$', _2_0_staff_views.workers_in_calendar, name='workers_in_calendar'),
    url(r'^calendar_average_content/$', _2_0_staff_views.calendar_average_content, name='calendar_average_content'),
    url(r'^calendar_detail_content/$', _2_0_staff_views.calendar_detail_content, name='calendar_detail_content'),

    url(r'^report/absent/$', absent.report_absent, name='report_absent'),
    url(r'^report/absent/details/(?P<location_pk>\d+)/(?P<date>\d\d\.\d\d\.\d{4})/$', absent.absent_details, name='report_absent_details'),

    url(r'^report/hired-fired/$', staff_turnover.hired_fired, name='report_hired_fired'),
    url(r'^report/hired-fired/details/(?P<location_pk>\d+)/(?P<year>\d{4})/(?P<month>\d{1,2})/$', staff_turnover.hired_fired_details, name='hired_fired_details'),

    url(r'^report/timesheet_timeliness/$', _1_orders_views.timesheet_timeliness, name='timesheet_timeliness'),

    url(r'^report/customer_summary/$', customer_summary.report, name='report_customer_summary'),
    url(
        r'^report/customer_summary/details/(?P<location_pk>\d+)/(?P<date>\d\d\.\d\d\.\d{4})/(?P<shift>\S*?)/(?P<report_type>\S*?)/$',
        customer_summary.details,
        name='report_customer_summary_details'
    ),
    url(r'^report/dashboard_root/$', reports.dashboard_root, name='report_dashboard_root'),
    url(
        r'^report/workers_to_link_with_applicants/$',
        reports.workers_to_link_with_applicants,
        name='workers_to_link_with_applicants'
    ),

    # LegalEntity
    url(
        r'^legal_entity/(?P<pk>\d+)/uses_simple_tax_system/',
        _5_finance_views.uses_simple_tax_system,
        name='legal_entity_uses_simple_tax_system'
    ),

    # Несуществующая страница
    url(r'^void/', generic.void, name='void'),

    # Временное
    # url(r'^import_accounts/$', utils.import_operations_and_accounts, name='import_accounts'),
    url(r'^workers_wo_phones/$', utils.workers_wo_phones, name='workers_wo_phones'),

    # Карта
    url(
        r'^map/$',
        delivery.geo_map,
        name='delivery_map'
    ),
]
