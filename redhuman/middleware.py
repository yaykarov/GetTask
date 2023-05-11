from importlib import import_module

from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseRedirect
from django.urls import reverse_lazy, resolve


SessionStore = import_module(settings.SESSION_ENGINE).SessionStore


_EVERYONE_PAGES = [
    ('', 'login'),
    ('', 'django_telegrambot'),
    ('', 'webhook'),
    ('the_redhuman_is', 'void'),
    ('the_redhuman_is', 'main'),
    ('the_redhuman_is', 'logout'),
    ('the_redhuman_is', 'check_auth'),

    ('the_redhuman_is', 'my_page'),

    ('the_redhuman_is', 'gt_customer_daily_reconciliation_confirm'),
    ('the_redhuman_is', 'gt_customer_daily_reconciliation_detail'),

    ('the_redhuman_is', 'telephony_operators_for_driver'),

    # Backoffice app
    ('the_redhuman_is', 'backoffice_auth_login'),
    ('the_redhuman_is', 'backoffice_claims_worker_turnout_autocomplete'),
    ('the_redhuman_is', 'backoffice_claims_create'),
    ('the_redhuman_is', 'backoffice_claims_list'),
    ('the_redhuman_is', 'backoffice_common_customer_autocomplete'),
    ('the_redhuman_is', 'backoffice_common_worker_by_customer_autocomplete'),
    ('the_redhuman_is', 'backoffice_common_administration_cost_type_autocomplete'),
    ('the_redhuman_is', 'backoffice_common_industrial_cost_type_autocomplete'),
    ('the_redhuman_is', 'backoffice_common_material_autocomplete'),
    ('the_redhuman_is', 'backoffice_common_menu'),
    ('the_redhuman_is', 'backoffice_delivery_worker_autocomplete'),
    ('the_redhuman_is', 'backoffice_delivery_customer_autocomplete'),
    ('the_redhuman_is', 'backoffice_delivery_operator_autocomplete'),
    ('the_redhuman_is', 'backoffice_delivery_import_history'),
    ('the_redhuman_is', 'backoffice_delivery_request_count'),
    ('the_redhuman_is', 'backoffice_expenses_actual_expenses'),
    ('the_redhuman_is', 'backoffice_expenses_expense_autocomplete'),
    ('the_redhuman_is', 'backoffice_expenses_expense_create'),
    ('the_redhuman_is', 'backoffice_expenses_expense_detail'),
    ('the_redhuman_is', 'backoffice_expenses_expense_update'),
    ('the_redhuman_is', 'backoffice_expenses_provider_autocomplete'),
    ('the_redhuman_is', 'backoffice_expenses_provider_detail'),
    ('the_redhuman_is', 'backoffice_expenses_update_provider'),
    ('the_redhuman_is', 'backoffice_delivery_route_autocomplete'),
    ('the_redhuman_is', 'backoffice_delivery_location_autocomplete'),
    ('the_redhuman_is', 'backoffice_delivery_service_autocomplete'),
    ('the_redhuman_is', 'backoffice_delivery_item_autocomplete'),
    ('the_redhuman_is', 'backoffice_delivery_zone_autocomplete'),
    ('the_redhuman_is', 'backoffice_delivery_worker_map_data'),
    ('the_redhuman_is', 'backoffice_delivery_call_to_driver'),
    ('the_redhuman_is', 'backoffice_delivery_call_to_worker'),
    ('the_redhuman_is', 'backoffice_delivery_ban_worker'),
    ('the_redhuman_is', 'backoffice_delivery_unban_worker'),
    ('the_redhuman_is', 'backoffice_delivery_set_worker_zone'),

    ('the_redhuman_is', 'backoffice_worker_add_comment'),
    ('the_redhuman_is', 'backoffice_worker_bind_to_talk_bank'),
    ('the_redhuman_is', 'backoffice_worker_detail'),
    ('the_redhuman_is', 'backoffice_worker_list'),
    ('the_redhuman_is', 'backoffice_worker_set_planned_contact_day'),
    ('the_redhuman_is', 'backoffice_worker_set_tag'),
    ('the_redhuman_is', 'backoffice_worker_update_online_status'),
    ('the_redhuman_is', 'backoffice_worker_update_rating'),

    # backoffice delivery v2
    ('the_redhuman_is', 'backoffice_delivery_request_list'),
    ('the_redhuman_is', 'backoffice_delivery_request_detail'),
    ('the_redhuman_is', 'backoffice_delivery_create_request'),
    ('the_redhuman_is', 'backoffice_delivery_import_requests'),
    ('the_redhuman_is', 'backoffice_delivery_update_request'),
    ('the_redhuman_is', 'backoffice_delivery_add_request_worker'),
    ('the_redhuman_is', 'backoffice_delivery_confirm_request_worker'),
    ('the_redhuman_is', 'backoffice_delivery_remove_request_worker'),
    ('the_redhuman_is', 'backoffice_delivery_create_item'),
    ('the_redhuman_is', 'backoffice_delivery_update_item'),
    ('the_redhuman_is', 'backoffice_delivery_move_item'),
    ('the_redhuman_is', 'backoffice_delivery_add_item_workers'),
    ('the_redhuman_is', 'backoffice_delivery_remove_item_worker'),
    ('the_redhuman_is', 'backoffice_delivery_delete_item_worker'),
    ('the_redhuman_is', 'backoffice_delivery_item_worker_start'),
    ('the_redhuman_is', 'backoffice_delivery_item_worker_start_photo_reject'),
    ('the_redhuman_is', 'backoffice_delivery_item_worker_start_photo_confirm'),
    ('the_redhuman_is', 'backoffice_delivery_item_worker_start_unconfirm'),
    ('the_redhuman_is', 'backoffice_delivery_item_worker_start_confirm'),
    ('the_redhuman_is', 'backoffice_delivery_item_worker_start_resolve_discrepancy'),
    ('the_redhuman_is', 'backoffice_delivery_item_worker_finish'),
    ('the_redhuman_is', 'backoffice_delivery_item_worker_finish_photo_reject'),
    ('the_redhuman_is', 'backoffice_delivery_item_worker_finish_photo_confirm'),
    ('the_redhuman_is', 'backoffice_delivery_item_worker_finish_reject'),
    ('the_redhuman_is', 'backoffice_delivery_item_worker_finish_confirm'),
    ('the_redhuman_is', 'backoffice_delivery_item_worker_set_hours'),
    ('the_redhuman_is', 'backoffice_photos_dashboard'),
    ('the_redhuman_is', 'backoffice_photos_dashboard_detail'),
    ('the_redhuman_is', 'backoffice_delivery_request_extra_photos'),
    ('the_redhuman_is', 'backoffice_delivery_request_add_extra_photos'),

    ('the_redhuman_is', 'backoffice_delivery_requests_on_map'),
    ('the_redhuman_is', 'backoffice_delivery_map_request_autocomplete'),
    ('the_redhuman_is', 'backoffice_delivery_map_worker_autocomplete'),

    ('the_redhuman_is', 'backoffice_reconciliations_calendar'),
    ('the_redhuman_is', 'backoffice_reconciliations_detail'),
    ('the_redhuman_is', 'backoffice_reconciliations_confirm_unconfirm'),
    ('the_redhuman_is', 'backoffice_reconciliations_send_email'),

    ('the_redhuman_is', 'backoffice_delivery_day_report'),
    ('the_redhuman_is', 'backoffice_delivery_interval_report'),
    ('the_redhuman_is', 'backoffice_delivery_suspicious_turnouts_report'),

    # GT mobile app
    ('the_redhuman_is', 'api_v0_create_one_off_code'),
    ('the_redhuman_is', 'api_v0_obtain_tokens'),

    ('the_redhuman_is', 'api_v0_status_update'),
    ('the_redhuman_is', 'api_v0_update_request'),
    ('the_redhuman_is', 'api_v0_upload_registration_info'),
    ('the_redhuman_is', 'api_v0_worker_account_info'),
    ('the_redhuman_is', 'api_v0_worker_payment_info'),
    ('the_redhuman_is', 'api_v0_update_worker_payment_info'),
    ('the_redhuman_is', 'api_v0_worker_requests'),
    ('the_redhuman_is', 'api_v0_worker_unpaid_requests'),

    # GT mobile app - ending slashes
    ('the_redhuman_is', 'api_v1_create_one_off_code'),
    ('the_redhuman_is', 'api_v1_obtain_tokens'),

    ('the_redhuman_is', 'api_v0_online_status_update'),
    ('the_redhuman_is', 'api_v1_status_update'),
    ('the_redhuman_is', 'api_v1_update_worker_payment_info'),
    ('the_redhuman_is', 'api_v1_upload_registration_info'),
    ('the_redhuman_is', 'api_v1_worker_account_info'),
    ('the_redhuman_is', 'api_v1_worker_payment_info'),
    ('the_redhuman_is', 'api_v1_request_payout'),

    # GT mobile app - v2
    ('the_redhuman_is', 'api_v2_create_one_off_code'),
    ('the_redhuman_is', 'api_v2_obtain_tokens'),
    ('the_redhuman_is', 'api_v2_upload_registration_info'),
    ('the_redhuman_is', 'api_v2_status_update'),
    ('the_redhuman_is', 'api_v2_online_status_update'),
    ('the_redhuman_is', 'api_v2_worker_requests'),
    ('the_redhuman_is', 'api_v2_worker_unpaid_requests'),
    ('the_redhuman_is', 'api_v2_worker_account_info'),
    ('the_redhuman_is', 'api_v2_worker_payment_info'),
    ('the_redhuman_is', 'api_v2_update_worker_payment_info'),
    ('the_redhuman_is', 'api_v2_add_request_worker'),
    ('the_redhuman_is', 'api_v2_confirm_request_worker'),
    ('the_redhuman_is', 'api_v2_item_worker_start'),
    ('the_redhuman_is', 'api_v2_item_worker_finish'),
    ('the_redhuman_is', 'api_v2_request_payout'),
    ('the_redhuman_is', 'api_v2_answer_poll'),

    # GT mobile app - partners
    ('the_redhuman_is', 'mobile_app_list_partners'),

    # Delivery map report
    ('the_redhuman_is', 'delivery_map'),

    # GT landing
    ('the_redhuman_is', 'gt_landing_calc_request'),
    ('the_redhuman_is', 'gt_landing_create_request'),

    # Todo: make a special group for that?
    # GT Customer account
    ('the_redhuman_is', 'gt_customer_request_autocomplete'),
    ('the_redhuman_is', 'gt_customer_item_autocomplete'),
    ('the_redhuman_is', 'gt_customer_location_autocomplete'),
    ('the_redhuman_is', 'gt_customer_signup'),
    ('the_redhuman_is', 'gt_customer_finish_registration'),
    ('the_redhuman_is', 'gt_customer_obtain_token'),
    ('the_redhuman_is', 'gt_customer_reset_password'),
    ('the_redhuman_is', 'gt_customer_update_password'),
    ('the_redhuman_is', 'gt_customer_account_info'),
    ('the_redhuman_is', 'gt_customer_update_legal_entity_info'),
    ('the_redhuman_is', 'gt_customer_legal_entity_info'),
    ('the_redhuman_is', 'gt_customer_add_contact_person'),
    ('the_redhuman_is', 'gt_customer_update_contact_person'),
    ('the_redhuman_is', 'gt_customer_contact_persons'),
    ('the_redhuman_is', 'gt_customer_get_contract'),
    ('the_redhuman_is', 'gt_customer_upload_contract_scans'),
    ('the_redhuman_is', 'gt_customer_report_scan'),
    ('the_redhuman_is', 'gt_customer_reports'),
    ('the_redhuman_is', 'gt_customer_confirm_report'),
    ('the_redhuman_is', 'gt_customer_imports'),
    ('the_redhuman_is', 'gt_customer_requests_file'),
    ('the_redhuman_is', 'gt_customer_invoice'),
    ('the_redhuman_is', 'gt_customer_invoices'),
    ('the_redhuman_is', 'gt_customer_create_invoice'),

    # GT Customer account - ending slashes
    ('the_redhuman_is', 'gt_customer_signup_v1'),
    ('the_redhuman_is', 'gt_customer_finish_registration_v1'),
    ('the_redhuman_is', 'gt_customer_obtain_token_v1'),
    ('the_redhuman_is', 'gt_customer_reset_password_v1'),
    ('the_redhuman_is', 'gt_customer_update_password_v1'),
    ('the_redhuman_is', 'gt_customer_update_legal_entity_info_v1'),
    ('the_redhuman_is', 'gt_customer_add_contact_person_v1'),
    ('the_redhuman_is', 'gt_customer_update_contact_person_v1'),
    ('the_redhuman_is', 'gt_customer_upload_contract_scans_v1'),
    ('the_redhuman_is', 'gt_customer_confirm_report_v1'),
    ('the_redhuman_is', 'gt_customer_create_invoice_v1'),

    # customer api
    ('the_redhuman_is', 'gt_customer_api_v1_auth_token'),
    ('the_redhuman_is', 'gt_customer_api_v1_delivery_request_list'),
    ('the_redhuman_is', 'gt_customer_api_v1_delivery_request_detail'),
    ('the_redhuman_is', 'gt_customer_api_v1_delivery_create_request'),
    ('the_redhuman_is', 'gt_customer_api_v1_location_list'),
    ('the_redhuman_is', 'gt_customer_api_v1_price'),

    # customer v2
    ('the_redhuman_is', 'gt_customer_delivery_request'),
    ('the_redhuman_is', 'gt_customer_delivery_request_detail'),
    ('the_redhuman_is', 'gt_customer_delivery_create_request'),
    ('the_redhuman_is', 'gt_customer_delivery_import_requests'),
    ('the_redhuman_is', 'gt_customer_delivery_update_request'),
    ('the_redhuman_is', 'gt_customer_delivery_create_item'),
    ('the_redhuman_is', 'gt_customer_delivery_update_item'),
    ('the_redhuman_is', 'gt_customer_report_details'),
    ('the_redhuman_is', 'gt_customer_request_photo'),

    ('the_redhuman_is', 'gt_customer_delivery_requests_on_map'),
    ('the_redhuman_is', 'gt_customer_delivery_map_request_autocomplete'),

    # Export
    ('the_redhuman_is', 'export_self_employed_receipts'),

    # Rocketchat
    ('the_redhuman_is', 'rocketchat_webhook_on_new_message'),

    # Talk Bank
    ('the_redhuman_is', 'talkbank_webhook_on_income_registered'),

    # Analytics
    ('the_redhuman_is', 'analytics_list_requests'),
    ('the_redhuman_is', 'analytics_list_calls'),
    ('the_redhuman_is', 'analytics_hours_summary'),
    ('the_redhuman_is', 'analytics_calls_turnout_summary'),
]


_FOREMAN_PAGES = [
    ('the_redhuman_is', 'photo_load_session_list'),
    ('the_redhuman_is', 'photo_load_session_add'),
    ('the_redhuman_is', 'photo_load_session_update'),
    ('the_redhuman_is', 'get_photo'),

    ('applicants', 'unassigned_count'),
]


_MANAGER_PAGES = _FOREMAN_PAGES + [
    ('the_redhuman_is', 'list_workers'),
    ('the_redhuman_is', 'worker_detail'),
    ('the_redhuman_is', 'worker_edit'),
    ('the_redhuman_is', 'timesheet'),
    ('the_redhuman_is', 'm_manager-autocomplete'),
    ('the_redhuman_is', 'd_manager-autocomplete'),
    ('the_redhuman_is', 'customer_list'),
    ('the_redhuman_is', 'customer_detail'),
    ('the_redhuman_is', 'customer-autocomplete'),
    ('the_redhuman_is', 'report_customer_summary'),
    ('the_redhuman_is', 'report_customer_summary_details'),
    ('the_redhuman_is', 'report_absent'),
    ('the_redhuman_is', 'report_absent_details'),
    ('the_redhuman_is', 'paysheet_v2_show'),
    ('the_redhuman_is', 'paysheet_v2_list'),
    ('the_redhuman_is', 'paysheet_v2_day_details'),
    ('the_redhuman_is', 'prepayment_show'),

    ('the_redhuman_is', 'workers_in_calendar'),
    ('the_redhuman_is', 'calendar_average_content'),
    ('the_redhuman_is', 'calendar_detail_content'),
    ('the_redhuman_is', 'customer-service-autocomplete'),
    ('the_redhuman_is', 'customer-location-autocomplete'),
    ('the_redhuman_is', 'range_timesheets'),
    ('the_redhuman_is', 'account_total_detail'),
    ('the_redhuman_is', 'timesheet_locations'),

    ('the_redhuman_is', 'worker_create_user'),

    ('the_redhuman_is', 'worker_search'),
    ('the_redhuman_is', 'worker-autocomplete'),
    ('the_redhuman_is', 'report_dashboard_root'),

    ('the_redhuman_is', 'vkusvill_performance_report'),
    ('the_redhuman_is', 'vkusvill_temporary_fines'),

    ('telegram_bot', 'users_list'),
]


_RECRUITMENT_PAGES = [
    ('applicants', 'list'),
    ('the_redhuman_is', 'report_absent'),
    ('the_redhuman_is', 'report_absent_details'),
]


_CHIEF_RECRUITMENT_PAGES = _RECRUITMENT_PAGES + [
    ('the_redhuman_is', 'report_customer_summary_details'),
]


_EXTERNAL_RECRUITMENT_PAGES = [
    ('applicants', 'list'),
    ('applicants', 'create'),
    ('applicants', 'detail'),
    ('applicants', 'update'),

    ('applicants', 'status-autocomplete'),
    ('applicants', 'manager_autocomplete'),
    ('applicants', 'source_autocomplete'),
]


_CAN_SEE_UNASSIGNED_APPLICANT_PAGES = [
    ('applicants', 'unassigned_count'),
    ('applicants', 'unassigned_list'),
    ('applicants', 'assign'),
]


_CAN_SEE_NEW_CUSTOMERS = [
    ('the_redhuman_is', 'delivery_new_customers_report'),
    ('the_redhuman_is', 'delivery_new_customers_report_data'),
]


_BOOKKEEPER_PAGES = _EVERYONE_PAGES + [
    ('the_redhuman_is', 'worker_detail'),
    ('the_redhuman_is', 'worker_snils'),
    ('the_redhuman_is', 'worker_save_snils'),
    ('the_redhuman_is', 'worker_self_employment_data'),
    ('the_redhuman_is', 'worker_save_self_employment_data'),
    ('the_redhuman_is', 'worker_image'),

    ('the_redhuman_is', 'contracts_list'),
    ('the_redhuman_is', 'download_notices'),
    ('the_redhuman_is', 'download_images_for_contracts'),
    ('the_redhuman_is', 'contracts_set_dates'),
    ('the_redhuman_is', 'contracts_fire'),
    ('the_redhuman_is', 'contracts_set_contractor'),
    ('the_redhuman_is', 'attach_notice_image'),
    ('the_redhuman_is', 'notification_of_contract_photos'),
    ('the_redhuman_is', 'contractors_summary'),
    ('the_redhuman_is', 'contractor_workers'),
    ('the_redhuman_is', 'export_contracts_csv'),
    ('the_redhuman_is', 'contractor_proxy_autocomplete'),
    ('the_redhuman_is', 'contractor_autocomplete'),
    ('the_redhuman_is', 'edit_contract'),

    ('the_redhuman_is', 'get_photo'),
    ('the_redhuman_is', 'notice_download_status'),
    ('the_redhuman_is', 'worker_edit'),
    ('the_redhuman_is', 'edit_patent'),

    ('applicants', 'unassigned_count'),
]


_EXPENSES_PAGES = _EVERYONE_PAGES + [
    ('the_redhuman_is', 'expenses_actual_expenses'),
    ('the_redhuman_is', 'expenses_create_expense'),
    ('the_redhuman_is', 'expenses_create_provider'),
    ('the_redhuman_is', 'expenses_index'),
    ('the_redhuman_is', 'expenses_provider_detail'),
    ('the_redhuman_is', 'expenses_update'),
    ('the_redhuman_is', 'expenses_update_provider'),

    ('the_redhuman_is', 'administration-cost-type-autocomplete'),
    ('the_redhuman_is', 'customer-autocomplete'),
    ('the_redhuman_is', 'expense-autocomplete'),
    ('the_redhuman_is', 'industrial-cost-type-autocomplete'),
    ('the_redhuman_is', 'material-autocomplete'),
    ('the_redhuman_is', 'provider-autocomplete'),

    ('the_redhuman_is', 'claims_create_claim'),
    ('the_redhuman_is', 'claims_list'),
    ('the_redhuman_is', 'claims_photos'),
    ('the_redhuman_is', 'claims_worker_turnout_autocomplete'),
    ('the_redhuman_is', 'expense-by-customer-autocomplete'),
    ('the_redhuman_is', 'worker-by-customer-autocomplete'),
]


_OPERATIONS_PAGE = _EVERYONE_PAGES + [
    ('the_redhuman_is', 'expense-autocomplete'),
    ('the_redhuman_is', 'expense_page'),
    ('the_redhuman_is', 'edit_expense'),
    ('the_redhuman_is', 'get_user_operations'),
    ('the_redhuman_is', 'legal-entity-autocomplete'),
    ('the_redhuman_is', 'make_expense'),
]


_CASHIER_PAGES = _OPERATIONS_PAGE + [
    ('the_redhuman_is', 'list_workers'),
    ('the_redhuman_is', 'worker_detail'),
    ('the_redhuman_is', 'worker-autocomplete'),
    ('the_redhuman_is', 'get_photo'),
    ('the_redhuman_is', 'worker_self_employment_data'),
    ('the_redhuman_is', 'worker_save_self_employment_data'),

    ('the_redhuman_is', 'workers_in_calendar'),
    ('the_redhuman_is', 'calendar_average_content'),
    ('the_redhuman_is', 'calendar_detail_content'),
    ('the_redhuman_is', 'customer-service-autocomplete'),
    ('the_redhuman_is', 'actual-location-autocomplete'),
    ('the_redhuman_is', 'customer-location-autocomplete'),
    ('the_redhuman_is', 'range_timesheets'),
    ('the_redhuman_is', 'account_total_detail'),
    ('the_redhuman_is', 'timesheet_locations'),

    ('the_redhuman_is', 'timesheet'),

    ('the_redhuman_is', 'accountable-person-autocomplete'),
    ('the_redhuman_is', 'all-worker-autocomplete'),
    ('the_redhuman_is', 'customer-autocomplete'),

    # Todo: extract to special group 'Закрытие ведомостей'
    ('the_redhuman_is', 'paysheet_v2_add_image'),
    ('the_redhuman_is', 'paysheet_v2_add_registry'),
    ('the_redhuman_is', 'paysheet_v2_close'),
    ('the_redhuman_is', 'paysheet_v2_day_details'),
    ('the_redhuman_is', 'paysheet_v2_list'),
    ('the_redhuman_is', 'paysheet_v2_paysheet_autocomplete'),
    ('the_redhuman_is', 'paysheet_v2_paysheet_receipts'),
    ('the_redhuman_is', 'paysheet_v2_remove_workers'),
    ('the_redhuman_is', 'paysheet_v2_save_receipts'),
    ('the_redhuman_is', 'paysheet_v2_show'),
    ('the_redhuman_is', 'prepayment_add_image'),
    ('the_redhuman_is', 'prepayment_close'),
    ('the_redhuman_is', 'prepayment_delete_worker'),
    ('the_redhuman_is', 'prepayment_show'),
    ('the_redhuman_is', 'paysheet_v2_talk_bank_payment_report'),

    ('applicants', 'unassigned_count'),

    ('the_redhuman_is', 'self_employment_list'),
    ('the_redhuman_is', 'self_employment_data'),
    ('the_redhuman_is', 'self_employment_toggle'),

    # Todo: Это доступ к балансу. Надо ограничить конкретными счетами.
    ('the_redhuman_is', 'account_total_detail'),
    ('the_redhuman_is', 'operating_account_detail'),
    ('the_redhuman_is', 'operating_account_detail_json'),
    ('the_redhuman_is', 'operating_account_tree'),
    ('the_redhuman_is', 'operating_account_tree_json'),
    ('the_redhuman_is', 'operating_account_add_operation'),
    ('the_redhuman_is', 'to_pay_salary_proxy'),
    ('the_redhuman_is', 'to_pay_salary'),
    ('the_redhuman_is', 'form_po'),

    # Платежный календарь
    ('the_redhuman_is', 'payment_schedule_index'),
    ('the_redhuman_is', 'payment_schedule_schedule'),
    ('the_redhuman_is', 'payment_schedule_operations'),
    ('the_redhuman_is', 'payment_schedule_day_operations'),
    ('the_redhuman_is', 'payment_schedule_create_operation'),
    ('the_redhuman_is', 'payment_schedule_delete_operation'),

    # Сверки
    ('the_redhuman_is', 'reconciliation_unpaid_autocomplete'),
    ('the_redhuman_is', 'reconciliation_remove'),
    ('the_redhuman_is', 'reconciliation_list'),
    ('the_redhuman_is', 'reconciliation_show'),
    ('the_redhuman_is', 'reconciliation_photos'),
    ('the_redhuman_is', 'reconciliation_add_image'),
    ('the_redhuman_is', 'reconciliation_set_invoice'),
    ('the_redhuman_is', 'reconciliation_extra_documents'),
    ('the_redhuman_is', 'reconciliation_block_operations'),

    # Клиенты
    ('the_redhuman_is', 'customer_list'),
    ('the_redhuman_is', 'customer_contract_scans'),
    ('the_redhuman_is', 'customer_add_contract_scans'),

    # Фотки рабочего
    ('the_redhuman_is', 'staff_worker_documents'),
    ('the_redhuman_is', 'staff_worker_documents_photos_data'),
    ('the_redhuman_is', 'staff_worker_documents_update_photo'),

    # Импорт выписок (в отдельную группу?)
    ('import1c', 'import-operation'),
    ('import1c', 'add-operation'),
    ('the_redhuman_is', 'finance-account-autocomplete'),

    # Запрос прав МТС
    ('the_redhuman_is', 'delivery_other'),
    ('the_redhuman_is', 'delivery_test_registry'),
    ('the_redhuman_is', 'delivery_workers_to_connect_to_mts'),

    # Начислить
    ('the_redhuman_is', 'make_payroll'),
]


_BANK_STATEMENTS_IMPORT_PAGES = _EVERYONE_PAGES + [
    ('import1c', 'upload-1c-file'),
]


_DELIVERY_OPERATOR_PAGES = _EVERYONE_PAGES + [
    ('the_redhuman_is', 'delivery_index'),
    ('the_redhuman_is', 'delivery_requests_on_map'),  # For access rights from react app
    ('the_redhuman_is', 'delivery_delivery_request_extra_photos'),
    ('the_redhuman_is', 'delivery_photo_global_dashboard'),
    ('the_redhuman_is', 'delivery_turnouts_report'),
    ('the_redhuman_is', 'delivery_online_status_report'),

    ('the_redhuman_is', 'delivery_location_autocomplete'),
    ('the_redhuman_is', 'delivery_service_autocomplete'),
    ('the_redhuman_is', 'delivery_route_autocomplete'),
    ('the_redhuman_is', 'delivery_item_autocomplete'),
    ('the_redhuman_is', 'delivery_worker_autocomplete'),
    ('the_redhuman_is', 'delivery_request_operator_autocomplete'),
    ('the_redhuman_is', 'delivery_zone_autocomplete'),
    ('the_redhuman_is', 'delivery_operator_autocomplete'),

    ('the_redhuman_is', 'delivery_imports_report'),
    ('the_redhuman_is', 'delivery_imports_report_data'),
    ('the_redhuman_is', 'delivery_requests_file'),

    ('the_redhuman_is', 'delivery_workers_report'), # Do not remove
    ('the_redhuman_is', 'delivery_daily_reconciliations'), # Do not remove
    ('the_redhuman_is', 'delivery_requests_count_report'),
    ('the_redhuman_is', 'delivery_requests_count_report_data'),
    ('the_redhuman_is', 'delivery_turnouts_period_report'),

    ('the_redhuman_is', 'delivery_call_list'),
    ('the_redhuman_is', 'delivery_call_list_csv'),
    ('the_redhuman_is', 'delivery_other'),

    # Автокомплит из других модулей
    ('the_redhuman_is', 'customer-autocomplete'),
    ('the_redhuman_is', 'customer-service-autocomplete'),
    ('the_redhuman_is', 'worker-by-customer-autocomplete'),

    ('the_redhuman_is', 'backoffice_delivery_calls_report'),
]


_DELIVERY_INSPECTOR = [
    # Сортировка фото
    ('the_redhuman_is', 'photo_load_add_comment'),
    ('the_redhuman_is', 'photo_load_bad_photo_alert'),
    ('the_redhuman_is', 'photo_load_close_session'),
    ('the_redhuman_is', 'photo_load_session_add'),
    ('the_redhuman_is', 'photo_load_session_delete'),
    ('the_redhuman_is', 'photo_load_session_list'),
    ('the_redhuman_is', 'photo_load_session_sort'), # Todo
    ('the_redhuman_is', 'photo_load_session_update'),
    ('the_redhuman_is', 'worker_turnout_output'),
    ('the_redhuman_is', 'get_photo'),

    # Автокомплит из других модулей
    ('the_redhuman_is', 'all-worker-autocomplete'),
    ('the_redhuman_is', 'country-autocomplete'),
    ('the_redhuman_is', 'position-autocomplete'),
]


_DELIVERY_CHIEF = [
    # Todo:
    ('the_redhuman_is', 'backoffice_delivery_calls_report'),
]


# Todo: currently there are only menu items
# need to add all the views and remove _SUPERGROUPS list
_HR_INSPECTOR_PAGES = _EVERYONE_PAGES + [
    ('the_redhuman_is', 'list_workers'),
    ('the_redhuman_is', 'self_employment_list'),
    ('the_redhuman_is', 'contracts_list'),

    ('the_redhuman_is', 'workers_in_calendar'),
    ('the_redhuman_is', 'hostel_expenses_report'),
]


# Todo: currently there are only menu items
# need to add all the views and remove _SUPERGROUPS list
_OPERATOR_PAGES = _EVERYONE_PAGES + [
    ('the_redhuman_is', 'orders_dashboard'),

    ('the_redhuman_is', 'list_workers'),
    ('the_redhuman_is', 'self_employment_list'),
    ('the_redhuman_is', 'contracts_list'),
    ('the_redhuman_is', 'photo_load_session_list'),

#    ('the_redhuman_is', 'fine_utils_import_fines'),
#    ('the_redhuman_is', 'hostel_list'),

    ('the_redhuman_is', 'customer_list'),

    ('the_redhuman_is', 'workers_in_calendar'),
    ('the_redhuman_is', 'hostel_expenses_report'),
    ('the_redhuman_is', 'workers_to_link_with_applicants'),

    ('the_redhuman_is', 'delivery_index'),
    ('the_redhuman_is', 'delivery_workers_report'),
    ('the_redhuman_is', 'delivery_imports_report'),
    ('the_redhuman_is', 'delivery_photo_global_dashboard'),
    ('the_redhuman_is', 'delivery_requests_count_report'),
    ('the_redhuman_is', 'delivery_turnouts_period_report'),
    ('the_redhuman_is', 'delivery_turnouts_report'),
]


_NEW_USERS_VERIFICATION = _EVERYONE_PAGES + [
    # Сортировка фото
    ('the_redhuman_is', 'photo_load_add_comment'),
    ('the_redhuman_is', 'photo_load_bad_photo_alert'),
    ('the_redhuman_is', 'photo_load_close_session'),
    ('the_redhuman_is', 'photo_load_session_add'),
    ('the_redhuman_is', 'photo_load_session_delete'),
    ('the_redhuman_is', 'photo_load_session_list'),
    ('the_redhuman_is', 'photo_load_session_sort'), # Todo
    ('the_redhuman_is', 'photo_load_session_update'),
    ('the_redhuman_is', 'worker_turnout_output'),
    ('the_redhuman_is', 'get_photo'),

    # Автокомплит из других модулей
    ('the_redhuman_is', 'all-worker-autocomplete'),
    ('the_redhuman_is', 'country-autocomplete'),
    ('the_redhuman_is', 'customer-repr-autocomplete'),
    ('the_redhuman_is', 'foreman-autocomplete'),
    ('the_redhuman_is', 'position-autocomplete'),
    ('the_redhuman_is', 'worker_with_contract_autocomplete'),

    # Список исполнителей
    ('the_redhuman_is', 'delivery_workers_report'), # Do not remove

    # Фотки рабочего
    ('the_redhuman_is', 'staff_worker_documents'),

    # Страница рабочего
    ('the_redhuman_is', 'worker_detail'),
]


_PAGES_FOR_GROUPS = {
    'hr_inspector'                    : _HR_INSPECTOR_PAGES,
    'Бригадиры'                       : _FOREMAN_PAGES,
    'Бухгалтеры внешние'              : _BOOKKEEPER_PAGES,
    'Верификация новых пользователей' : _NEW_USERS_VERIFICATION,
    'Видят необработанные звонки'     : _CAN_SEE_UNASSIGNED_APPLICANT_PAGES,
    'Видят новых клиентов'            : _CAN_SEE_NEW_CUSTOMERS,
    'Доставка-диспетчер'              : _DELIVERY_OPERATOR_PAGES,
    'Доставка-проверяющий'            : _DELIVERY_INSPECTOR,
    'Доставка-руководитель'           : _DELIVERY_CHIEF,
    'Импорт банковских выписок'       : _BANK_STATEMENTS_IMPORT_PAGES,
    'Касса'                           : _CASHIER_PAGES,
    'Менеджеры'                       : _MANAGER_PAGES,
    'Операционисты'                   : _OPERATOR_PAGES,
    'Подача расходов'                 : _EXPENSES_PAGES,
    'Подборщики внешние'              : _EXTERNAL_RECRUITMENT_PAGES,
    'Подборщики руководитель'         : _CHIEF_RECRUITMENT_PAGES,
    'Подборщики'                      : _RECRUITMENT_PAGES,
    'Учет операций'                   : _OPERATIONS_PAGE,
}


_NAMESPACES_FOR_GROUPS = {
    'Подборщики руководитель' : ['applicants', 'wiki'],
    'Подборщики' : ['applicants', 'wiki'],
    'Менеджеры'  : ['wiki'],
    'Бригадиры'  : ['wiki'],
}


_SUPERGROUPS = [
    'Операционисты',
    'hr_inspector'
]


class RestrictAccess(object):
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        path_data = resolve(request.path)

        if path_data.view_name == 'django.views.static.serve':
            return None

        page = (path_data.namespace, path_data.url_name)
        if page in _EVERYONE_PAGES:
            return None

        if not hasattr(request, 'user'):
            return HttpResponseRedirect(
                reverse_lazy('the_redhuman_is:void')
            )

        if request.user.is_superuser:
            return None

        auth_session_id = request.GET.get('session_id')
        if not request.user.is_authenticated:
            if auth_session_id:
                auth_session = SessionStore(session_key=auth_session_id)
                data = auth_session.load()
                user_id = data.get('_auth_user_id')
                if user_id:
                    user = User.objects.get(pk=user_id)
                    login(request, user)

        if not request.user.is_authenticated:
            return HttpResponseRedirect(
                reverse_lazy('the_redhuman_is:void')
            )


        user_groups = request.user.groups.values_list('name', flat=True)

        for group in user_groups:
            if group in _SUPERGROUPS:
                return None

            pages = _PAGES_FOR_GROUPS.get(group)
            if pages and page in pages:
                return None

            namespaces = _NAMESPACES_FOR_GROUPS.get(group)
            if namespaces and path_data.namespace in namespaces:
                return None

        return HttpResponseRedirect(
            reverse_lazy('the_redhuman_is:void')
        )

    def process_exception(self, request, exception):
        if isinstance(exception, PermissionDenied):
            return HttpResponseRedirect(
                reverse_lazy('the_redhuman_is:void')
            )

        return None


def is_page_allowed(groups, page):
    for group in groups:
        pages = _PAGES_FOR_GROUPS.get(group)
        if pages and page in pages:
            return True

    return False
