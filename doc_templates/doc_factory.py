# -*- coding: utf-8 -*-

from doc_templates import odt


def _notification_document(root, values):
    INTERVALS = {
        'contractor_department_of_internal_affairs' : ['ia_department_first_cell1', 'ia_department_first_cell2'],
        'contractor_legal_entity'                   : 'contractor_legal_entity_cell',
        'contractor_individual'                     : 'contractor_individual_cell',
        'contractor_full_name'                      : ['contractor_full_name_cell1', 'contractor_full_name_cell2', 'contractor_full_name_cell3'],
        'contractor_reg_number'                     : 'contractor_reg_number_first_cell',
        'contractor_tax_and_reason_code'            : 'contractor_tax_and_reason_code_first_cell',
        'contractor_full_address'                   : [
            'contractor_full_address_first_cell1',
            'contractor_full_address_first_cell2',
            'contractor_full_address_first_cell3',
            'contractor_full_address_first_cell4',
        ],
        'contractor_phone_number'                   : 'contractor_phone_number_first_cell',
        'contractor_work_address'                   : [
            'work_address_first_cell1',
            'work_address_first_cell2',
            'work_address_first_cell3',
        ],

        'last_name'                   : 'last_name_first_cell',
        'name'                        : 'name_first_cell',
        'patronymic'                  : 'patronymic_first_cell',
        'citizenship'                 : 'citizenship_first_cell',
        'place_of_birth'              : 'place_of_birth_first_cell',
        'birth_date_day'              : 'birth_day_first_cell',
        'birth_date_month'            : 'birth_month_first_cell',
        'birth_date_year'             : 'birth_year_first_cell',

        'passport'                    : 'passport_first_cell',
        'pass_series'                 : 'pass_series_first_cell',
        'pass_num'                    : 'pass_num_first_cell',
        'pass_date_of_issue_day'      : 'pass_date_of_issue_day_first_cell',
        'pass_date_of_issue_month'    : 'pass_date_of_issue_month_first_cell',
        'pass_date_of_issue_year'     : 'pass_date_of_issue_year_first_cell',
        'pass_issued_by'              : 'pass_issued_by_first_cell',

        'mig_series_number'           : 'migration_card_sn_first_cell',
        'm_day'                       : 'migration_card_day_first_cell',
        'm_month'                     : 'migration_card_month_first_cell',
        'm_year'                      : 'migration_card_year_first_cell',

        'reg_address'                 : ['reg_address_first_cell1', 'reg_address_first_cell2', 'reg_address_first_cell3'],
        'reg_date_day'                : 'reg_date_day_first_cell',
        'reg_date_month'              : 'reg_date_month_first_cell',
        'reg_date_year'               : 'reg_date_year_first_cell',

        # Todo: cont_name is a bad key name, it is profession actually
        'cont_name'                   : 'contract_name_first_cell',
        'td'                          : 'td_cell',
        'gpd'                         : 'gpd_cell',

        'patent'                      : 'patent_first_cell',
        'patent_series'               : 'patent_series_first_cell',
        'patent_num'                  : 'patent_num_first_cell',
        'patent_date_of_issue_day'    : 'patent_date_of_issue_day_first_cell',
        'patent_date_of_issue_month'  : 'patent_date_of_issue_month_first_cell',
        'patent_date_of_issue_year'   : 'patent_date_of_issue_year_first_cell',
        'patent_issued_by'            : 'patent_issued_by_first_cell',
        'patent_start_date_day'       : 'patent_start_date_day_first_cell',
        'patent_start_date_month'     : 'patent_start_date_month_first_cell',
        'patent_start_date_year'      : 'patent_start_date_year_first_cell',
        'patent_end_date_day'         : 'patent_end_date_day_first_cell',
        'patent_end_date_month'       : 'patent_end_date_month_first_cell',
        'patent_end_date_year'        : 'patent_end_date_year_first_cell',

        # Todo: тоже неудачная группа ключей, т.к. это дата заключения в одном уведомлении
        # и дата расторжения - в другом
        'cont_day'                    : 'contract_day_first_cell',
        'cont_month'                  : 'contract_month_first_cell',
        'cont_year'                   : 'contract_year_first_cell',
    }

    PLAIN_CELLS = {
        'doc_day'                          : 'document_day_cell',
        'doc_month'                        : 'document_month_cell',
        'doc_year'                         : 'document_year_cell',

        'contractor_manager_position'      : 'contractor_manager_position_cell',
        'contractor_manager_name'          : 'contractor_manager_name_cell',
        'contractor_proxy_number'          : 'contractor_proxy_number_cell',
        'contractor_proxy_name'            : 'contractor_proxy_name_cell',
        'contractor_proxy_passport_series' : 'contractor_proxy_passport_series_cell',
        'contractor_proxy_passport_number' : 'contractor_proxy_passport_number_cell',
        'contractor_proxy_passport_issued_by' : 'contractor_proxy_passport_issued_by_cell',

        'contractor_proxy_issue_date_day'  : 'contractor_proxy_issue_date_day_cell',
        'contractor_proxy_issue_date_month': 'contractor_proxy_issue_date_month_cell',
        'contractor_proxy_issue_date_year' : 'contractor_proxy_issue_date_year_cell',

        'contractor_proxy_passport_issue_date_day'   : 'contractor_proxy_passport_issue_date_day_cell',
        'contractor_proxy_passport_issue_date_month' : 'contractor_proxy_passport_issue_date_month_cell',
        'contractor_proxy_passport_issue_date_year'  : 'contractor_proxy_passport_issue_date_year_cell',
    }

    return odt.fill_template(
        root,
        INTERVALS,
        PLAIN_CELLS,
        values
    )


def notice_of_contract_document(values):
    return _notification_document(
        'doc_templates/tmpl/notice_of_contract/',
        values
    )


def notice_of_contract_response(values, filename='notification_of_contract.odt'):
    return odt.make_response(
        notice_of_contract_document(values),
        filename
    )


def notification_of_termination_document(values):
    return _notification_document(
        'doc_templates/tmpl/notification_of_termination/',
        values
    )


def notification_of_termination_response(values, filename='notification_of_termination.odt'):
    return odt.make_response(
        notification_of_termination_document(values),
        filename
    )


def _reference_of_notification(root, organization_name, worker_name):
    INTERVALS = {}
    PLAIN_CELLS = {
        'worker_name'       : 'worker_name',
        'organization_name' : 'organization_name'
    }

    return odt.fill_template(
        root,
        INTERVALS,
        PLAIN_CELLS,
        {
            'worker_name' : worker_name,
            'organization_name' : 'Представлена {}'.format(organization_name)
        }
    )


def reference_of_notification_of_contract(organization_name, worker_name):
    return _reference_of_notification(
        'doc_templates/tmpl/reference_of_notification_of_contract/',
        organization_name,
        worker_name
    )


def reference_of_notification_of_termination(organization_name, worker_name):
    return _reference_of_notification(
        'doc_templates/tmpl/reference_of_notification_of_termination/',
        organization_name,
        worker_name
    )


def reference_of_notification_of_termination_response(
        organization_name,
        worker_name,
        filename='reference_of_notification_of_termination.odt'):
    return odt.make_response(
        reference_of_notification_of_termination(organization_name, worker_name),
        filename
    )


def delivery_contract(*args, **kwargs):
    keywords = [
        'contract_id',
        'contract_day',
        'contract_month',
        'contract_year',
        'legal_entity_name_full',
        'legal_entity_name_short_1',
        'legal_entity_name_short_2',
        'legal_entity_person',
        'legal_entity_person_reason',
        'email_1',
        'email_2',
        'legal_address',
        'mail_address',
        'legal_entity_tax_number',
        'legal_entity_reason_code',
        'bank_account',
        'bank_name',
        'correspondent_account',
        'bank_identification_code'
    ]
    PLAIN_CELLS = { k: k for k in keywords }

    legal_entity_name_short = kwargs['legal_entity_name_short']
    del kwargs['legal_entity_name_short']
    kwargs['legal_entity_name_short_1'] = legal_entity_name_short
    kwargs['legal_entity_name_short_2'] = legal_entity_name_short

    email = kwargs['email']
    del kwargs['email']
    kwargs['email_1'] = email
    kwargs['email_2'] = email

    return odt.fill_template(
        'doc_templates/tmpl/delivery_contract',
        {},
        PLAIN_CELLS,
        kwargs
    )


def delivery_contract_response(*args, **kwargs):
    return odt.make_response(
        delivery_contract(*args, **kwargs),
        'gettask_contract.odt'
    )


def delivery_contract_response_pdf(*args, **kwargs):
    return odt.make_response_pdf(
        delivery_contract(*args, **kwargs),
        'gettask_contract.pdf'
    )


def delivery_invoice(*args, **kwargs):
    keywords = [
        'number',
        'day',
        'month',
        'year',
        'legal_entity',
        'total_amount_1',
        'total_amount_2',
        'amount_without_vat_1',
        'amount_without_vat_2',
        'amount_without_vat_3',
        'vat',
    ]
    PLAIN_CELLS = { k: k for k in keywords }

    total_amount = kwargs['total_amount']
    del kwargs['total_amount']
    kwargs['total_amount_1'] = total_amount
    kwargs['total_amount_2'] = total_amount

    amount_without_vat = kwargs['amount_without_vat']
    del kwargs['amount_without_vat']
    kwargs['amount_without_vat_1'] = amount_without_vat
    kwargs['amount_without_vat_2'] = amount_without_vat
    kwargs['amount_without_vat_3'] = amount_without_vat

    return odt.fill_template(
        'doc_templates/tmpl/invoice',
        {},
        PLAIN_CELLS,
        kwargs
    )


def delivery_invoice_pdf(*args, **kwargs):
    return odt.convert_to_pdf(delivery_invoice(*args, **kwargs))


def delivery_worker_list(day, month, year, workers):
    if len(workers) > 44:
        raise Exception('Рабочих больше 44 и они не помещаются в шаблон файла списка')

    keywords = [
        'day',
        'month',
        'year',
        'total',
    ]
    PLAIN_CELLS = { k: k for k in keywords }

    values = {
        'day': day,
        'month': month,
        'year': year,
        'total': str(len(workers))
    }

    for i, worker in enumerate(workers):
        k1 = f'num_{i}'
        k2 = f'full_name_{i}'
        PLAIN_CELLS[k1] = k1
        PLAIN_CELLS[k2] = k2
        values[k1] = str(i + 1)
        values[k2] = str(worker)

    return odt.fill_template(
        'doc_templates/tmpl/delivery_worker_list',
        {},
        PLAIN_CELLS,
        values
    )


def delivery_worker_list_pdf(*args, **kwargs):
    return odt.convert_to_pdf(delivery_worker_list(*args, **kwargs))


# Todo: remove?
def delivery_worker_list_response(day, month, year, workers):
    return odt.make_response(
        delivery_worker_list(day, month, year, workers),
        'worker_list.odt'
    )

def delivery_worker_list_response_pdf(*args, **kwargs):
    return odt.make_response_pdf(
        delivery_worker_list_pdf(*args, **kwargs),
        'worker_list.pdf'
    )
