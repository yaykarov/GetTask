# -*- coding: utf-8 -*-

import datetime
import pytz
import re

from urllib.parse import urlencode

from dal import autocomplete

from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import User
from django.core.exceptions import MultipleObjectsReturned
from django.urls import reverse
from django.db.models import Q
from django.forms import model_to_dict
from django.http import HttpResponseRedirect, JsonResponse, HttpResponse
from django.shortcuts import render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import ListView, CreateView, UpdateView, DetailView, TemplateView
from django.views.generic.edit import FormView

from applicants import forms

from applicants.models import AllowedStatusTransition
from applicants.models import Applicant
from applicants.models import ApplicantHistoryNode
from applicants.models import ApplicantSource
from applicants.models import Status
from applicants.models import StatusFinal
from applicants.models import StatusInitial
from applicants.models import active_applicants

from the_redhuman_is.auth import staff_account_required

from the_redhuman_is.models import Metro
from the_redhuman_is.models import CustomerLocation
from the_redhuman_is.models import Country
from the_redhuman_is.models import WorkerTurnout
from utils.date_time import date_from_string
from utils.date_time import string_from_date
from utils.date_time import time_interval_format
from the_redhuman_is.views.utils import get_customer_account


def _unassigned_applicants():
    return active_applicants().filter(
        author=None,
    )


def _status_infos(applicants):
    result = []
    def _get_key(status):
        if hasattr(status, 'order'):
            return status.order.order_int
        return 0
    statuses = sorted(Status.objects.filter(active=True), key=_get_key)
    for status in statuses:
        count = applicants.filter(
            status=status
        ).count()

        result.append((status, count))

    return result


class CustomLoginRequired(LoginRequiredMixin):
    login_url = reverse_lazy('login')
    redirect_field_name = 'next'

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()

        account = get_customer_account(request)
        if account:
            return self.handle_no_permission()

        return super(CustomLoginRequired, self).dispatch(
            request,
            *args,
            **kwargs
        )


class AjaxableResponseMixin:
    def form_invalid(self, form):
        response = super().form_invalid(form)
        if self.request.is_ajax():
            return JsonResponse(form.errors, status=400)
        else:
            return response

    def form_valid(self, form):
        response = super().form_valid(form)
        if self.request.is_ajax():
            data = {
                'pk': self.object.pk,
            }
            return JsonResponse(data)
        else:
            return response


class ApplicantFormMixin(CustomLoginRequired, FormView):
    model = Applicant
    form_class = forms.ApplicantForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        data = kwargs.get('data').copy()
        data['phone'] = re.sub('[^0-9]', '', data['phone'])
        if data['next_date']:
            data['next_date'] = datetime.datetime.strptime(
                data['next_date'],
                '%d-%m-%Y'
            ).date()
        kwargs.update({'data': data})
        return kwargs

    def get_initial(self):
        if self.request.user.groups.filter(name='Подборщики'):
            return {'author': self.request.user}
        return {}


def _first_day(strange_logic=False):
    first_day = timezone.now().date()
    if strange_logic and first_day.year == 2018 and first_day.month == 11:
        first_day = first_day.replace(day=8)
    else:
        first_day = first_day.replace(day=1)
    return string_from_date(first_day)


def _base_filters(request, default_first_day=None):
    if not default_first_day:
        default_first_day = _first_day()
    first_day = request.GET.get('first_day')
    if not first_day:
        first_day = default_first_day
    manager_pk = request.GET.get('manager')
    if not manager_pk:
        if 'today_work' in request.GET:
            manager_pk = request.user.pk
    return (
        request.GET.get('source'),
        manager_pk,
        first_day,
        request.GET.get('last_day'),
    )


def _initial_filter(request, default_first_day=None):
    if not default_first_day:
        default_first_day = _first_day()
    initial = {}
    source_pk, manager_pk, first_day, last_day = _base_filters(
        request, default_first_day)
    if source_pk:
        initial['source'] = ApplicantSource.objects.get(pk=source_pk)
    if manager_pk:
        initial['manager'] = User.objects.get(pk=manager_pk)
    if not first_day:
        first_day = default_first_day
    if first_day:
        initial['first_day'] = first_day
    if last_day:
        initial['last_day'] = last_day
    return initial


class ApplicantsListView(CustomLoginRequired, ListView):
    model = Applicant

    def _extra_filters(self):
        return (
            self.request.GET.get('interval_type'),
            self.request.GET.get('filter_status'),
        )

    def _base_queryset(self):
        applicants = active_applicants()

        user_groups = self.request.user.groups.values_list('name', flat=True)
        if 'Подборщики внешние' in user_groups:
            recruitment_groups = []
            GROUP_RX = re.compile('^Подборщики внешние \d+$')
            for group in user_groups:
                m = GROUP_RX.match(group)
                if m:
                    recruitment_groups.append(group)

            external_recruiters = User.objects.filter(
                groups__name__in=recruitment_groups
            ).distinct()
            applicants = applicants.filter(
                author__in=external_recruiters
            )

        source_pk, manager_pk, first_day, last_day = _base_filters(
            self.request
        )
        interval_type, status_pk = self._extra_filters()
        if source_pk:
            applicants = applicants.filter(
                source__pk=source_pk
            )
        if manager_pk:
            applicants = applicants.filter(
                author__pk=manager_pk
            )

        if interval_type == 'turnout_date':
            # Todo: maybe there is nicer way to do this?
            pks = []
            first_date = date_from_string(first_day)
            last_date = date_from_string(last_day)
            for applicant in applicants:
                first_turnout = applicant.first_turnout_date()
                if not first_turnout:
                    continue
                if first_date and first_date > first_turnout:
                    continue
                if last_date and last_date < first_turnout:
                    continue
                pks.append(applicant.pk)

            applicants = applicants.filter(pk__in=pks)
        else:
            date_prefix = 'init_date'
            if interval_type in ['next_date', 'last_edited']:
                date_prefix = interval_type

            if first_day:
                applicants = applicants.filter(
                    **{ '{}__gte'.format(date_prefix): date_from_string(first_day)}
                )
            if last_day:
                end = date_from_string(last_day)
                if date_prefix == 'last_edited':
                    end += datetime.timedelta(days=1)
                applicants = applicants.filter(
                    **{ '{}__lte'.format(date_prefix): end }
                )

        return applicants

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user_groups = self.request.user.groups.values_list('name', flat=True)
        if 'Подборщики внешние' in user_groups:
            context['create_form'] = forms.ApplicantForm(location_pk=29)
            context['edit_form'] = forms.ApplicantForm(prefix='edit', location_pk=29)
        else:
            context['create_form'] = forms.ApplicantForm()
            context['edit_form'] = forms.ApplicantForm(prefix='edit')

        initial = _initial_filter(self.request)
        interval_type, status_pk = self._extra_filters()
        if interval_type:
            initial['interval_type'] = interval_type
        context['filter_form'] = forms.ListFilterForm(initial=initial)

        applicants = self._base_queryset()

        context['status_infos'] = _status_infos(applicants)
        context['applicants_count'] = applicants.count()

        if status_pk is not None:
            context['status_highlight'] = int(status_pk)

        for param in [
                'first_day',
                'last_day',
                'show_first_reaction',
                'show_first_turnout_date',
                'show_multiple_links',
                'today_work',
            ]:
            value = self.request.GET.get(param)
            if value:
                context[param] = value

        context['initial_status'] = StatusInitial.objects.get().status.pk

        return context

    def get_queryset(self):
        # dirty hack, I know, I know
        forced_number = self.request.GET.get('forced_number')
        if forced_number:
            nodes = ApplicantHistoryNode.objects.filter(
                applicant__active=True,
                applicant__phone=forced_number
            )
            pks = []
            for node in nodes:
                head = node.head()
                if head:
                    pk = head.applicant.pk
                    if pk not in pks:
                        pks.append(pk)
            self.queryset = active_applicants().filter(
                pk__in=pks
            )
            return self.queryset

        self.queryset = self._base_queryset()
        interval_type, status_pk = self._extra_filters()
        if interval_type == 'turnout_date':
            status_pk = StatusFinal.objects.get().status.pk
        if status_pk:
            self.queryset = self.queryset.filter(
                status__pk=status_pk
            )

        if 'today_work' in self.request.GET:
            self.queryset = self.queryset.filter(
                Q(next_date=timezone.now().date()) |
                Q(status__initial__isnull=False)
            )

        present_status_pk = self.request.GET.get('filter_has_status')
        if present_status_pk:
            status = Status.objects.get(pk=present_status_pk)
            if not hasattr(status, 'initial'):
                def _check(applicant):
                    return applicant.status == status
                pks = []
                for applicant in self.queryset.all():
                    if applicant.find_first_in_history(_check):
                        pks.append(applicant.pk)
                self.queryset = self.queryset.filter(pk__in=pks)

        return self.queryset.order_by(
            '-last_edited',
            'phone'
        ).select_related(
            'author',
            'location',
            'metro',
            'source',
            'status',
        )

    def get_template_names(self):
        return ['applicants/list.html',]


_ALREADY_WORKS_ERROR = {
    'result': 'error',
    'error': 'already_works',
    'error_text': 'Есть работник с таким номером, который уже работает, у которого нет привязки к соискателю. А создание и редактирование заявок задним числом - запрещено. Обратитесь, пожалуйста, к Светлане.'
}


class ApplicantCreateView(ApplicantFormMixin, CreateView):
    http_method_names = ['post']

    def form_valid(self, form):
        applicant = form.save(commit=False)
        applicant.author = self.request.user
        if self.request.user.is_superuser or applicant.is_valid_to_save():
            applicant.save()
            self.object = applicant
            print('Applicant just saved: {}'.format(applicant))
            return JsonResponse({'result': 'ok'})
        else:
            return JsonResponse(_ALREADY_WORKS_ERROR)

    def form_invalid(self, form):
        return HttpResponseRedirect(self.error_url)


class ApplicantDetailView(DetailView):
    model = Applicant

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        context = self.get_context_data(object=self.object)
        if self.request.is_ajax():
            data = {'object': model_to_dict(self.object)}
            if self.object.status:
                data['object']['status'] = {
                    'id': self.object.status.id,
                    'name': self.object.status.name
                }
            if data['object']['init_date']:
                data['object']['init_date'] = datetime.datetime.strftime(
                    data['object']['init_date'],
                    '%d-%m-%Y'
                )
            if data['object']['next_date']:
                data['object']['next_date'] = datetime.datetime.strftime(
                    data['object']['next_date'],
                    '%d-%m-%Y'
                )
            return JsonResponse(data)
        else:
            return self.render_to_response(context)


class ApplicantUpdateView(ApplicantFormMixin, AjaxableResponseMixin,
                          UpdateView):
    success_url = reverse_lazy('applicants:list')
    error_url = reverse_lazy('applicants:list')
    http_method_names = ['post', ]

    def form_valid(self, form):
        self.object = form.save(commit=False)

        if self.request.user.is_superuser or self.object.is_valid_to_save():
            self.object.save()
            return JsonResponse({'result': 'ok'})
        else:
            return JsonResponse(_ALREADY_WORKS_ERROR)

    def form_invalid(self, form):
        return JsonResponse({})


class ImportApplicant(CustomLoginRequired, TemplateView):
    template_name = 'applicants/upload_xls.html'

    def handle_uploaded_file(self, f):
        import os
        import tempfile
        import xlrd
        fd, path = tempfile.mkstemp()
        errors = []
        try:
            with os.fdopen(fd, 'wb') as tmp:
                tmp.write(f.read())
            book = xlrd.open_workbook(path)
            sh = book.sheet_by_index(0)
            for rownum in range(1, sh.nrows):
                try:
                    date = sh.cell_value(rownum, 1)
                    date = datetime.datetime(*xlrd.xldate_as_tuple(date, book.datemode))
                except:
                    errors.append({'row': rownum, 'error': 'дата'})
                    continue

                phone = sh.cell_value(rownum, 2)
                phone = str(phone).strip()
                phone = phone.split('.')[0]
                phone = re.sub('^8', '7', phone)
                if not phone.isdigit():
                    errors.append({'row': rownum, 'error': 'телефон'})
                    continue

                if Applicant.objects.filter(phone=phone).exists():
                    errors.append({
                        'row': rownum,
                        'error': 'соискатель с телефоном {} уже есть'.format(phone)
                    })
                    continue

                type = sh.cell_value(rownum, 4)
                if type == 'Входящий' or type == 'вх':
                    type = 'in'
                else:
                    type = 'out'

                status = sh.cell_value(rownum, 14)
                try:
                    status = Status.objects.get(name=status)
                except Status.DoesNotExist:
                    status = StatusInitial.objects.get().status

                name = sh.cell_value(rownum, 6)

                source = sh.cell_value(rownum, 3).strip()
                if source is not None:
                    try:
                        source = ApplicantSource.objects.get(name=source)
                    except ApplicantSource.DoesNotExist:
                        errors.append({'row': rownum, 'error': 'источник'})
                        source = None

                age = sh.cell_value(rownum, 7)
                age = str(age).strip().split('.')[0]
                if not age.isdigit():
                    age = None
                    errors.append({'row': rownum, 'error': 'Возраст'})

                have_docs = sh.cell_value(rownum, 8)
                if have_docs == 'есть':
                    have_docs = True
                else:
                    have_docs = False

                city = None
                metro = sh.cell_value(rownum, 9).strip()
                if metro is not None:
                    try:
                        metro = Metro.objects.get(name=metro)
                    except Metro.DoesNotExist:
                        errors.append({'row': rownum, 'error': 'метро'})
                        if metro:
                            city = metro
                        metro = None
                    except MultipleObjectsReturned:
                        metro = Metro.objects.filter(name=metro).first()

                citizenship = sh.cell_value(rownum, 5).strip()
                if citizenship is not None:
                    try:
                        citizenship = Country.objects.get(
                            name=citizenship
                        )
                    except Country.DoesNotExist:
                        errors.append({'row': rownum, 'error': 'Объект'})
                        citizenship = None

                location = sh.cell_value(rownum, 10).strip()
                if location is not None:
                    try:
                        location = CustomerLocation.objects.get(
                            location_name=location
                        )
                    except CustomerLocation.DoesNotExist:
                        errors.append({'row': rownum, 'error': 'Объект'})
                        location = None

                work_type = sh.cell_value(rownum, 11)
                if work_type == 'постоянная':
                    work_type = 'full'
                elif work_type == 'подработка':
                    work_type = 'part'
                elif work_type == 'вахта':
                    work_type = 'shift'
                else:
                    work_type = None

                try:
                    next_date = sh.cell_value(rownum, 12)
                    next_date = datetime.datetime(
                        *xlrd.xldate_as_tuple(next_date, book.datemode)
                    )
                except:
                    errors.append(
                        {'row': rownum, 'error': 'дата следующего контакта'})
                    next_date = None

                comment = sh.cell_value(rownum, 15)

                obj = Applicant(
                    init_date=date,
                    phone=phone,
                    type=type,
                    author=self.request.user,
                    status=status,
                    name=name,
                    source=source,
                    age=age,
                    have_docs=have_docs,
                    citizenship=citizenship,
                    metro=metro,
                    city=city,
                    location=location,
                    work_type=work_type,
                    next_date=next_date,
                    comment=comment,
                )
                obj.save()
        finally:
            os.remove(path)
        return errors

    def post(self, request, *args, **kwargs):
        context = self.get_context_data(**kwargs)
        if 'file' in request.FILES:
            errors = self.handle_uploaded_file(request.FILES['file'])
            context['success'] = True
            context['errors'] = errors
        return self.render_to_response(context)


class StatusAutocomplete(LoginRequiredMixin, autocomplete.Select2QuerySetView):
    def get_queryset(self):
        queryset = Status.objects.filter(active=True, final__isnull=True)
        if self.request.user.is_superuser:
            return queryset
        current_status = self.forwarded.get('status_hidden')
        initial_status = StatusInitial.objects.get().status
        statuses_to = []
        if not current_status:
            statuses_to.append(initial_status.pk)
            current_status = initial_status
        statuses_to.extend(
            list(
                AllowedStatusTransition.objects.filter(
                    status_from=current_status
                ).values_list('status_to', flat=True)
            )
        )

        source_pk = self.forwarded.get('source')
        if source_pk:
            source = ApplicantSource.objects.get(pk=source_pk)
            if source.name == 'Яндекс':
                statuses_to.append(
                    Status.objects.get(name='встреча в офисе').pk
                )

        queryset = queryset.filter(pk__in=statuses_to)

        if self.q:
            queryset = queryset.filter(name__icontains=self.q)

        return queryset


class SourceAutocomplete(LoginRequiredMixin, autocomplete.Select2QuerySetView):
    def get_queryset(self):
        queryset = ApplicantSource.objects.all()

        if self.q:
            queryset = queryset.filter(name__icontains=self.q)
        return queryset


class ManagerAutocomplete(LoginRequiredMixin, autocomplete.Select2QuerySetView):
    def get_queryset(self):
        user_groups = self.request.user.groups.values_list('name', flat=True)

        if 'Подборщики внешние' in user_groups:
            recruitment_groups = []
            GROUP_RX = re.compile('^Подборщики внешние \d+$')
            for group in user_groups:
                m = GROUP_RX.match(group)
                if m:
                    recruitment_groups.append(group)
        else:
            recruitment_groups = [
                'Подборщики',
                'Подборщики внешние',
                'Подборщики руководитель'
            ]

        queryset = User.objects.filter(
            groups__name__in=recruitment_groups
        ).distinct(
        ).order_by('username')

        if self.q:
            queryset = queryset.filter(name__icontains=self.q)
        return queryset


@staff_account_required
def unassigned_list(request):
    return render(
        request,
        'applicants/unassigned_applicants.html',
        {
            'applicants': _unassigned_applicants()
        }
    )


@staff_account_required
def unassigned_count(request):
    unassigned = _unassigned_applicants()
    count = unassigned.count()
    data = { 'count': count }
    data['time'] = 'не посчитано'
    if 0 < count < 10:
        oldest = max(unassigned, key=lambda applicant: applicant.idle_time())
        data['time'] = time_interval_format(oldest.idle_time())
    return JsonResponse(data)


@staff_account_required
def assign(request, pk):
    applicant = Applicant.objects.get(pk=pk)
    applicant.author = request.user
    applicant.save()
    return HttpResponse()


def _status_color(status):
    COLORS = {
        'отклик':                  '#011f4b',
        'приглашен на оформление': '#123059',
        'встреча в офисе':         '#244168',
        'отправлен на проверку СБ':'#365377',
        'отправлен на объект':     '#486486',
        'встреча на объекте':      '#5a7695',
        'выход':                   '#6b87a4',
        'резерв':                  '#6b87a4',
        'не согласен':             '#7d98b3',
        'не подходит':             '#8faac2',
        'отказ СБ':                '#a1bbd1',
        'перезвон':                '#b3cde0',
    }
    return COLORS.get(status.name, '#0F0')


def _same_enough(applicant1, applicant2):
    if applicant1.status != applicant2.status:
        return False
    if applicant1.phone != applicant2.phone:
        return False
    if applicant1.name != applicant2.name:
        return False
    if applicant1.author != applicant2.author:
        return False
    return True


@staff_account_required
def history(request, pk):
    applicant = Applicant.objects.get(pk=pk)

    history = []
    for item in applicant.filtered_history_list(_same_enough):
        history.append((item, _status_color(item.status)))

    return render(
        request,
        'applicants/statuses_history.html',
        {
            'applicants': history
        }
    )


@staff_account_required
def funnel(request):
    names = [
        'отклик',
        'приглашен на оформление',
        'встреча в офисе',
        'отправлен на проверку СБ',
        'отправлен на объект',
        'встреча на объекте',
        'выход',
    ]
    extra_names = [
        'резерв',
        'не согласен',
        'не подходит',
        'отказ СБ',
        'перезвон',
    ]
    status_chain = [(Status.objects.get(name=name), True) for name in names]
    status_chain.extend(
        [(Status.objects.get(name=name), False) for name in extra_names]
    )

    data = []
    for status, need_gantt in status_chain:
        data.append(
            {
                'name': status.name,
                'count': 0,
                'timedelta_count': 0,
                'timedelta': datetime.timedelta(),
                'need_gantt': need_gantt,
                'color': _status_color(status),
            }
        )

    applicants = active_applicants()
    source_pk, manager_pk, first_day, last_day = _base_filters(
        request, _first_day(strange_logic=True))
    request_params = {}
    if source_pk:
        applicants = applicants.filter(
            source__pk=source_pk
        )
        request_params['source'] = source_pk
    if manager_pk:
        applicants = applicants.filter(
            author__pk=manager_pk
        )
        request_params['manager'] = manager_pk
    if first_day:
        applicants = applicants.filter(
            init_date__gte=date_from_string(first_day)
        )
        request_params['first_day'] = first_day
    if last_day:
        applicants = applicants.filter(
            init_date__lte=date_from_string(last_day)
        )
        request_params['last_day'] = last_day

    data[0]['count'] = applicants.count()

    def _url(status):
        params = {}
        params.update(request_params)
        params['interval_type'] = 'init_date'
        if hasattr(status, 'final'):
            params['filter_status'] = status.pk
        else:
            params['filter_has_status'] = status.pk
        uri = request.build_absolute_uri(reverse('applicants:list') + '?' + urlencode(params))
        return uri

    for i in range(len(status_chain)):
        status, need_gantt = status_chain[i]
        data[i]['url'] = _url(status)

    for applicant in applicants:
        for i in range(len(status_chain))[1:]:
            status, need_gantt = status_chain[i]
            def _check(applicant):
                return applicant.status == status
            if hasattr(status, 'final'):
                if _check(applicant):
                    current = applicant
                else:
                    current = None
            else:
                current = applicant.find_first_in_history(_check)
            if current:
                data[i]['count'] += 1
                if not need_gantt:
                    continue
                prev_status, tmp = status_chain[i - 1]
                def _check_previous(applicant):
                    return applicant.status == prev_status
                previous = applicant.find_first_in_history(_check_previous)
                if previous:
                    if current.last_edited > previous.last_edited:
                        data[i - 1]['timedelta_count'] += 1
                        data[i - 1]['timedelta'] += (current.last_edited - previous.last_edited)

    def _interval_in_seconds(interval):
        return interval.days * 24 * 60 * 60 + interval.seconds

    previous_seconds = 0
    for item in data:
        if item['timedelta_count'] == 0:
            item['timedelta_count'] = 1
        avg_time = item['timedelta'] / item['timedelta_count']
        item['seconds'] = _interval_in_seconds(avg_time)
        if item['need_gantt']:
            item['begin'] = previous_seconds
            previous_seconds += item['seconds']
        item['timedelta'] = time_interval_format(avg_time)

    def _average_lifetime(status):
        lifetime = datetime.timedelta()
        filtered_applicants = applicants.filter(
            status=status
        )
        for applicant in filtered_applicants:
            lifetime += (
                applicant.last_edited -
                applicant.history_list()[0].last_edited
            )
        if filtered_applicants.exists():
            return _interval_in_seconds(
                lifetime / filtered_applicants.count()
            )
        return None

    statuses_with_lifetime = [
        'выход',
        'резерв',
        'не согласен',
        'не подходит',
        'отказ СБ',
    ]
    index = len(names) - 1
    for name in statuses_with_lifetime:
        status=Status.objects.get(name=name)
        lifetime = _average_lifetime(status)
        if lifetime is not None:
            data[index]['need_gantt'] = True
            data[index]['begin'] = 0
            data[index]['seconds'] = lifetime
        index += 1

    return render(
        request,
        'applicants/funnel.html',
        {
            'data': data,
            'filter_form': forms.FunnelFilterForm(
                initial=_initial_filter(
                    request,
                    _first_day(strange_logic=True)
                )
            )
        }
    )


# Todo: date_utils?
def _home_date_to_utc_time(date):
    dt = datetime.datetime.combine(
        date,
        datetime.time()
    )
    return pytz.timezone('Europe/Moscow').localize(dt).astimezone(pytz.timezone('UTC'))


def _utc_time_to_home_date(dt):
    return dt.astimezone(pytz.timezone('Europe/Moscow')).date()


@staff_account_required
def conveyor_report(request):
    source_pk, manager_pk, first_day, last_day = _base_filters(request)
    first_day = date_from_string(first_day)
    if last_day:
        last_day = date_from_string(last_day)
    else:
        last_day = timezone.now().date()

    begin_time = _home_date_to_utc_time(first_day)
    end_time = _home_date_to_utc_time(last_day + datetime.timedelta(days=1))

    initial_status = Status.objects.get(initial__isnull=False)

    names = [
        'приглашен на оформление',
        'встреча в офисе',
        'встреча на объекте',
        'отправлен на объект',
        'резерв',
        'отправлен на проверку СБ',
        'отказ СБ',
        'выход',
    ]

    statuses = [Status.objects.get(name=name) for name in names]
    days = [
        first_day + datetime.timedelta(days=d) for d in range(0, (last_day-first_day).days + 1)
    ]

    all_statuses = [initial_status] + statuses

    grid = { status: {day:[] for day in days} for status in all_statuses }

    nodes = ApplicantHistoryNode.objects.filter(
        timestamp__gte=begin_time,
        timestamp__lt=end_time
    ).select_related(
        'applicant'
    ).filter(
        applicant__active=True,
        applicant__status__in=statuses
    )

    # For initial status
    apps = active_applicants().filter(
        init_date__gte=first_day,
        init_date__lte=last_day
    ).distinct()

    if source_pk:
        source_pk = int(source_pk)
        nodes = nodes.filter(
            applicant__source__pk=source_pk
        )
        apps = apps.filter(
            source__pk=source_pk
        )
    if manager_pk:
        manager_pk = int(manager_pk)
        nodes = nodes.filter(
            applicant__author__pk=manager_pk
        )
        apps = apps.filter(
            author__pk=manager_pk
        )

    for node in nodes:
        if not node.previous or not _same_enough(node.previous.applicant, node.applicant):
            head = node.head()
            if head:
                row = grid[node.applicant.status]
                day = _utc_time_to_home_date(node.timestamp)
                cell = row[day]
                if head not in cell:
                    cell.append(head)

    initial_row = grid[initial_status]
    for applicant in apps:
        initial_row[applicant.init_date].append(applicant)

    def _applicants_url(status, day):
        params = {
            'status': status.pk,
            'day': string_from_date(day)
        }
        if source_pk:
            params['source'] = source_pk
        if manager_pk:
            params['manager'] = manager_pk
        return request.build_absolute_uri(
            reverse('applicants:conveyor_details') + '?' + urlencode(params)
        )

    data = []
    for status in all_statuses:
        row = []
        for day in days:
            row.append((len(grid[status][day]), _applicants_url(status, day)))
        if hasattr(status, 'final'):
            name = 'выходы (журнал)'
        else:
            name = status
        data.append((name, row, sum([value for value, url in row])))


    def _workers_url(day, report_type, citizenship=None):
        url = reverse(
            'the_redhuman_is:report_customer_summary_details',
            kwargs = {
                'location_pk': 0,
                'date': string_from_date(day),
                'shift': '-',
                'report_type': report_type
            }
        )
        params = {}
        if source_pk:
            params['source'] = source_pk
        if manager_pk:
            params['manager'] = manager_pk
        if citizenship:
            params['citizenship'] = citizenship

        return request.build_absolute_uri(
            url + '?' + urlencode(params)
        )

    # Real turnouts
    row_all = []
    row_applicants = []
    row_applicants_russian = []
    row_applicants_not_russian = []
    for day in days:
        count_all = 0
        count_applicants = 0
        count_applicants_russian = 0
        count_applicants_not_russian = 0
        turnouts = WorkerTurnout.objects.filter(
            timesheet__sheet_date=day
        )
        for turnout in turnouts:
            if turnout.is_first():
                count_all += 1
                if hasattr(turnout.worker, 'applicant_link'):
                    applicant = turnout.worker.applicant_link.applicant
                    if ((not source_pk or source_pk == applicant.source.pk) and
                        (not manager_pk or manager_pk == applicant.author.pk)):
                        count_applicants += 1
                        if turnout.worker.citizenship.name=='РФ':
                            count_applicants_russian += 1
                        else:
                            count_applicants_not_russian += 1

        row_all.append((count_all, _workers_url(day, 'new_turnouts')))
        row_applicants.append((count_applicants, _workers_url(day, 'new_applicants')))
        row_applicants_russian.append((count_applicants_russian, _workers_url(day, 'new_applicants', 'russian')))
        row_applicants_not_russian.append((count_applicants_not_russian, _workers_url(day, 'new_applicants', 'not_russian')))
    data.append(
        (
            'новые выходы',
            row_all,
            sum([value for value, url in row_all])
        )
    )
    data.append(
        (
            'новые выходы от подбора всего',
            row_applicants,
            sum([value for value, url in row_applicants])
        )
    )
    data.append(
        (
            'новые выходы от подбора РФ',
            row_applicants_russian,
            sum([value for value, url in row_applicants_russian])
        )
    )
    data.append(
        (
            'новые выходы от подбора не РФ',
            row_applicants_not_russian,
            sum([value for value, url in row_applicants_not_russian])
        )
    )

    return render(
        request,
        'applicants/conveyor_report.html',
        {
            'filter_form': forms.ConveyorFilterForm(
                initial=_initial_filter(request)
            ),
            'days': days,
            'data': data
        }
    )


@staff_account_required
def conveyor_details(request):
    # required
    status = Status.objects.get(pk=request.GET['status'])
    # required
    day = date_from_string(request.GET['day'])

    source_pk = request.GET.get('source')
    manager_pk = request.GET.get('manager')

    def _url(applicant):
        return request.build_absolute_uri(
            reverse(
                'applicants:history',
                kwargs={
                    'pk': applicant.pk
                }
            )
        )

    def _initial_list():
        apps = active_applicants().filter(
            init_date=day
        ).distinct()
        if source_pk:
            apps = apps.filter(
                source__pk=source_pk
            )
        if manager_pk:
            apps = apps.filter(
                author__pk=manager_pk
            )
        return [(app, _url(app)) for app in apps.order_by('-author')]

    def _general_list():
        begin_time = _home_date_to_utc_time(day)
        end_time = _home_date_to_utc_time(day + datetime.timedelta(days=1))

        nodes = ApplicantHistoryNode.objects.filter(
            timestamp__gte=begin_time,
            timestamp__lt=end_time,
        ).select_related(
            'applicant'
        ).filter(
            applicant__active=True,
            applicant__status=status
        )
        if source_pk:
            nodes = nodes.filter(
                applicant__source__pk=source_pk
            )
        if manager_pk:
            nodes = nodes.filter(
                applicant__author__pk=manager_pk
            )

        heads = []
        for node in nodes:
            if not node.previous or not _same_enough(node.previous.applicant, node.applicant):
                head = node.head()
                if head and head not in heads:
                    heads.append(head)

        return [(head.applicant, _url(head.applicant)) for head in heads]

    if hasattr(status, 'initial'):
        apps = _initial_list()
    else:
        apps = _general_list()

    return render(
        request,
        'applicants/short_list.html',
        {
            'applicants': apps
        }
    )
