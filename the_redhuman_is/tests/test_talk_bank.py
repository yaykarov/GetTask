#from decimal import (
#    Decimal,
#)
#
#import pytest
#
#from the_redhuman_is.async_utils.talk_bank.talk_bank import (
#    CancelReceiptReason,
#    SelfemploymentsStatus,
#    Service,
#    TalkBankClient,
#)
#
#
#@pytest.fixture
#def client_bank():
#    base_url = 'https://baas-staging.talkbank.io'
#    partner_id = 'a2281839-c0c2-424c-9b1a-12e79fce77fc'
#    partner_token = (
#        '2bb80d537b1da3e38bd30361aa855686bde0eacd7162fef6a25fe97bf527a25b'
#    )
#    return TalkBankClient(base_url, partner_id, partner_token)
#
#
#@pytest.fixture
#def services():
#    return [
#        Service('Наименование услуги', Decimal('123.05'), 1),
#        Service('Наименование услуги', Decimal('100.25'), 2),
#    ]
#
#
#@pytest.mark.parametrize(
#    'method,url,date_time,body,expected',
#    [
#        (
#            'GET',
#            '/api/v1/method?alpha=&limit=5&skip=50',
#            'Tue, 19 Feb 2019 08:43:02 GMT',
#            '',
#            (
#                'TB1-HMAC-SHA256 a2281839-c0c2-424c-9b1a-12e79fce77fc:0ac12ac'
#                + '72ae5fff35f644b8304f92cb16c61bc0e6c92c16ad181d2433825b243'
#            ),
#        ),
#        (
#            'POST',
#            '/api/v1/method',
#            'Tue, 19 Feb 2019 11:43:02 GMT',
#            '{"data": "request"}',
#            (
#                'TB1-HMAC-SHA256 a2281839-c0c2-424c-9b1a-12e79fce77fc:192cdf7'
#                + 'b394464e7f06db97df27b21fd17174299050f6f608d396892cf70fc67'
#            ),
#        ),
#    ],
#)
#def test_create_value_for_authorization_header(
#    method, url, date_time, body, expected, client_bank,
#):
#    authorization = client_bank.create_value_for_authorization_header(
#        method,
#        url,
#        date_time,
#        body,
#    )
#    assert authorization == expected
#
#
#def test_create_client_without_identification(client_bank, requests_mock):
#    url = client_bank.get_full_url('create_client')
#    requests_mock.post(url, json={"client_id": "123124"})
#    result = client_bank.create_client_without_identification(
#        '123124', '79451111111',
#    )
#    assert result == "123124"
#
#
#def test_create_client_with_simple_identification(client_bank, requests_mock):
#    url = client_bank.get_full_url('create_client')
#    requests_mock.post(url, json={"client_id": "123124"})
#    result = client_bank.create_client_with_simple_identification(
#        '123124',
#        'Иван',
#        'Иванович',
#        'Иванов',
#        '1970-01-01',
#        0,
#        'secret_word',
#        '79451111111',
#        '1100',
#        '111928',
#        '2015-01-12',
#        '6449013711',
#        '116-973-385 89',
#    )
#    assert result == "123124"
#
#
#def test_get_selfemployment_status(client_bank, requests_mock):
#    url = client_bank.get_full_url(
#        'get_selfemployment_status', client_id='client123',
#    )
#    mock_response = {
#        "client_id": "client123",
#        "status": "registered",
#        "description": "Success",
#        "details": {
#            "FirstName": "ИВАН",
#            "SecondName": "ПЕТРОВ",
#            "Patronymic": "ВАСИЛЬЕВИЧ",
#            "RegistrationTime": "2020-07-13T16:08:00.090Z",
#            "Activities": ["42"],
#            "Region": "01000000",
#            "Phone": "79131110000",
#            "Email": "info@info.ru",
#            "Inn": "567342672585",
#        },
#    }
#    requests_mock.get(url, json=mock_response)
#    status = client_bank.get_selfemployment_status('client123')
#    assert status == SelfemploymentsStatus('registered')
#
#
#def test_bind_client(client_bank, requests_mock):
#    client_id = 'client1'
#    url = client_bank.get_full_url('bind_client', client_id=client_id)
#    mock_response = {
#        "client_id": client_id,
#        "status": "success",
#    }
#    requests_mock.post(url, json=mock_response)
#    completed = client_bank.bind_client(client_id)
#    assert completed
#
#
#def test_register_income_from_individual(client_bank, requests_mock, services):
#    client_id = 'f00001'
#    url = client_bank.get_full_url('register_income', client_id=client_id)
#    expected_receipt_id = '20040u4xrg'
#    expected_link = (
#        'https://lknpd.nalog.ru/api/v1/receipt/637401428296/20040u4xrg/print'
#    )
#    mock_response = {
#        "client_id": client_id,
#        "status": "success",
#        "data": {
#            "ReceiptId": expected_receipt_id,
#            "Link": expected_link,
#        },
#    }
#    requests_mock.post(url, json=mock_response)
#    receipt_id, link = client_bank.register_income_from_individual(
#        client_id, '2020-10-26T06:35:40+00:00', services, 323.55,
#    )
#    assert receipt_id == expected_receipt_id
#    assert link == expected_link
#
#
#def test_register_income_from_legal_entity(
#    client_bank, requests_mock, services,
#):
#    client_id = 'client123'
#    url = client_bank.get_full_url('register_income', client_id=client_id)
#    expected_receipt_id = '2000guuwhv'
#    expected_link = (
#        'https://himself-ktr.nalog.ru/api/v1/receipt/540860935007/'
#        + '2000guuwhv/print'
#    )
#    mock_response = {
#        "client_id": client_id,
#        "status": "success",
#        "data": {
#            "ReceiptId": expected_receipt_id,
#            "Link": expected_link,
#        },
#    }
#    requests_mock.post(url, json=mock_response)
#    receipt_id, link = client_bank.register_income_from_legal_entity(
#        client_id,
#        '2020-10-26T06:35:40+00:00',
#        services,
#        323.55,
#        '7734387717',
#        'Рога и Копыта',
#    )
#    assert receipt_id == expected_receipt_id
#    assert link == expected_link
#
#
#def test_register_income_from_foreign_agency(
#    client_bank, requests_mock, services,
#):
#    client_id = 'f00001'
#    url = client_bank.get_full_url('register_income', client_id=client_id)
#    expected_receipt_id = '20040u4xrg'
#    expected_link = (
#        'https://lknpd.nalog.ru/api/v1/receipt/637401428296/20040u4xrg/print'
#    )
#    mock_response = {
#        "client_id": client_id,
#        "status": "success",
#        "data": {
#            "ReceiptId": expected_receipt_id,
#            "Link": expected_link,
#        },
#    }
#    requests_mock.post(url, json=mock_response)
#    receipt_id, link = client_bank.register_income_from_foreign_agency(
#        client_id,
#        '2021-11-25T12:10:40+00:00',
#        services,
#        5,
#        'LLC Workaround',
#    )
#    assert receipt_id == expected_receipt_id
#    assert link == expected_link
#
#
#def test_transfer(client_bank, requests_mock):
#    url = client_bank.get_full_url('transfer')
#    expected_completed = False
#    expected_status = 'new'
#    expected_order_slug = 'external_sandbox_e3bqG7MJ'
#    expected_talkbank_commission = 2500
#    expected_beneficiary_partner_commission = None
#    mock_response = {
#        "completed": expected_completed,
#        "status": expected_status,
#        "order_slug": expected_order_slug,
#        "talkbank_commission": expected_talkbank_commission,
#        "beneficiary_partner_commission": (
#            expected_beneficiary_partner_commission
#        ),
#    }
#    requests_mock.post(url, json=mock_response)
#    result = client_bank.transfer(
#        Decimal('10.00'),
#        '00000000000000000001',
#        '000000001',
#        'Рога и Копыта',
#        '1231231231',
#    )
#    assert result.completed == expected_completed
#    assert result.status == expected_status
#    assert result.order_slug == expected_order_slug
#    assert result.talkbank_commission == Decimal(
#        str(expected_talkbank_commission / 100),
#    )
#    assert (
#        result.beneficiary_partner_commission == Decimal('0.00')
#    )
#
#
#def test_get_transfer_status(client_bank, requests_mock):
#    expected_completed = True
#    expected_status = 'success'
#    expected_order_slug = 'transfer_xxxx'
#    expected_talkbank_commission = 2500
#    expected_beneficiary_partner_commission = None
#    mock_response = {
#        "completed": expected_completed,
#        "status": expected_status,
#        "order_slug": expected_order_slug,
#        "talkbank_commission": expected_talkbank_commission,
#        "beneficiary_partner_commission": (
#            expected_beneficiary_partner_commission
#        ),
#    }
#    url = client_bank.get_full_url(
#        'get_transfer_status', order_slug=expected_order_slug,
#    )
#    requests_mock.get(url, json=mock_response)
#    result = client_bank.get_transfer_status(expected_order_slug)
#    assert result.completed == expected_completed
#    assert result.status == expected_status
#    assert result.order_slug == expected_order_slug
#    assert result.talkbank_commission == Decimal(
#        str(expected_talkbank_commission / 100),
#    )
#    assert result.beneficiary_partner_commission == Decimal('0.00')
#
#
#def test_cancel_receipt(client_bank, requests_mock):
#    client_id = 'abc123'
#    mock_response = {
#        'client_id': client_id,
#        'status': 'success',
#        'data': {
#            'RequestResult': 'DELETED'
#        }
#    }
#    url = client_bank.get_full_url(
#        'cancel_receipt', client_id=client_id,
#    )
#    requests_mock.delete(url, json=mock_response)
#    receipt_id = '640243'
#    reason = CancelReceiptReason.refund
#    client_bank.cancel_receipt(client_id, receipt_id, reason)
