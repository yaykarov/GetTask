# -*- coding: utf-8 -*-

from django.http import HttpResponse

from doc_templates.doc_factory import delivery_contract_response


def test(request):
    return delivery_contract_response(
        contract_day='12',
        contract_month='июля',
        contract_year='2020',
        legal_entity_name_full='ООО Опрятные ребята',
        legal_entity_name_short='Опрятные ребята',
        legal_entity_person='Прянишникова Сергея Викторовича',
        legal_entity_person_reason='устава',
        email='abc@google.com',
        legal_address='Не дом и не улица',
        mail_address='Москва, ул. Ленина-Сталина, 23к4 офис 566',
        legal_entity_tax_number='123432254',
        legal_entity_reason_code='1545454545',
        bank_account='25068156204134',
        bank_name='Банк Барабанк',
        correspondent_account='622-11405445236635',
        bank_identification_code='65252544'
    )
