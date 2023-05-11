# -*- coding: utf-8 -*-

import datetime
import random

from django.contrib.auth.models import User
from django.contrib.auth.hashers import make_password

from django.db import transaction
from django.db.models import (
    CharField,
    F,
    OuterRef,
    Q,
    Subquery,
    Value,
)
from django.db.models.functions import (
    Concat,
    NullIf,
    Replace,
    StrIndex,
    Substr,
    Upper,
)

from django.utils import timezone

import applicants
import import1c

from finance.models import (
    Account,
    Operation,
)

from finance.model_utils import (
    ensure_account,
    get_root_account,
)

from the_redhuman_is import models

from the_redhuman_is.views.reports import _add_saldo
from utils.expressions import PostgresConcatWS


random.seed(1)


@transaction.atomic
def reset_workers_accounts(username, last_day):

    root_76 = get_root_account('76')
    account_76 = ensure_account(root_76, 'Расчеты с рабочими')

    workers = models.Worker.objects.all().exclude(
        worker_turnouts__timesheet__sheet_date__gt=last_day
    )

    accounts = _add_saldo(
        Account.objects.filter(
            worker_account__worker__in=workers
        )
    ).annotate(
        worker=F('worker_account__worker')
    ).filter(
        Q(saldo__gt=0) | Q(saldo__lt=0)
    )

    author = User.objects.get(username=username)

    timepoint = datetime.datetime.combine(
        last_day,
        datetime.time(23, 59, 59)
    )

    operations = []

    for account in accounts:
        # need to swap accounts manually because of bulk_create
        if account.saldo > 0:
            debit = account
            credit = account_76
            amount = account.saldo
        else:
            debit = account_76
            credit = account
            amount = -account.saldo

        operations.append(
            Operation(
                timepoint=timepoint,
                author=author,
                comment='Обнуление счета работника',
                debet=debit,
                credit=credit,
                amount=amount,
            )
        )

    Operation.objects.bulk_create(operations)


@transaction.atomic
def remove_sensitive_data():
    now = timezone.now()

    # Users

    password = make_password('psw123123qwe')

    # Todo: usernames?
    User.objects.all().update(
        password=password,
        first_name=Concat(Value('Пользователь '), 'pk'),
        last_name='xxx',
        email='',
    )

    # Finance

    Operation.objects.all().update(
        amount=13,
        comment='xxx'
    )

    Account.objects.filter(
        parent__isnull=False
    ).update(
        name=Concat(Value('Счёт '), 'pk'),
        full_name=Concat(Value('Счёт '), 'pk'),
    )

    # Customers

    models.Customer.objects.all().update(
        cust_name=Concat(Value('Клиент '), 'pk')
    )

#    models.CustomerLocation.objects.all().update(
#        location_name=Concat(Value('Объект '), 'pk'),
#        location_adress='xxx',
#        location_how_to_get='xxx'
#    )

    models.CustomerRepr.objects.all().update(
        repr_last_name='xxx',
        repr_name='xxx',
        repr_patronymic='xxx',
        position='xxx',
        tel_number='xxx',
    )

    models.Contractor.objects.all().update(
        department_of_internal_affairs='xxx',
        full_name=Concat(Value('Организация '), 'pk'),
        reg_number='xxx',
        tax_number='xxx',
        reason_code='xxx',
        full_address='xxx',
        phone_number='xxx',
        manager_position='xxx',
        manager_name='xxx',
        work_address='xxx'
    )

    models.ContractorProxy.objects.all().update(
        number='xxx',
        issue_date=now
    )

    # LegalEntities

    models.LegalEntity.objects.all().update(
        short_name=Concat(Value('Юрлицо '), 'pk')
    )

    # Expenses

    models.Provider.objects.all().update(
        name=Concat(Value('Поставщик '), 'pk'),
        tax_code='xxx'
    )

    models.Expense.objects.all().update(
        amount=13,
        comment='xxx'
    )

    models.ExpenseRejection.objects.all().update(
        comment='xxx'
    )

    # Paysheets

    models.Paysheet_v2Entry.objects.all().update(
        amount=13
    )

    # Calculators

    models.CalculatorInterval.objects.all().update(
        k=1,
        b=1
    )

    models.Pair.objects.all().update(
        key=1,
        value=1
    )

    # Workers

    def get_local_kwargs(outer_ref, with_last_name=False):
        last_name = models.Worker.objects.filter(pk=OuterRef(outer_ref)).values_list('last_name')[:1]
        name = models.Worker.objects.filter(pk=OuterRef(outer_ref)).values_list('name')[:1]
        patronymic = models.Worker.objects.filter(pk=OuterRef(outer_ref)).values_list('patronymic')[:1]
        kwargs = {
            'name': Subquery(name),
            'patronymic': Subquery(patronymic),
        }
        if with_last_name:
            kwargs['last_name'] = Subquery(last_name)
        return kwargs

    selfemployment_data_qs = models.WorkerSelfEmploymentData.objects.all(
    ).annotate(
        **get_local_kwargs('worker', with_last_name=True)
    ).annotate(
        uppercase_cardholder=Upper('cardholder_name'),
        uppercase_full_name=Upper(
            PostgresConcatWS(
                Value(' '),
                F('last_name'),
                F('name'),
                NullIf(F('patronymic'), Value(''))
            )
        )
    )

    selfemployment_data_qs.exclude(
        uppercase_cardholder=F('uppercase_full_name')  # others' cards
    ).update(
        cardholder_name=PostgresConcatWS(
            Value(' '),
            F('worker_id'),
            Substr('cardholder_name', StrIndex('cardholder_name', Value(' ')) + 1),
            output_field=CharField()
        )
    )

    selfemployment_data_qs.filter(
        uppercase_cardholder=F('uppercase_full_name')  # own cards
    ).update(
        cardholder_name=PostgresConcatWS(
            Value(' '),
            F('worker_id'),
            F('name'),
            NullIf(F('patronymic'), Value(''))
        )
    )

    models.Worker.objects.all().update(
        last_name=F('pk'),
        mig_series='xxx',
        mig_number='xxx',
        m_date_of_issue=now,
        m_date_of_exp=datetime.date(year=2050, month=1, day=1),
    )
    worker_pks = list(models.Worker.objects.values_list('pk', flat=True))
    phones = ['7926' + str(i).zfill(7) for i in range(1, len(worker_pks) + 1)]
    random.shuffle(phones)
    min_birthday = datetime.date(1970, 1, 1)
    birthday_range = (datetime.date(2003, 1, 1) - min_birthday).days - 1
    for pk, tel in zip(worker_pks, phones):
        models.Worker.objects.filter(pk=pk).update(
            tel_number=tel,
            birth_date=min_birthday + datetime.timedelta(days=random.randint(0, birthday_range))
        )
    models.Worker.objects.filter(pk__in=random.sample(worker_pks, 1000)).update(birth_date=None)

    def get_image_url(prefix, suffix, pk_field='pk'):
        return Concat(
            Substr(
                Concat(
                    Value('workers/'),
                    PostgresConcatWS(
                        Value(' '),
                        Concat(Value('Рабочий '), pk_field, output_field=CharField()),
                        F('name'),
                        NullIf(F('patronymic'), Value(''))
                    ),
                    Value(prefix),
                    PostgresConcatWS(
                        Value('_'),
                        Concat(Value('Рабочий_'), pk_field, output_field=CharField()),
                        Replace(F('name'), Value(' '), Value('_')),
                        NullIf(Replace(F('patronymic'), Value(' '), Value('_')), Value('')),
                    ),
                ),
                1,
                100-len(suffix)
            ),
            Value(suffix)
        )

    models.WorkerPassport.objects.all().update(
        passport_series='xxx',
        another_passport_number='xxx',
        date_of_issue=now,
        date_of_exp=now,
        issued_by='xxx',
    )

    models.WorkerRegistration.objects.all().update(
        r_date_of_issue=now,
        city='xxx',
        street='xxx',
        house_number='xxx',
        building_number='xxx',
        appt_number='xxx',
    )

    models.WorkerPatent.objects.all().update(
        series='xxx',
        number='xxx',
        date_of_issue=now,
        date_end=now,
        issued_by='xxx',
        profession='xxx'
    )

    models.WorkerMedicalCard.objects.all().update(
        number='xxx',
        card_date_of_issue=now,
        card_date_of_exp=now,
    )

    qs = models.WorkerMedicalCard.objects.annotate(**get_local_kwargs('worker'))
    qs.exclude(image='').update(image=get_image_url('/card_', '.jpg', 'worker_id'))
    qs.exclude(image2='').update(image2=get_image_url('/card_', '_001.jpg', 'worker_id'))
    qs.exclude(image3='').update(image3=get_image_url('/card_', '_002.jpg', 'worker_id'))

    models.WorkerSNILS.objects.all().update(
        number='xxx',
        date_of_issue=now
    )

    # Contract

    qs = models.Contract.objects.annotate(**get_local_kwargs('c_worker'))
    qs.exclude(image='').update(image=get_image_url('/contract_', '.jpg', 'c_worker_id'))
    qs.exclude(image2='').update(image2=get_image_url('/contract_', '_1.jpg', 'c_worker_id'))
    qs.exclude(image3='').update(image3=get_image_url('/contract_', '_2.jpg', 'c_worker_id'))

    def get_ref_kwargs():
        return {
            'worker': Subquery(models.Contract.objects.filter(id=OuterRef('contract_id')).values('c_worker__id')[:1]),
            'name': Subquery(models.Contract.objects.filter(id=OuterRef('contract_id')).values('c_worker__name')[:1]),
            'patronymic': Subquery(models.Contract.objects.filter(id=OuterRef('contract_id')).values(
                'c_worker__patronymic')[:1]),
        }

    # NoticeOfContract

    qs = models.NoticeOfContract.objects.annotate(**get_ref_kwargs())
    qs.exclude(image='').update(image=get_image_url('/notices_of_contract_', '.jpg', 'worker'))

    # NoticeOfTermination

    qs = models.NoticeOfTermination.objects.annotate(**get_ref_kwargs())
    qs.select_related('contract').exclude(image='').update(
        image=get_image_url('/noticeoftermination_', '.jpg', 'worker'))

    # Applicants

    applicants.models.Applicant.objects.all().update(
        phone='79262222222',
        name='xxx',
        comment='xxx',
        passport_series='xxx',
        passport_number='xxx'
    )

    # Import1c

    import1c.models.AccountMapping.objects.all().delete()
    import1c.models.ImportedNode.objects.all().delete()
    import1c.models.Import.objects.all().delete()

    # GT (aka delivery)

#    models.DeliveryService.objects.all().update(
#        customer_service_name=Concat(Value('Тариф '), 'pk'),
#        operator_service_name=Concat(Value('Тариф '), 'pk')
#    )

    models.DeliveryRequest.objects.all().update(
        driver_name='XXX XXXX XXXXX',
        driver_phones='79263333333',
        comment='xxx',
    )

    models.DeliveryItem.objects.all().update(
        code=Concat(Value('code '), 'pk'), # Todo: more correct transformation
        shipment_type='xxx',
        address='xxx',
    )

    models.DeliveryWorkerFCMToken.objects.all().update(
        app_id='123',
        token='456'
    )

    models.MobileAppStatus.objects.all().update(
        app_id='123',
        version_code='1',
        device_manufacturer='Apple',
        device_model='Iphone 33'
    )

    models.DeliveryCustomerLegalEntity.objects.all().update(
        full_name=Concat(Value('Организация '), 'pk'),
        legal_address='xxx',
        mail_address='xxx',
        tax_number='xxx',
        reason_code='xxx',
        bank_name='xxx',
        bank_identification_code='xxx',
        bank_account='xxx',
        correspondent_account='xxx',
    )

    # Auth

    models.OneOffCode.objects.all().delete()

    models.UserPhone.objects.all().update(phone=79264444444)

    models.UserRegistrationInfo.objects.all().delete()

    models.ResetPasswordRequest.objects.all().delete()
