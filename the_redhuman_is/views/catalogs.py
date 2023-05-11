# -*- coding: utf-8 -*-

import json

from django.urls import reverse
from django.forms import modelformset_factory
from django.http import HttpResponse, HttpResponseRedirect
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render

from django.views.decorators.http import require_POST

from urllib.parse import quote_plus

from applicants.models import AllowedStatusTransition
from applicants.models import ApplicantSource
from applicants.models import Status
from applicants.models import StatusFinal
from applicants.models import StatusInitial
from applicants.models import StatusOrder
from applicants.models import VacantCustomerLocation

from ..auth import staff_account_required

from the_redhuman_is.models import AccountablePerson
from the_redhuman_is.models import AdministrationCostType
from the_redhuman_is.models import Country
from the_redhuman_is.models import Creditor
from the_redhuman_is.models import DevelopmentManagerPosition
from the_redhuman_is.models import IndustrialCostType
from the_redhuman_is.models import LegalEntity
from the_redhuman_is.models import MaintenanceManagerPosition
from the_redhuman_is.models import Metro
from the_redhuman_is.models import Position
from the_redhuman_is.models import Worker

from the_redhuman_is.models import legal_entity

from the_redhuman_is import forms

from the_redhuman_is.forms import AdministrationCostTypeFormSet
from the_redhuman_is.forms import CountryFormSet
from the_redhuman_is.forms import CreditorFormSet
from the_redhuman_is.forms import DManagerPositionFormSET
from the_redhuman_is.forms import DPositionForm
from the_redhuman_is.forms import IndustrialCostTypeFormSet
from the_redhuman_is.forms import MManagerPositionFormSET
from the_redhuman_is.forms import MPositionForm
from the_redhuman_is.forms import MetroFormSet
from the_redhuman_is.forms import NameForm
from the_redhuman_is.forms import PositionFormSet
from the_redhuman_is.forms import VacantCustomerLocationForm


from finance.models import Account

from the_redhuman_is.metro_models import City, MetroBranch, MetroStation

from the_redhuman_is.metro_forms import CityForm, MetroBranchForm, MetroStationForm


@staff_account_required
def index(request):
    return render(
        request,
        'the_redhuman_is/catalogs/index.html'
    )


# deprecated
@staff_account_required
def metro(request):
    stations = Metro.objects.all().order_by('name')
    return render(request, 'the_redhuman_is/catalogs/metro.html', {'stations': stations})


@staff_account_required
def manage_metro(request):
    if request.method == "POST":
        formset = MetroFormSet(
            request.POST,
        )

        if formset.is_valid():
            pks = []
            stations = formset.save(commit=False)

            for form in formset:
                if form['id'].value() != '':
                    pks.append(int(form['id'].value()))

            for station in stations:
                station.save()
                if station.id not in pks:
                    pks.append(station.id)

            for form in formset.deleted_forms:
                pk = int(form['id'].value())
                Metro.objects.filter(pk=pk).delete()
                pks.remove(pk)

            pks.sort()

            return JsonResponse({'success': True, 'pks': pks})
        else:
            return JsonResponse(formset.errors, status=400, safe=False)


def metro_new(request):
    return render(request, 'the_redhuman_is/catalogs/metro_new.html')


def ajax_metro_new(request):
    data = {}
    cities = [city.get_dict() for city in City.objects.all()]
    data['cities'] = cities
    branches = [branch.get_dict() for branch in MetroBranch.objects.all()]
    data['branches'] = branches
    stations = [station.get_dict() for station in MetroStation.objects.all()]
    data['stations'] = stations

    return JsonResponse(data)


def manage_metro_new(request):
    print(request.GET)
    model = request.GET.get('model') or None
    # data = request.GET.getlist('data') or None
    # print(data)
    action = request.GET.get('action') or None
    status = 'error'
    form = None

    entity = None
    if action == 'delete':
        pk = request.GET.get('pk') or None
        obj = None
        if model == 'city':
            obj = City.objects.filter(pk=pk).first()
        elif model == 'branch':
            obj = MetroBranch.objects.filter(pk=pk).first()
        elif model == 'station':
            obj = MetroStation.objects.filter(pk=pk).first()
        if obj:
            obj.delete()
            status = 'ok'
            entity = {'pk': pk}

    elif action == 'create':
        if model == 'city':
            form = CityForm(request.GET)
        elif model == 'branch':
            form = MetroBranchForm(request.GET)
        elif model == 'station':
            form = MetroStationForm(request.GET)
        # print("form: {}".format(form))
        if form and form.is_valid():
            obj = form.save(commit=False)
            obj.save()
            entity = obj.get_dict()
            status = 'ok'
    elif action == 'edit':
        pk = request.GET.get('pk') or None
        if model == 'city':
            obj = City.objects.filter(pk=pk).first()
            form = CityForm(request.GET, instance=obj)
        elif model == 'branch':
            obj = MetroBranch.objects.filter(pk=pk).first()
            form = MetroBranchForm(request.GET, instance=obj)
        elif model == 'station':
            obj = MetroStation.objects.filter(pk=pk).first()
            form = MetroStationForm(request.GET, instance=obj)
        if form and form.is_valid():
            obj = form.save(commit=True)
            entity = obj.get_dict()
            status = 'ok'
    errors = {}
    # print(form)
    if not status == 'ok':
        errors['all'] = form.errors['__all__'] if '__all__' in form.errors.keys() else None
        for field in form:
            errors[field.name] = " ".join(field.errors)
        print(errors)
    return JsonResponse({'status': status, 'errors': errors, 'action': action, 'model': model, 'entity': entity})


@staff_account_required
def metro_create(request):
    Metro.objects.all().delete()
    metros = [
        'Авиамоторная',
        'Автозаводская',
        'Академическая',
        'Александровский сад',
        'Алексеевская',
        'Алма-Атинская',
        'Алтуфьево',
        'Аннино',
        'Арбатская',
        'Аэропорт',
        'Авиамоторная',
        'Аминьевское шоссе',
        'Бабушкинская',
        'Багратионовская',
        'Баррикадная',
        'Бауманская',
        'Беговая',
        'Белорусская',
        'Беляево',
        'Бибирево',
        'Библиотека имени Ленина',
        'Битцевский парк',
        'Борисово',
        'Боровицкая',
        'Ботанический сад',
        'Братиславская',
        'Бульвар адмирала Ушакова',
        'Бульвар Дмитрия Донского',
        'Бульвар Рокоссовского',
        'Бунинская Аллея',
        'Бутырская',
        'Беломорская улица',
        'Боровское шоссе',
        'Бутырская',
        'Варшавская',
        'ВДНХ',
        'Владыкино',
        'Водный стадион',
        'Войковская',
        'Волгоградский проспект',
        'Волжская',
        'Волоколамская',
        'Воробьевы горы',
        'Выставочная',
        'Выхино',
        'Верхние Лихоборы',
        'Волхонка',
        'Воронцовская',
        'Деловой центр',
        'Динамо',
        'Дмитровская',
        'Добрынинская',
        'Домодедовская',
        'Достоевская',
        'Дубровка',
        'Давыдково',
        'Деловой центр',
        'Дорогомиловская',
        'Жулебино',
        'Зябликово',
        'Измайловская',
        'Калужская',
        'Кантемировская',
        'Каховская',
        'Каширская',
        'Киевская',
        'Китай-город',
        'Кожуховская',
        'Коломенская',
        'Комсомольская',
        'Коньково',
        'Котельники',
        'Красногвардейская',
        'Краснопресненская',
        'Красносельская',
        'Красные ворота',
        'Крестьянская застава',
        'Кропоткинская',
        'Крылатское',
        'Кузнецкий мост',
        'Кузьминки',
        'Кунцевская',
        'Кунцевская',
        'Курская',
        'Кутузовская',
        'Каховская',
        'Каширская',
        'Кленовый бульвар',
        'Косино',
        'Кунцевская',
        'Ленинский проспект',
        'Лермонтовский проспект',
        'Лесопарковая',
        'Лубянка',
        'Люблино',
        'Лефортово',
        'Ломоносовский проспект',
        'Лухмановская',
        'Марксистская',
        'Марьина роща',
        'Марьино',
        'Маяковская',
        'Медведково',
        'Международная',
        'Менделеевская',
        'Митино',
        'Молодежная',
        'Мякинино',
        'Минская',
        'Мичуринский проспект',
        'Нагатинская',
        'Нагорная',
        'Нахимовский Проспект',
        'Новогиреево',
        'Новокосино',
        'Новокузнецкая',
        'Новослободская',
        'Новоясеневская',
        'Новые Черёмушки',
        'Некрасовка',
        'Нижегородская улица',
        'Нижние Мневники',
        'Нижняя Масловка',
        'Новопеределкино',
        'Октябрьская',
        'Октябрьское поле',
        'Орехово',
        'Отрадное',
        'Охотный ряд',
        'Окружная',
        'Окская улица',
        'Очаково',
        'Павелецкая',
        'Парк Культуры',
        'Парк Победы',
        'Партизанская',
        'Первомайская',
        'Перово',
        'Петровско-Разумовская',
        'Печатники',
        'Пионерская',
        'Планерная',
        'Площадь Ильича',
        'Площадь Революции',
        'Полежаевская',
        'Полянка',
        'Пражская',
        'Преображенская площадь',
        'Пролетарская',
        'Проспект Вернадского',
        'Проспект Мира',
        'Профсоюзная',
        'Пушкинская',
        'Пятницкое шоссе',
        'Петровский парк',
        'Петровско-Разумовская',
        'Печатники',
        'Плющиха',
        'Проспект Вернадского',
        'Речной вокзал',
        'Рижская',
        'Римская',
        'Румянцево',
        'Рязанский проспект',
        'Раменки',
        'Рассказовка',
        'Ржевская',
        'Рубцовская',
        'Савеловская',
        'Саларьево',
        'Свиблово',
        'Севастопольская',
        'Семеновская',
        'Серпуховская',
        'Славянский бульвар',
        'Смоленская',
        'Сокол',
        'Сокольники',
        'Спартак',
        'Спортивная',
        'Сретенский бульвар',
        'Строгино',
        'Студенческая',
        'Сухаревская',
        'Сходненская',
        'Севастопольский проспект',
        'Селигерская',
        'Солнцево',
        'Стахановская',
        'Стромынка',
        'Таганская',
        'Тверская',
        'Театральная',
        'Текстильщики',
        'Теплый стан',
        'Технопарк',
        'Тимирязевская',
        'Третьяковская',
        'Тропарёво',
        'Трубная',
        'Тульская',
        'Тургеневская',
        'Тушинская',
        'Текстильщики',
        'Терехово',
        'Улица 1905 года',
        'Улица академика Янгеля',
        'Улица Горчакова',
        'Улица Скобелевская',
        'Улица Старокачаловская',
        'Университет',
        'Улица Дмитриевского',
        'Улица Народного ополчения',
        'Улица Новаторов',
        'Филевский парк',
        'Фили',
        'Фонвизинская',
        'Фрунзенская',
        'Фонвизинская',
        'Царицыно',
        'Цветной бульвар',
        'Черкизовская',
        'Чертановская',
        'Чеховская',
        'Чистые пруды',
        'Чкаловская',
        'Шаболовская',
        'Шипиловская',
        'Шоссе Энтузиастов',
        'Шелепиха',
        'Шереметьевская',
        'Щелковская',
        'Щукинская',
        'Электрозаводская',
        'Юго-Западная',
        'Южная',
        'Юго-Восточная',
        'Ясенево'
        ]
    for item in metros:
        metro_obj = Metro.objects.create(name=item)
        metro_obj.save()
    return HttpResponse("Данные метро сохранены")


@staff_account_required
def country(request):
    countries = Country.objects.all().order_by('name')
    return render(request, 'the_redhuman_is/catalogs/country.html', {'countries': countries})


@staff_account_required
def country_create(request):
    Country.objects.all().delete()
    countries = ["РФ", "Киргизия", "Казахстан", "Узбекистан", "Украина", "Белоруссия", "Таджикистан",
                 "Республика Армения", "Республика Молдова"]
    for c in countries:
        country_obj = Country.objects.create(name=c)
        country_obj.save()
    return HttpResponse("Данные стран сохранены")


@staff_account_required
def manage_country(request):
    if request.method == "POST":
        formset = CountryFormSet(
            request.POST,
        )

        if formset.is_valid():
            pks = []
            countries = formset.save(commit=False)

            for form in formset:
                if form['id'].value() != '':
                    pks.append(int(form['id'].value()))

            for c in countries:
                c.save()
                if c.id not in pks:
                    pks.append(c.id)

            for form in formset.deleted_forms:
                pk = int(form['id'].value())
                Country.objects.filter(pk=pk).delete()
                pks.remove(pk)

            pks.sort()

            return JsonResponse({'success': True, 'pks': pks})
        else:
            return JsonResponse(formset.errors, status=400, safe=False)


@staff_account_required
def position(request):
    positions = Position.objects.all().order_by('name')
    return render(request, 'the_redhuman_is/catalogs/position.html', {'positions': positions})


@staff_account_required
def position_create(request):
    Position.objects.all().delete()
    positions = ["Грузчик", "Стажер", "Бригадир"]
    for p in positions:
        position = Position.objects.create(name=p)
        position.save()
    return HttpResponse("Данные должностей сохранены")


@staff_account_required
def manage_position(request):
    if request.method == "POST":
        formset = PositionFormSet(
            request.POST,
        )

        if formset.is_valid():
            pks = []
            positions = formset.save(commit=False)

            for form in formset:
                if form['id'].value() != '':
                    pks.append(int(form['id'].value()))

            for p in positions:
                p.save()
                if p.id not in pks:
                    pks.append(p.id)

            for form in formset.deleted_forms:
                pk = int(form['id'].value())
                Position.objects.filter(pk=pk).delete()
                pks.remove(pk)

            pks.sort()

            return JsonResponse({'success': True, 'pks': pks})
        else:
            return JsonResponse(formset.errors, status=400, safe=False)


# Менеджеры по ведению

@staff_account_required
def m_manager_position(request):
    mpositions = MaintenanceManagerPosition.objects.all().order_by('position__name')
    return render(request, 'the_redhuman_is/catalogs/m_manager_position.html', {'mpositions': mpositions})


@staff_account_required
def manage_m_manager_position(request):
    if request.method == "POST":
        formset = MManagerPositionFormSET(
            request.POST,
        )

        if formset.is_valid():
            pks = []
            positions = formset.save(commit=False)

            for form in formset:
                if form['id'].value() != '':
                    pks.append(int(form['id'].value()))

            for p in positions:
                p.save()
                if p.pk not in pks:
                    pks.append(p.pk)

            for form in formset.deleted_forms:
                pk = int(form['id'].value())
                MaintenanceManagerPosition.objects.filter(pk=pk).delete()
                pks.remove(pk)

            pks.sort()

            return JsonResponse({'success': True, 'pks': pks})
        else:
            return JsonResponse(formset.errors, status=400, safe=False)
    else:
        n = request.GET.get("n")
        prefix = 'form-' + n
        form = MPositionForm(prefix=prefix)
        return render(request, 'the_redhuman_is/catalogs/manager_position_form.html', {'form': form})


# Менеджеры по развитию

@staff_account_required
def d_manager_position(request):
    dpositions = DevelopmentManagerPosition.objects.all().order_by('position__name')
    return render(request, 'the_redhuman_is/catalogs/d_manager_position.html', {'dpositions': dpositions})


@staff_account_required
def manage_d_manager_position(request):
    if request.method == "POST":
        formset = DManagerPositionFormSET(
            request.POST,
        )

        if formset.is_valid():
            pks = []
            positions = formset.save(commit=False)

            for form in formset:
                if form['id'].value() != '':
                    pks.append(int(form['id'].value()))

            for p in positions:
                p.save()
                if p.pk not in pks:
                    pks.append(p.pk)

            for form in formset.deleted_forms:
                pk = int(form['id'].value())
                DevelopmentManagerPosition.objects.filter(pk=pk).delete()
                pks.remove(pk)

            pks.sort()

            return JsonResponse({'success': True, 'pks': pks})
        else:
            return JsonResponse(formset.errors, status=400, safe=False)
    else:
        n = request.GET.get("n")
        prefix = 'form-' + n
        form = DPositionForm(prefix=prefix)
        return render(request, 'the_redhuman_is/catalogs/manager_position_form.html', {'form': form})

#Кредиторы

@staff_account_required
def creditor(request):
    creditors = Creditor.objects.all().order_by('name')
    return render(request, 'the_redhuman_is/catalogs/creditor.html', {'creditors': creditors})


@staff_account_required
def manage_creditor(request):
    if request.method == "POST":
        formset = CreditorFormSet(
            request.POST,
        )

        if formset.is_valid():
            pks = []
            creditors = formset.save(commit=False)

            for form in formset:
                if form['id'].value() != '':
                    pks.append(int(form['id'].value()))

            for creditor_obj in creditors:
                creditor_obj.save()
                if creditor_obj.id not in pks:
                    pks.append(creditor_obj.id)

            for form in formset.deleted_forms:
                pk = int(form['id'].value())
                Creditor.objects.filter(pk=pk).delete()
                pks.remove(pk)

            pks.sort()

            return JsonResponse({'success': True, 'pks': pks})
        else:
            return JsonResponse(formset.errors, status=400, safe=False)


#Виды расходов, Администрация

@staff_account_required
def administration_cost_type(request):
    administration_cost_types = AdministrationCostType.objects.all().order_by('name')
    messages = []
    account_90_2_root = Account.objects.filter(name="Общехозяйственные расходы",parent__name__startswith="2").count()
    if account_90_2_root == 0:
        messages.append("Нет корневого счета в 90.2")
    account_90_9_root = Account.objects.filter(name="Общехозяйственные расходы", parent__name__startswith="9").count()
    if account_90_9_root == 0:
        messages.append("Нет корневого счета в 90.9")
    print(messages)
    return render(request, 'the_redhuman_is/catalogs/administration_cost_type.html', {'administration_cost_types': administration_cost_types, 'messages': messages})


#Виды производственных расходов

@staff_account_required
def industrial_cost_type(request):
    industrial_cost_types = IndustrialCostType.objects.all().order_by('name')
    return render(request, 'the_redhuman_is/catalogs/industrial_cost_type.html', {'industrial_cost_types': industrial_cost_types,})


@staff_account_required
def manage_administration_cost_type(request):
    if request.method == "POST":
        formset = AdministrationCostTypeFormSet(
            request.POST,
        )

        if formset.is_valid():
            pks = []
            administration_cost_types = formset.save(commit=False)

            for form in formset:
                if form['id'].value() != '':
                    pks.append(int(form['id'].value()))

            for administration_cost_type in administration_cost_types:
                administration_cost_type.save()
                if administration_cost_type.id not in pks:
                    pks.append(administration_cost_type.id)

            for form in formset.deleted_forms:
                pk = int(form['id'].value())
                AdministrationCostType.objects.filter(pk=pk).delete()
                pks.remove(pk)

            pks.sort()

            return JsonResponse({'success': True, 'pks': pks})
        else:
            return JsonResponse(formset.errors, status=400, safe=False)
    elif request.method == "GET":
        type_pk = request.GET.get("pk")
        action = request.GET.get("action")
        if type_pk is not None:
            cost_type = AdministrationCostType.objects.get(pk=type_pk)
            # if cost_type.account_90_1 is None:
            #     root_90_1 = Account.objects.filter(
            #         name="Общехозяйственные расходы", parent__name__startswith="1").first()
            #     if root_90_1 is None:
            #         raise Exception("Нет корневого счета в 90.1")
            #     cost_type.account_90_1 = Account.objects.create(name=cost_type.name, parent=root_90_1)
            #     cost_type.save()
            cost_type.save()
            '''if cost_type.account_90_2 is None:
                root_90_2 = Account.objects.filter(name="Общехозяйственные расходы", parent__name__startswith="2").first()
                if root_90_2 is None:
                    raise Exception("Нет корневого счета в 90.2")
                cost_type.account_90_2 = Account.objects.create(name=cost_type.name, parent=root_90_2)
                cost_type.save()

            if cost_type.account_90_9 is None:
                root_90_9 = Account.objects.filter(name="Общехозяйственные расходы", parent__name__startswith="9").first()
                if root_90_9 is None:
                    raise Exception("Нет корневого счета в 90.9")
                cost_type.account_90_9 = Account.objects.create(name=cost_type.name, parent=root_90_9)
                cost_type.save()'''

        elif action == "none-root":
            account_90 = Account.objects.get(name__startswith="90.", parent=None)
            # root_90_1 = Account.objects.filter(name="Общехозяйственные расходы", parent__name__startswith="1").first()
            # if root_90_1 is None:
            root_90_2 = Account.objects.filter(name="Общехозяйственные расходы", parent__name__startswith="2").first()
            if root_90_2 is None:
                account_90_2 = Account.objects.get(name__startswith="2", parent=account_90)
                Account.objects.create(name="Общехозяйственные расходы", parent=account_90_2)
            root_90_9 = Account.objects.filter(name__startswith="9.", parent=account_90).first()
            if root_90_9 is None:
                root_90_9 = Account.objects.create(name="9. Прибыли и убытки", parent=account_90)
            account_90_9 = Account.objects.filter(name="Общехозяйственные расходы", parent=root_90_9).first()
            if account_90_9 is None:
                # account_90_9 = Account.objects.get(name__startswith="9", parent=account_90)
                Account.objects.create(name="Общехозяйственные расходы", parent=root_90_9)
        return JsonResponse({"success": True})


@staff_account_required
def manage_industrial_cost_type(request):
    if request.method == "POST":
        formset = IndustrialCostTypeFormSet(
            request.POST,
        )

        if formset.is_valid():
            pks = []
            industrial_cost_types = formset.save(commit=False)

            for form in formset:
                if form['id'].value() != '':
                    pks.append(int(form['id'].value()))

            for industrial_cost_type in industrial_cost_types:
                industrial_cost_type.save()
                if industrial_cost_type.id not in pks:
                    pks.append(industrial_cost_type.id)

            for form in formset.deleted_forms:
                pk = int(form['id'].value())
                IndustrialCostType.objects.filter(pk=pk).delete()
                pks.remove(pk)

            pks.sort()

            return JsonResponse({'success': True, 'pks': pks})
        else:
            return JsonResponse(formset.errors, status=400, safe=False)


@staff_account_required
def accountable_persons(request):
    message = request.GET.get("message") or None
    error = True if request.GET.get("error") == "true" else False
    persons = AccountablePerson.objects.all()
    for person in persons:
        person.as_str = str(person.worker)
    worker_form = forms.WorkerSearchForm()
    return render(request, 'the_redhuman_is/catalogs/accountable_person.html', {'persons': persons, 'worker_form': worker_form, "message": message, "error": error})


@staff_account_required
def manage_accountable_persons(request):
    error = "false"
    if (request.GET.get('action') or None) == 'create':
        worker_id = request.GET.get('worker') or None
        worker = get_object_or_404(Worker, pk=worker_id) # Worker.objects.filter(pk=worker_id).first()
        if AccountablePerson.objects.filter(worker=worker).count() == 0:
            person = AccountablePerson.objects.create(worker=worker)
            message = 'Добавлено подотчетное лицо ' + str(worker)
        else:
            message = 'Подотчетное лицо уже существует'
            error = 'true'
    elif (request.GET.get('action') or None) == 'delete':
        worker_id = request.GET.get('worker') or None
        worker = get_object_or_404(Worker,pk=worker_id)
        person = AccountablePerson.objects.filter(worker=worker)
        if person is None:
            message = 'Выбранного подотчетного лица не существует'
            error = "true"
        else:
            person.delete()
            message = 'Удалено подотчетное лицо ' + str(worker)
    else:
        message = 'Не выбрано действие'
        error = "true"

    return HttpResponseRedirect(reverse('the_redhuman_is:accountable_persons')+'?message='+quote_plus(message)+'&error='+error)


@staff_account_required
def applicant_status(request):
    return render(
        request,
        'the_redhuman_is/catalogs/applicant_status.html',
        {
            'title': 'Статусы соискателей',
        }
    )


@staff_account_required
def applicant_status_ajax(request):
    data = []
    for status in Status.objects.filter(active=True):
        item = {
            'id': status.pk,
            'name': status.name,
            'is_initial': hasattr(status, 'initial'),
            'is_final': hasattr(status, 'final'),
            'children': list(status.children),
        }
        if hasattr(status, 'order'):
            item['order'] = status.order.order_int
        data.append(item)
    return JsonResponse(data, safe=False)


@staff_account_required
def applicant_status_manage(request):
    if request.method == "POST":
        data = json.loads(request.body)
        status = None
        parent = None
        if 'new_status' in data:
            status = Status.objects.create(name=data['new_status'])
        if 'status' in data:
            status = Status.objects.get(id=data['status'])
        if 'parent' in data:
            parent = Status.objects.get(id=data['parent'])
        if 'is_initial' in data:
            if data['is_initial']:
                if not hasattr(status, 'initial'):
                    StatusInitial.objects.create(status=status)
            else:
                if hasattr(status, 'initial'):
                    status.initial.delete()
        if 'is_final' in data:
            if data['is_final']:
                if not hasattr(status, 'final'):
                    StatusFinal.objects.create(status=status)
            else:
                if hasattr(status, 'final'):
                    status.final.delete()

        if 'order' in data:
            order = int(data['order'])
            if hasattr(status, 'order'):
                status.order.order_int = order
                status.order.save()
            else:
                StatusOrder.objects.create(status=status, order_int=order)

        if status and parent:
            AllowedStatusTransition.objects.create(
                status_from=parent,
                status_to=status
            )
        return JsonResponse({'id': status.pk, 'name': status.name})
    return JsonResponse('error', status=400, safe=False)


@staff_account_required
def applicant_status_delete(request):
    if request.method == "POST":
        data = json.loads(request.body)
        if 'status' in data:
            if 'parent' in data:
                allowed_transition = AllowedStatusTransition.objects.get(
                    status_from=data['parent'],
                    status_to=data['status']
                )
                allowed_transition.delete()
            else:
                status = Status.objects.get(pk=data['status'])
                status.active = False
                status.save()
            return JsonResponse({'id': data['status'], 'status': 'deleted'})
    return JsonResponse('error', status=400, safe=False)


@staff_account_required
def applicant_sources(request):
    sources = ApplicantSource.objects.all().order_by('name')
    return render(
        request,
        'the_redhuman_is/catalogs/catalog_table.html',
        {
            'title': 'Источники информации',
            'items': sources,
            'table_row_title': 'Название',
            'form_action': reverse('the_redhuman_is:catalog_applicant_sources_manage'),
        }
    )


@staff_account_required
def applicant_sources_manage(request):
    if request.method == "POST":
        formset = modelformset_factory(ApplicantSource, form=NameForm,
                                       fields=('name',))
        formset = formset(request.POST)
        if formset.is_valid():
            pks = []
            formset.save()
            for form in formset:
                if form['id'].value() != '':
                    pks.append(int(form['id'].value()))
            return JsonResponse({'success': True, 'pks': pks})
        else:
            return JsonResponse(formset.errors, status=400, safe=False)


@staff_account_required
def applicant_locations(request):
    locations = VacantCustomerLocation.objects.all().order_by('location__location_name')
    return render(
        request,
        'the_redhuman_is/catalogs/applicants_locations_table.html',
        {
            'title': 'Доступные объекты',
            'items': locations,
            'table_row_title': 'Название',
            'form': VacantCustomerLocationForm()
        }
    )


@staff_account_required
def applicant_locations_manage(request):
    if request.method == "POST":
        for item in request.POST.getlist('location'):
            VacantCustomerLocation.objects.get_or_create(location_id=item)
    return HttpResponseRedirect(
        reverse('the_redhuman_is:catalog_applicant_locations')
    )


@staff_account_required
def legal_entities(request):
    return render(
        request,
        'the_redhuman_is/catalogs/legal_entity.html',
        {
            'legal_entities': LegalEntity.objects.all()
        }
    )


@require_POST
@staff_account_required
def create_legal_entity(request):
    short_name = request.POST['name']
    if LegalEntity.objects.filter(short_name=short_name).exists():
        raise Exception('Юрлицо с именем {} уже заведено'.format(short_name))
    simple_taxes = (request.POST.get('simple_taxes') == 'on')
    legal_entity.create_legal_entity(short_name, simple_taxes)
    return redirect('the_redhuman_is:catalog_legal_entities')


@require_POST
@staff_account_required
def delete_legal_entity(request, pk):
    entity = LegalEntity.objects.get(pk=pk)
    entity.try_to_delete()
    return redirect('the_redhuman_is:catalog_legal_entities')
