# -*- coding: utf-8 -*-

import datetime

import pytz

from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import (
    Group,
    User,
)

from django.core.exceptions import PermissionDenied

from django.urls import reverse

from django.db import transaction
from django.db.models import (
    Exists,
    OuterRef,
    Q,
    Subquery,
)

from django.http import JsonResponse

from django.shortcuts import (
    get_object_or_404,
    redirect,
    render,
)

import finance

from applicants.models import (
    active_applicants,
    possible_applicants_to_link,
)

from telegram_bot.models import TelegramUser
from telegram_bot.telegrambot import OFFICE_BOT

from the_redhuman_is import models

from the_redhuman_is.models import (
    Contract,
    TimeSheet,
    Worker,
    WorkerComments,
    WorkerMedicalCard,
    WorkerPassport,
    WorkerPatent,
    WorkerRegistration,
)

from the_redhuman_is.models.deposit import (
    ensure_worker_deposit,
    return_deposit_to_worker,
)

from the_redhuman_is.services.turnout_calculations import update_not_paid_turnout_payments

from the_redhuman_is import forms

from the_redhuman_is.forms import (
    ContractForm,
    WorkerForm,
    WorkerMedicalCardForm,
    WorkerPassportForm,
    WorkerPatentForm,
    WorkerRegistrationForm,
    WorkerSelfEmploymentDataForm,
    WorkerPhotoForm,
)
from the_redhuman_is.auth import staff_account_required

from the_redhuman_is.views import utils

from utils.date_time import date_from_string

from the_redhuman_is.views.contracts import (
    ContractorProxyForm,
    SingleContractorForm,
)


""" Карточка рабочего и карточка контракта """
# Новый рабочий
@staff_account_required
def new_worker(request):
    if request.method == "POST":
        wform = WorkerForm(request.POST, request.FILES, prefix='worker')
        wpform = WorkerPassportForm(request.POST, prefix='passport')
        wrform = WorkerRegistrationForm(request.POST, prefix='reg')
        wpaform = WorkerPatentForm(request.POST, prefix='patent')
        med_card_form = forms.WorkerMedicalCardForm(request.POST, request.FILES,
                                                    prefix='med')
        ok = True
        worker = None
        if wform.is_valid() and wpform.is_valid():
            worker = wform.save()

            ensure_worker_deposit(worker)

            workerpassport = wpform.save(commit=False)
            workerpassport.workers_id = worker
            models.create_worker_operating_account(worker)
            if wrform.is_valid() and wpaform.is_valid() and wpaform.has_changed():
                workerregistration = wrform.save(commit=False)
                workerregistration.workers_id = worker
                workerpatent = wpaform.save(commit=False)
                workerpatent.workers_id = worker

                workerregistration.save()
                workerpatent.save()
            workerpassport.save()
            Contract.objects.create(
                end_date=min(workerpassport.date_of_exp,
                             worker.m_date_of_exp),
                cont_type=worker.contract_type,
                c_worker=worker
            ).save()
        else:
            ok = False

        if worker and med_card_form.is_valid() and med_card_form.has_changed():
            med_card = med_card_form.save(commit=False)
            med_card.worker = worker
            med_card.save()

        if ok:
            return redirect("/")

    else:
        wform = WorkerForm(prefix='worker')
        wpform = WorkerPassportForm(prefix='passport')
        wrform = WorkerRegistrationForm(prefix='reg')
        wpaform = WorkerPatentForm(request.POST, prefix='patent')
        med_card_form = forms.WorkerMedicalCardForm(prefix='med')

    return render(
        request,
        "the_redhuman_is/new_worker.html",
        {
            "wform": wform,
            "wpform": wpform,
            "wrform": wrform,
            "wpaform": wpaform,
            "med_card_form": med_card_form,
        }
    )


def _worker_detail_impl(request, worker, show_personal_info, show_turnouts):
    data = {
        'show_personal_info': show_personal_info
    }
    if show_personal_info:
        worker_images = models.get_worker_photos(worker)
        workerpasss = worker.workerpassport_set.all()
        workerpasss_active = workerpasss.filter(is_actual=True)
        workerregs = worker.workerregistration_set.all()
        workerregs_active = workerregs.filter(is_actual=True)
        workerpatents = worker.workerpatent_set.all()
        contracts = Contract.objects.filter(c_worker=worker)
        comments = WorkerComments.objects.filter(worker=worker)
        med_cards = models.WorkerMedicalCard.objects.filter(worker=worker)

        data['worker_images'] = worker_images
        data['workerpasss'] = workerpasss
        data['workerpasss_active'] = workerpasss_active
        data['workerregs'] = workerregs
        data['workerregs_active'] = workerregs_active
        data['workerpatents'] = workerpatents
        data['contractor_form'] = SingleContractorForm()
        data['proxy_form'] = ContractorProxyForm()
        data['contracts'] = contracts
        data['comments'] = comments
        data['med_cards'] = med_cards


    items_with_saldo = []
    account = None
    if show_turnouts:
        turnouts = worker.worker_turnouts.filter(
            turnoutoperationtopay__isnull=True
        ).prefetch_related(
            'timesheet',
            'timesheet__customer',
            'timesheet__cust_location'
        )

        items = []
        for turnout in turnouts:
            timesheet = turnout.timesheet
            item = {}
            item['timepoint'] = datetime.datetime.combine(
                timesheet.sheet_date,
                datetime.time(0, 1),
                pytz.timezone('Europe/Moscow')
            )
            item['timesheet_pk'] = timesheet.pk
            item['customer_pk'] = timesheet.customer.pk
            item['customer_name'] = timesheet.customer.cust_name
            item['location_name'] = timesheet.cust_location.location_name
            item['turn'] = timesheet.sheet_turn
            item['turnout'] = turnout.pk
            items.append(item)

        operating_account = worker.worker_account
        account = operating_account.account

        def _timesheet_subquery(field):
            return Subquery(
                models.TimeSheet.objects.filter(
                    worker_turnouts__turnoutoperationtopay__operation__pk=OuterRef('pk')
                ).values(field)
            )

        operations = finance.models.Operation.objects.filter(
            Q(debet=account) |
            Q(credit=account)
        ).annotate(
            timesheet_pk = _timesheet_subquery('pk'),
            customer_pk = _timesheet_subquery('customer'),
            customer_name = _timesheet_subquery('customer__cust_name'),
            location_name = _timesheet_subquery('cust_location__location_name'),
            turn = _timesheet_subquery('sheet_turn'),
            hours_worked = Subquery(
                models.WorkerTurnout.objects.filter(
                    turnoutoperationtopay__operation__pk=OuterRef('pk')
                ).values('hours_worked')
            ),
            turnout = Subquery(
                models.WorkerTurnout.objects.filter(
                    turnoutoperationtopay__operation__pk=OuterRef('pk')
                ).values('pk')
            ),
            paysheet = Subquery(
                models.Paysheet_v2.objects.filter(
                    paysheet_entries__operation__pk=OuterRef('pk')
                ).values('pk')
            ),
            prepayment = Subquery(
                models.Prepayment.objects.filter(
                    workers__operation__pk=OuterRef('pk')
                ).values('pk')
            ),
            is_in_paysheet = Exists(
                models.Paysheet_v2EntryOperation.objects.filter(
                    operation__pk=OuterRef('pk')
                )
            )
        ).prefetch_related(
            'debet',
            'credit',
        ).order_by('timepoint')

        for operation in operations:
            item = {}
            item['pk'] = operation.pk
            item['timepoint'] = operation.timepoint
            item['comment'] = operation.comment
            item['amount'] = operation.amount
            item['debet'] = operation.debet
            item['credit'] = operation.credit

            if operation.timesheet_pk:
                item['timesheet_pk'] = operation.timesheet_pk
                item['customer_pk'] = operation.customer_pk
                item['customer_name'] = operation.customer_name
                item['location_name'] = operation.location_name
                item['turn'] = operation.turn
                if operation.hours_worked is not None:
                    item['turnout'] = operation.turnout
                    item['hours_worked'] = operation.hours_worked

            url = None
            if operation.paysheet:
                url = reverse(
                    'the_redhuman_is:paysheet_v2_show',
                    kwargs={ 'pk': operation.paysheet }
                )
            if operation.prepayment:
                url = reverse(
                    'the_redhuman_is:prepayment_show',
                    kwargs={ 'pk': operation.prepayment }
                )
            if url:
                item['comment_url'] = url
            if operation.is_in_paysheet:
                item['is_in_paysheet'] = True

            items.append(item)

        items = sorted(items, key=lambda item: item['timepoint'])

        saldo = 0
        for item in items:
            if 'amount' in item.keys():
                if item['debet'] == account:
                    saldo -= item['amount']
                else:
                    saldo += item['amount']

            items_with_saldo.append((item, saldo))

    data['head_title'] = 'Рабочий №{} {}'.format(worker.pk, worker)
    data['worker'] = worker
    data['account'] = account
    data['operations'] = reversed(items_with_saldo)
    data['applicants'] = possible_applicants_to_link(worker)
    data['selfemployment_data'] = worker.selfemployment_data.order_by('-deletion_ts', '-pk').first()

    return render(
        request,
        'the_redhuman_is/worker_detail_new.html',
        data
    )


# Карточка рабочего
@login_required
def worker_detail(request, pk):
    worker = get_object_or_404(Worker, pk=pk)

    user_groups = request.user.groups.values_list('name', flat=True)

    every_worker_allowed = request.user.is_superuser or 'Касса' in user_groups
    allowed_positions = ('грузчик', 'бригадир')
    if not every_worker_allowed and worker.position.name.lower() not in allowed_positions:
        raise PermissionDenied()

    show_personal_info = True
    if 'Менеджеры' in user_groups:
        show_personal_info = False
        customers = models.Customer.objects.filter(
            maintenancemanager__worker__workeruser__user=request.user
        )
        timesheets = TimeSheet.objects.filter(
            Q(foreman=worker) |
            Q(worker_turnouts__worker=worker),
            customer__in=customers
        )
        if not timesheets.exists():
            raise PermissionDenied()

    show_turnouts = 'Бухгалтеры внешние' not in user_groups

    return _worker_detail_impl(
        request,
        worker,
        show_personal_info,
        show_turnouts,
    )


def my_page(request):
    return _worker_detail_impl(
        request,
        get_object_or_404(
            Worker.objects.filter(workeruser__user=request.user)
        ),
        show_personal_info=True,
        show_turnouts=True,
    )


# Редактирование рабочего
@staff_account_required
def worker_edit(request, pk, msg=None):
    worker = get_object_or_404(Worker, pk=pk)
    if request.method == "POST":
        wform = WorkerForm(request.POST, request.FILES or None, instance=worker)
        photo_deletion_form = WorkerPhotoForm(request.POST, worker_pk=worker.pk)
        if wform.is_valid() and photo_deletion_form.is_valid():
            worker = wform.save()
            for photo in photo_deletion_form.cleaned_data['photos']:
                photo.delete()
            return redirect('the_redhuman_is:worker_detail', pk=worker.pk)
    else:
        wform = WorkerForm(instance=worker)
        photo_deletion_form = WorkerPhotoForm(worker_pk=worker.pk)
    return render(
        request,
        'the_redhuman_is/new_worker.html',
        {
            'wform': wform,
            'msg': msg,
            'photo_del_form': photo_deletion_form
        }
    )


# Удаление рабочего
@staff_account_required
def worker_del(request, pk):
        worker = get_object_or_404(Worker, pk=pk)
        if request.method == "POST":
            form = WorkerForm(request.POST, instance=worker)
            if form.is_valid():
                worker.delete()
                return redirect('/')
        else:
            form = WorkerForm(instance=worker)
        return render(request, 'the_redhuman_is/new_worker.html', {'form': form})


# Новый паспорт + деактивация старых паспортов
@staff_account_required
def new_passport(request, pk):
    worker = get_object_or_404(Worker, pk=pk)
    if request.method == "POST":
        npform = WorkerPassportForm(request.POST)
        if npform.is_valid():
            passport = npform.save(commit=False)
            WorkerPassport.objects.filter(workers_id=worker).update(is_actual=False)
            passport.workers_id = worker
            passport.save()
            return redirect('the_redhuman_is:worker_detail', pk=worker.pk)
    else:
        npform = WorkerPassportForm()
    return render(request, 'the_redhuman_is/new_passport.html',
                  {'npform': npform})


@staff_account_required
def edit_passport(request, pk):
    passport = get_object_or_404(WorkerPassport, pk=pk)
    if request.method == "POST":
        pform = WorkerPassportForm(request.POST, instance=passport)
        if pform.is_valid():
            pform.save()
            return redirect(
                'the_redhuman_is:worker_detail',
                pk=passport.workers_id.pk
            )
    else:
        pform = WorkerPassportForm(instance=passport)
    return render(
        request,
        'the_redhuman_is/new_passport.html',
        { 'npform': pform }
    )


# Новая регистрация
@staff_account_required
def new_registration(request, pk):
    worker = get_object_or_404(Worker, pk=pk)
    if request.method == "POST":
        nrform = WorkerRegistrationForm(request.POST)
        if nrform.is_valid():
            registration = nrform.save(commit=False)
            old_registration = WorkerRegistration.objects.filter(workers_id=worker).update(is_actual=False)
            registration.workers_id = worker
            registration.save()
            return redirect('the_redhuman_is:worker_detail', pk=worker.pk)
    else:
        nrform = WorkerRegistrationForm()
    return render(request,
                  'the_redhuman_is/new_registration.html',
                  {'nrform': nrform})


@staff_account_required
def edit_registration(request, pk):
    registration = get_object_or_404(WorkerRegistration, pk=pk)
    if request.method == "POST":
        rform = WorkerRegistrationForm(request.POST, instance=registration)
        if rform.is_valid():
            rform.save()
            return redirect('the_redhuman_is:worker_detail',
                            pk=registration.workers_id.pk)
    else:
        rform = WorkerRegistrationForm(instance=registration)
    return render(request,
                  'the_redhuman_is/new_registration.html',
                  {'nrform': rform})


# Новый патент
@staff_account_required
def new_patent(request, pk):
    worker = get_object_or_404(Worker, pk=pk)
    if request.method == "POST":
        npform = WorkerPatentForm(request.POST)
        if npform.is_valid():
            patent = npform.save(commit=False)
            WorkerPatent.objects.filter(workers_id=worker).update(is_actual=False)
            patent.workers_id = worker
            patent.save()
            return redirect('the_redhuman_is:worker_detail', pk=worker.pk)
    else:
        npform = WorkerPatentForm()
    return render(request, 'the_redhuman_is/new_patent.html', {'npform': npform})


@staff_account_required
def edit_patent(request, pk):
    patent = get_object_or_404(WorkerPatent, pk=pk)
    if request.method == "POST":
        pform = WorkerPatentForm(request.POST, instance=patent)
        if pform.is_valid():
            pform.save()
            return redirect('the_redhuman_is:worker_detail',
                            pk=patent.workers_id.pk)
    else:
        pform = WorkerPatentForm(instance=patent)
    return render(request, 'the_redhuman_is/new_patent.html', {'npform': pform})


@staff_account_required
def new_contract(request, pk):
    """Новый контракт с рабочим"""
    worker = get_object_or_404(Worker, pk=pk)
    if request.method == "POST":
        form = ContractForm(
            data=request.POST,
            files=request.FILES
        )
        if form.is_valid():
            contract = form.save(commit=False)
            old_contracts = Contract.objects.filter(c_worker=worker,
                                                    is_actual=True)
            for item in old_contracts:
                item.is_actual=False
                item.save()
            contract.c_worker = worker
            contract.end_date = worker.m_date_of_exp
            contract.save()
            return redirect('the_redhuman_is:worker_detail', pk=pk)
    else:
        form = ContractForm()
    return render(request, 'the_redhuman_is/new_contract.html', {'form': form})


@staff_account_required
def edit_contract(request, pk):
    contract = get_object_or_404(Contract, pk=pk)
    if request.method == 'POST':
        form = ContractForm(
            data=request.POST,
            files=request.FILES,
            instance=contract
        )
        if form.is_valid():
            contract = form.save()
            return redirect(
                'the_redhuman_is:worker_detail',
                pk=contract.c_worker.pk
            )
    else:
        form = ContractForm(
            readonly_dates=False,
            instance=contract
        )
    return render(request, 'the_redhuman_is/new_contract.html', {'form': form})


# Todo: don't do like this (same url for get & post requests)!
@staff_account_required
def worker_add_med_card(request, pk):
    worker = get_object_or_404(Worker, pk=pk)
    if request.method == "POST":
        form = forms.WorkerMedicalCardForm(request.POST, request.FILES)
        if form.is_valid():
            med_card = form.save(commit=False)
            med_card.worker = worker
            med_card.save()
            return redirect('the_redhuman_is:worker_detail', pk=pk)
    return render(
        request,
        "the_redhuman_is/new_medcard.html",
        {
            "form": forms.WorkerMedicalCardForm()
        }
    )


@staff_account_required
def worker_edit_med_card(request, pk):
    med_card = get_object_or_404(WorkerMedicalCard, pk=pk)
    if request.method == "POST":
        form = WorkerMedicalCardForm(request.POST, request.FILES,
                                     instance=med_card)
        if form.is_valid():
            form.save()
            return redirect('the_redhuman_is:worker_detail',
                            pk=med_card.worker.pk)
    else:
        form = WorkerMedicalCardForm(instance=med_card)
    return render(request, "the_redhuman_is/new_medcard.html", {"form": form})


# Ссылка на фото контракта
@login_required
def contract_image(request, pk):
    contract = Contract.objects.get(pk=pk)
    return utils.render_image(request, contract.image)


@login_required
def contract_image2(request, pk):
    contract = Contract.objects.get(pk=pk)
    return utils.render_image(request, contract.image2)


@login_required
def contract_image3(request, pk):
    contract = Contract.objects.get(pk=pk)
    return utils.render_image(request, contract.image3)


# Фото медкнижки
@login_required
def med_card_image(request, pk):
    med_card = models.WorkerMedicalCard.objects.get(pk=pk)
    return utils.render_image(request, med_card.image)


@login_required
def med_card_image2(request, pk):
    med_card = models.WorkerMedicalCard.objects.get(pk=pk)
    return utils.render_image(request, med_card.image2)


@login_required
def med_card_image3(request, pk):
    med_card = models.WorkerMedicalCard.objects.get(pk=pk)
    return utils.render_image(request, med_card.image3)


@login_required
def get_photo(request, pk):
    photo = models.Photo.objects.get(pk=pk)
    return utils.render_image(request, photo.image)


@staff_account_required
def return_deposit(request, pk):
    if request.method == "POST":
        worker = models.Worker.objects.get(pk=pk)
        return_deposit_to_worker(worker, request.user)
    return redirect('the_redhuman_is:worker_detail', pk=pk)


@staff_account_required
def link_applicant(request, worker_pk, applicant_pk):
    applicant = active_applicants().get(pk=applicant_pk)
    worker = models.Worker.objects.get(pk=worker_pk)

    linked_now = applicant.try_link_to_worker(request.user, 'Линковка вручную.', worker)
    if linked_now:
        applicant.try_set_final_status()

    return redirect('the_redhuman_is:worker_detail', pk=worker_pk)


@staff_account_required
def remove_applicant_link(request, worker_pk):
    worker = models.Worker.objects.get(pk=worker_pk)
    worker.applicant_link.unlink()

    return redirect('the_redhuman_is:worker_detail', pk=worker_pk)


@staff_account_required
def create_user(request, worker_pk):
    worker = models.Worker.objects.get(pk=worker_pk)

    if not worker.tel_number:
        return redirect(
            'the_redhuman_is:worker_edit',
            pk=worker_pk,
            msg="Заполните номер телефона."
        )

    with transaction.atomic():
        if not TelegramUser.objects.filter(phone=worker.tel_number):
            user = User.objects.create_user(
                username=request.POST['username'],
                password=request.POST['password'],
                first_name=worker.name,
                last_name=worker.last_name
            )
            user.groups.add(
                Group.objects.get(name='Бригадиры')
            )
            user.save()
            TelegramUser.objects.create(
                user=user,
                phone=worker.tel_number,
                bot=OFFICE_BOT,
            )

    return redirect('telegram_bot:users_list')


@staff_account_required
def snils(request, worker_pk):
    worker = models.Worker.objects.get(pk=worker_pk)

    return render(
        request,
        'the_redhuman_is/worker_snils.html',
        { 'worker' : worker }
    )


@staff_account_required
def save_snils(request, worker_pk):
    worker = models.Worker.objects.get(pk=worker_pk)

    try:
        worker.update_snils(
            request.POST.get('number'),
            date_from_string(request.POST.get('date_of_issue')),
            request.FILES.get('image')
        )
        return JsonResponse({ 'ok': True })
    except Exception as e:
        return JsonResponse({ 'error' : str(e)})


def self_employment_data(request, worker_pk):
    worker = models.Worker.objects.with_full_name().get(pk=worker_pk)
    wse_data = worker.selfemployment_data.order_by('-deletion_ts', '-pk').first()
    if wse_data is not None:
        form = WorkerSelfEmploymentDataForm(instance=wse_data)
    else:
        form = WorkerSelfEmploymentDataForm(initial={'cardholder_name': worker.full_name})

    return render(
        request,
        'the_redhuman_is/worker/self_employment_data.html',
        {
            'worker': worker,
            'form': form,
        }
    )


def save_self_employment_data(request, worker_pk):
    form = WorkerSelfEmploymentDataForm(
        request.POST,
        instance=(
            models.WorkerSelfEmploymentData.objects.filter(worker_id=worker_pk).order_by('-deletion_ts', '-pk').first()
            or models.WorkerSelfEmploymentData(worker_id=worker_pk)
        )
    )
    instance = form.save()
    update_not_paid_turnout_payments(instance.worker, request.user)
    return redirect('the_redhuman_is:worker_detail', pk=worker_pk)


@staff_account_required
def search_worker(request):
    return render(
        request,
        'the_redhuman_is/worker/search.html',
        {
            'search_form': forms.WorkerSearchForm()
        }
    )
