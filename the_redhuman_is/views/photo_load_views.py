import datetime
import re

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType

from django.db import transaction

from django.db.models import (
    Count,
    IntegerField,
    OuterRef,
    Subquery,
)

from django.db.models.functions import Coalesce

from django.http import (
    Http404,
    HttpResponseRedirect,
    JsonResponse,
)

from django.shortcuts import render
from django.urls import (
    reverse,
    reverse_lazy
)
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic import (
    DetailView,
    FormView,
    ListView,
    RedirectView,
)

from the_redhuman_is.forms import (
    PhotoLoadSessionCommentForm,
    PhotoLoadSessionForm,
    TimeSheetSelectForm,
    TimeSheetWOutImagesForm,
    WorkerContractForm,
    WorkerFormWOutImages,
    WorkerPassportForm,
    WorkerPatentWithCitizenshipForm,
    WorkerRegistrationWithCitizenshipForm,
    WorkerTurnoutFormSet,
    WorkerWithContractSearchFormSet,
    all_worker_search_form,
)

from the_redhuman_is.models import (
    CustomerFine,
    CustomerFineDeduction,
    Photo,
    PhotoLoadSession,
    PhotoSessionCitizenship,
    PhotoSessionComments,
    PhotoSessionRejectedPhotos,
    TimeSheet,
    TurnoutBonus,
    TurnoutDeduction,
    TurnoutService,
    Worker,
    WorkerTurnout,
    WorkerZone,
)
from the_redhuman_is.models.worker import (
    MobileAppWorker,
    WorkerRating,
)

from the_redhuman_is.services.delivery_worker_zones import (
    NoWorkerZoneData,
    TooManyZones,
    get_mobile_app_zone,
)

from the_redhuman_is.views.utils import (
    _get_value,
    exception_to_500,
    get_customer_account,
)

from the_redhuman_is import models

from the_redhuman_is._1_orders_views import _update_turnouts

from the_redhuman_is.tasks import (
    send_push_notification_to_user,
    send_tg_message,
    send_tg_message_to_clerks,
    send_tg_message_to_dispatchers,
)

from telegram_bot.utils import send_message


class AddComment(LoginRequiredMixin, FormView):
    form_class = PhotoLoadSessionCommentForm

    def form_valid(self, form):
        session = PhotoLoadSession.objects.get(pk=self.kwargs['pk'])
        session.status = 'comment'
        session.save()
        comment = PhotoSessionComments.objects.create(
            comment=form.cleaned_data['comment'],
            sender=self.request.user,
            session=session
        )

        # send message to telegram
        try:
            t_chat_id = session.sender.telegramuser.chat_id
        except:
            pass
        else:
            session_url = reverse_lazy(
                'the_redhuman_is:photo_load_session_sort',
                kwargs={'pk': session.id, 'name': session.content_type}
            )
            message = '{} добавил комментарий к '.format(self.request.user.get_full_name())
            message += ' <a href="https://{}{}">cессии №{}</a>. '.format(
                self.request.META['HTTP_HOST'],
                session_url,
                session.id
            )
            message += "Комментарий: \n<i>{}</i>".format(comment.comment)
            send_tg_message(t_chat_id, message)

        return JsonResponse(dict(
            date=comment.date.strftime("%d.%m.%y %H:%M"),
            comment=comment.comment,
            user=self.request.user.username
        ))

    def form_invalid(self, form):
        return JsonResponse({'status': 0}, status=500)


class CustomLoginRequired(LoginRequiredMixin):
    login_url = reverse_lazy('login')
    redirect_field_name = 'next'

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()

        account = get_customer_account(request)
        if account:
            return self.handle_no_permission()

        return super(CustomLoginRequired, self).dispatch(request, *args,
                                                         **kwargs)


class PhotoLoadListView(CustomLoginRequired, ListView):
    template_name = 'the_redhuman_is/photo_load_list.html'
    model = PhotoLoadSession
    ordering = '-id'
    user_group = None

    def dispatch(self, request, *args, **kwargs):
        user_groups = self.request.user.groups.values_list('name', flat=True)
        if 'Бригадиры' in user_groups:
            self.user_group = 'brigad'
        elif 'Операционисты' in user_groups:
            self.user_group = 'oper'
        return super(PhotoLoadListView, self).dispatch(request, args, **kwargs)

    def get_queryset(self):
        user_groups = self.request.user.groups.values_list('name', flat=True)
        queryset = super(PhotoLoadListView, self).get_queryset()
        q = self.request.GET.get('q', 'last_30_days')
        if 'Бригадиры' in user_groups or 'Менеджеры' in user_groups:
            queryset = queryset.filter(sender=self.request.user)
        if q == 'new':
            queryset = queryset.filter(status='new')
        elif q == 'last_30_days':
            deadline = timezone.now().date() - datetime.timedelta(days=30)
            queryset = queryset.filter(date_create__gte=deadline)
        elif q == 'work':
            queryset = queryset.filter(status='work')
        elif q == 'comment':
            handler = User.objects.filter(
                groups__name='Операционист'
            ).values('id')
            last_comments_by_sender = PhotoSessionComments.objects.all()
            last_comments_by_sender = last_comments_by_sender.distinct(
                'sender'
            ).order_by('sender')
            last_comments_by_sender = last_comments_by_sender.values('id')
            queryset = queryset.filter(
                comments__id__in=last_comments_by_sender,
                comments__sender__in=handler
            )

        queryset = queryset.annotate(
            photo_count=Coalesce(
                Subquery(
                    Photo.objects.filter(
                        object_id=OuterRef('pk'),
                        content_type=ContentType.objects.get_for_model(PhotoLoadSession)
                    ).values(
                        'object_id'
                    ).annotate(
                        count=Count('pk')
                    ).values(
                        'count'
                    ),
                    output_field=IntegerField()
                ),
                0
            ),
            last_comment=Subquery(
                PhotoSessionComments.objects.filter(
                    session=OuterRef('pk')
                ).order_by(
                    '-date'
                ).values(
                    'comment'
                )[:1]
            )
        ).select_related(
            'sender',
            'handler',
            'photosessioncitizenship',
        ).distinct()
        return queryset

    def get_context_data(self, **kwargs):
        context = super(PhotoLoadListView, self).get_context_data(**kwargs)
        title = 'Сортировка фото'
        context['head_title'] = title
        context['title'] = title
        context['user_groups'] = self.request.user.groups.values_list('name', flat=True)
        return context


@require_POST
def delete_photo_load_session(request, pk):
    try:
        with transaction.atomic():
            pls = PhotoLoadSession.objects.filter(
                content_type='worker',
            ).get(pk=pk)
            pls.comments.all().delete()
            PhotoSessionCitizenship.objects.filter(session=pls).delete()
            PhotoSessionRejectedPhotos.objects.filter(session=pls).delete()
            pls.delete()
        return JsonResponse({})
    except PhotoLoadSession.DoesNotExist:
        return JsonResponse({}, status=404)


class PhotoLoadAddView(CustomLoginRequired, FormView):
    template_name = 'the_redhuman_is/photo_load_add.html'
    form_class = PhotoLoadSessionForm
    success_url = reverse_lazy('the_redhuman_is:photo_load_session_list')
    title_dict = {'worker': 'рабочего',
                  'contract': 'договора',
                  'timesheet': 'табеля'}

    def get(self, request, *args, **kwargs):
        sessions = PhotoLoadSession.objects.filter(
            content_type=self.kwargs['name'],
            sender=self.request.user
        )
        sessions = sessions.exclude(status='complete')
        if sessions:
            session = sessions.last()
            return HttpResponseRedirect(
                reverse_lazy(
                    'the_redhuman_is:photo_load_session_update',
                    kwargs={'pk': session.id, 'name': session.content_type}
                )
            )
        else:
            return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(PhotoLoadAddView, self).get_context_data(**kwargs)
        context['head_title'] = 'Добавление новых фотографий'
        context['title'] = 'Добавить файлы {}'.format(
            self.title_dict[self.kwargs['name']])
        return context

    def post(self, request, *args, **kwargs):
        form_class = self.get_form_class()
        form = self.get_form(form_class)
        if form.is_valid():
            with transaction.atomic():
                # create session
                session = PhotoLoadSession.objects.create(
                    content_type=self.kwargs['name'],
                    status='new',
                    sender=self.request.user
                )
                # add comment
                if form.cleaned_data['comment']:
                    PhotoSessionComments.objects.create(
                        comment=form.cleaned_data['comment'],
                        sender=self.request.user,
                        session=session
                    )
                for key in request.FILES:
                    models.add_photo(session, request.FILES[key])

            # send telegram message
            session_url = reverse_lazy(
                'the_redhuman_is:photo_load_session_sort',
                kwargs={'pk': session.id, 'name': session.content_type}
            )
            message = '{} добавил {} '.format(
                self.request.user.get_full_name(),
                models.get_photos(session).count(),
            )
            message += ' <a href="https://{}{}">{} №{}</a>'.format(
                self.request.META['HTTP_HOST'],
                session_url,
                session.get_content_type.lower(),
                session.id
            )
            send_tg_message_to_clerks(message)
            return self.form_valid(form)
        else:
            return self.form_invalid(form)

    def form_valid(self, form):
        if self.request.is_ajax():
            return JsonResponse({'url': self.get_success_url()})
        else:
            return HttpResponseRedirect(self.get_success_url())


class PhotoLoadUpdateView(CustomLoginRequired, FormView):
    template_name = 'the_redhuman_is/photo_load_update.html'
    form_class = PhotoLoadSessionForm
    success_url = reverse_lazy('the_redhuman_is:photo_load_session_list')
    title_dict = {
        'contract': 'договора',
        'worker': 'рабочего',
        'timesheet': 'табеля'
    }

    def get_context_data(self, **kwargs):
        session = PhotoLoadSession.objects.get(pk=self.kwargs['pk'])
        context = super(PhotoLoadUpdateView, self).get_context_data(**kwargs)
        context['head_title'] = 'Фотографии сессии №{}'.format(
            self.kwargs['pk'])
        context['title'] = 'Фотографии сессии №{}'.format(self.kwargs['pk'])
        context['title2'] = 'Добавить eще файлы для {}'.format(
            self.title_dict[self.kwargs['name']])
        context['pictures'] = models.get_photos(session)
        context['object'] = session
        return context

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        form_class = self.get_form_class()
        form = self.get_form(form_class)
        if form.is_valid():
            # get session
            try:
                session = PhotoLoadSession.objects.get(
                    pk=self.kwargs['pk']
                )
            except PhotoLoadSession.DoesNotExist:
                return Http404

            # add new comment
            if form.cleaned_data['comment']:
                PhotoSessionComments.objects.create(
                    comment=form.cleaned_data['comment'],
                    sender=self.request.user,
                    session=session
                )
            # add pictures
            for key in request.FILES:
                models.add_photo(session, request.FILES[key])
            # send telegram message
            session_url = reverse_lazy(
                'the_redhuman_is:photo_load_session_sort',
                kwargs={'pk': session.id, 'name': session.content_type}
            )
            message = '{} обновил '.format(request.user.get_full_name())
            message += ' <a href="https://{}{}">сессия №{}</a>'.format(
                self.request.META['HTTP_HOST'],
                session_url,
                session.id
            )
            send_tg_message_to_clerks(message)
            return self.form_valid(form)
        else:
            return self.form_invalid(form)

    def form_valid(self, form):
        if self.request.is_ajax():
            return JsonResponse({'url': self.get_success_url()})
        else:
            return HttpResponseRedirect(self.get_success_url())


class PhotoLoadSortContractView(CustomLoginRequired, DetailView):
    template_name = 'the_redhuman_is/photo_load_sort_contract.html'
    model = PhotoLoadSession
    context_object_name = 'session'
    success_url = reverse_lazy('the_redhuman_is:photo_load_session_list')

    def get_context_data(self, **kwargs):
        self.object = self.get_object()
        context = super().get_context_data(**kwargs)
        title = 'Обработка фотографий сессии №{}'.format(self.object.pk)
        context['head_title'] = title
        context['title'] = title
        context['photo2session'] = models.get_photos(self.object)
        context['worker_search'] = all_worker_search_form()
        context['comment_form'] = PhotoLoadSessionCommentForm()
        if self.request.method == 'GET':
            context['contract_form'] = WorkerContractForm(prefix='contract')
        return context

    def get_success_url(self):
        return self.request.get_full_path()

    def form_invalid(self, forms):
        error_message = 'Исправьте ошибки на форме {}'
        if not forms['contract_form'].is_valid():
            messages.error(self.request, error_message.format('Договор'),
                           extra_tags='alert-danger')
        return self.render_to_response(self.get_context_data(**forms))

    @transaction.atomic()
    def form_valid(self, forms):
        session = self.get_object()
        if self.request.POST.get('session_comment', None):
            session.status = 'comment'
        elif self.request.POST.get('session_status', None):
            session.status = 'complete'
        else:
            session.status = 'work'
        session.handler = self.request.user
        session.save()

        worker = Worker.objects.get(pk=self.request.POST.get('worker'))
        actual_contract = worker.get_actual_contract()
        if actual_contract is None or forms['contract_form'].has_changed():
            contract = forms['contract_form'].save(commit=False)
            contract.c_worker = worker
            contract.save()
        else:
            contract = actual_contract

        # link photo
        photo_ids = self.request.POST.getlist('images')

        # remove old images
        if photo_ids:
            contract.image = None
            contract.image2 = None
            contract.image3 = None
            contract.save()
            models.get_photos(contract).delete()

        for pk in photo_ids:
            photo = Photo.objects.get(pk=pk)
            photo.change_target(contract)

        messages.success(
            self.request,
            'Контракт {} успешно сохранен'.format(contract),
            extra_tags='alert-success'
        )
        return HttpResponseRedirect(self.get_success_url())

    def post(self, request, *args, **kwargs):
        request = self.request.POST.copy()
        worker_id = request.get('worker', '')
        if worker_id.isdigit():
            worker = Worker.objects.get(pk=worker_id)
            phone = request.get('worker-tel_number')
            if phone:
                worker.tel_number = phone
                worker.save()
            contract = worker.get_actual_contract()
        else:
            contract = None
        forms = {
            'contract_form': WorkerContractForm(
                request,
                initial=contract.__dict__ if contract else None,
                prefix='contract'
            ),
        }

        if forms['contract_form'].is_valid():
            return self.form_valid(forms)
        else:
            return self.form_invalid(forms)


class PhotoLoadSortTimesheetAfterView(CustomLoginRequired, DetailView):
    template_name = 'the_redhuman_is/photo_load_sort_timesheet_after.html'
    model = PhotoLoadSession
    context_object_name = 'session'
    success_url = reverse_lazy('the_redhuman_is:photo_load_session_list')

    def get_context_data(self, **kwargs):
        self.object = self.get_object()
        context = super().get_context_data(**kwargs)
        title = 'Обработка фотографий сессии №{}'.format(self.object.pk)
        context['head_title'] = title
        context['title'] = title
        context['photo2session'] = models.get_photos(self.object)
        context['worker_search'] = all_worker_search_form()
        context['comment_form'] = PhotoLoadSessionCommentForm()

        timesheet = TimeSheet.objects.get(pk=self.kwargs['timesheet_pk'])
        turnouts = WorkerTurnout.objects.filter(timesheet=timesheet)
        turnouts = turnouts.order_by('id')
        if self.request.method == 'GET':
            formset = WorkerTurnoutFormSet(queryset=turnouts)
            context['after'] = formset

        cfines_set = CustomerFine.objects.filter(turnout__in=turnouts)
        cfines_set = cfines_set.order_by('id')
        cfines = {}
        for cfine in cfines_set:
            if cfine.turnout_id not in cfines:
                cfines[cfine.turnout_id] = []
            if cfine.operation.amount is None:
                cfine.operation.amount = ''
            cfines[cfine.turnout_id].append(cfine)

        cf_deductions = CustomerFineDeduction.objects.filter(
            fine__in=cfines_set.values_list('operation_id', flat=True)
        )
        cf_deductions = cf_deductions.order_by('id')
        cf_deductions = cf_deductions.values_list(
            'deduction_id', flat=True
        )
        fines_set = TurnoutDeduction.objects.filter(turnout__in=turnouts)
        fines_set = fines_set.exclude(operation__in=cf_deductions)
        fines = {}
        for fine in fines_set.order_by('id'):
            if fine.turnout_id not in fines:
                fines[fine.turnout_id] = []
            if fine.operation.amount is None:
                fine.operation.amount = ''
            fines[fine.turnout_id].append(fine)

        bonuses_set = TurnoutBonus.objects.filter(turnout__in=turnouts)
        bonuses = {}
        for bonus in bonuses_set.order_by('id'):
            if bonus.turnout_id not in bonuses:
                bonuses[bonus.turnout_id] = []
            if bonus.operation.amount is None:
                bonus.operation.amount = ''
            bonuses[bonus.turnout_id].append(bonus)

        for i in range(len(turnouts)):
            turnout_service = TurnoutService.objects.all()
            turnout_service = turnout_service.filter(turnout=turnouts[i])
            turnout_service = turnout_service.first()
            if turnout_service:
                customer_service = turnout_service.customer_service
                formset[i].fields["service"].initial = customer_service
            if turnouts[i].id not in fines:
                fines[turnouts[i].id] = []
                fines[turnouts[i].id].append({'val': '', 'comment': ''})
            if turnouts[i].id not in bonuses:
                bonuses[turnouts[i].id] = []
                bonuses[turnouts[i].id].append({'val': '', 'comment': ''})
            if turnouts[i].id not in cfines:
                cfines[turnouts[i].id] = []
                cfines[turnouts[i].id].append({'val': '', 'comment': ''})

        fines[0] = []
        fines[0].append({'val': '', 'comment': ''})
        bonuses[0] = []
        bonuses[0].append({'val': '', 'comment': ''})
        cfines[0] = []
        cfines[0].append({'val': '', 'comment': ''})

        context['timesheet'] = timesheet
        context['fines'] = fines
        context['bonuses'] = bonuses
        context['cfines'] = cfines
        return context

    def get_success_url(self):
        return self.request.get_full_path()

    def form_invalid(self, forms):
        error_message = 'Исправьте ошибки на форме'
        messages.error(self.request, error_message, extra_tags='alert-danger')
        return self.render_to_response(self.get_context_data(**forms))

    @transaction.atomic()
    def form_valid(self, forms):
        session = self.get_object()
        if self.request.POST.get('session_comment', None):
            session.status = 'comment'
        elif self.request.POST.get('session_status', None):
            session.status = 'complete'
        else:
            session.status = 'work'
        session.handler = self.request.user
        session.save()

        timesheet = TimeSheet.objects.get(pk=self.kwargs['timesheet_pk'])

        delete_turnouts = self.request.POST.getlist('delete')

        filtered_forms = []
        for i, form in enumerate(forms['after']):
            customer_service = form.cleaned_data.get('service')
            if not customer_service:
                continue
            if not form.is_valid():
                continue
            if form.cleaned_data['id'] and str(form.cleaned_data['id'].id) in delete_turnouts:
                continue

            filtered_forms.append(form)

        _update_turnouts(self.request, timesheet, filtered_forms)

        operations_id = list()
        for turnout_pk in delete_turnouts:
            turnout = WorkerTurnout.objects.get(pk=turnout_pk)

            if hasattr(turnout, 'turnoutoperationtopay'):
                turnout.turnoutoperationtopay.operation.delete()

            if hasattr(turnout, 'turnoutcustomeroperation'):
                turnout.turnoutcustomeroperation.operation.delete()

            turnout.delete()

        # link photo
        photo_ids = self.request.POST.getlist('images')
        for pk in photo_ids:
            photo = Photo.objects.get(pk=pk)
            photo.change_target(timesheet)

        messages.success(
            self.request,
            'Табель {} успешно сохранен'.format(timesheet),
            extra_tags='alert-success'
        )
        return HttpResponseRedirect(self.get_success_url())

    def post(self, request, *args, **kwargs):
        request = self.request.POST.copy()
        timesheet = TimeSheet.objects.get(pk=self.kwargs['timesheet_pk'])
        turnouts = WorkerTurnout.objects.filter(timesheet=timesheet)
        forms = {
            'after': WorkerTurnoutFormSet(request, queryset=turnouts)
        }
        if forms['after'].is_valid():
            return self.form_valid(forms)
        else:
            return self.form_invalid(forms)


class PhotoLoadSortTimesheetBeforeView(CustomLoginRequired, DetailView):
    template_name = 'the_redhuman_is/photo_load_sort_timesheet.html'
    model = PhotoLoadSession
    context_object_name = 'session'
    success_url = reverse_lazy('the_redhuman_is:photo_load_session_list')

    def get_context_data(self, **kwargs):
        self.object = self.get_object()
        context = super().get_context_data(**kwargs)
        title = 'Обработка фотографий сессии №{}'.format(self.object.pk)
        context['head_title'] = title
        context['title'] = title
        context['photo2session'] = models.get_photos(self.object)
        context['worker_search'] = WorkerWithContractSearchFormSet
        context['comment_form'] = PhotoLoadSessionCommentForm()
        if self.request.method == 'GET':
            context['timesheet_form'] = TimeSheetWOutImagesForm(
                initial={'turnouts_number': 1},
                prefix='before'
            )
            context['timesheet_select_form'] = TimeSheetSelectForm(
                prefix='after'
            )
        return context

    def get_success_url(self):
        return self.request.get_full_path()

    def form_invalid(self, forms):
        error_message = 'Исправьте ошибки на форме'
        messages.error(self.request, error_message, extra_tags='alert-danger')
        return self.render_to_response(self.get_context_data(**forms))

    @transaction.atomic()
    def form_valid(self, forms):
        session = self.get_object()
        if self.request.POST.get('session_comment', None):
            session.status = 'comment'
        elif self.request.POST.get('session_status', None):
            session.status = 'complete'
        else:
            session.status = 'work'
        session.handler = self.request.user
        session.save()

        if forms['before'].has_changed():
            workers_count = 0
            for item in forms['workers'].cleaned_data:
                if item:
                    workers_count += 1

            timesheet = forms['before'].save(commit=False)
            timesheet.turnouts_number = workers_count
            timesheet.is_executed = False
            timesheet.save()
            forms['before'].save_m2m()

            # add workers
            for worker_form in forms['workers'].cleaned_data:
                if worker_form:
                    WorkerTurnout.objects.create(
                        timesheet=timesheet,
                        worker=worker_form['worker'],
                        contract=worker_form['worker'].get_actual_contract()
                    ).save()

        # link photo
        photo_ids = self.request.POST.getlist('images')
        for pk in photo_ids:
            photo = Photo.objects.get(pk=pk)
            photo.change_target(timesheet)

        messages.success(self.request,
                         'Табель {} успешно сохранен'.format(timesheet),
                         extra_tags='alert-success')
        return HttpResponseRedirect(self.get_success_url())

    def post(self, request, *args, **kwargs):
        request = self.request.POST.copy()
        forms = {
            'before': TimeSheetWOutImagesForm(request, prefix='before'),
            'after': TimeSheetSelectForm(request, prefix='after'),
            'workers': WorkerWithContractSearchFormSet(request),
        }
        if self.request.POST.get('action') == 'before':
            if forms['before'].is_valid():
                return self.form_valid(forms)
            else:
                return self.form_invalid(forms)
        elif self.request.POST.get('action') == 'after':
            if forms['after'].is_valid():
                timesheet_pk = forms['after'].cleaned_data['timesheet'].pk
                url = reverse_lazy(
                    'the_redhuman_is:photo_load_session_sort',
                    kwargs={
                        'pk': kwargs['pk'],
                        'name': 'timesheet',
                        'timesheet_pk': timesheet_pk
                    }
                )
                return HttpResponseRedirect(url)
        return self.form_invalid(forms)


_PASSPORT_RX = re.compile('.*passport.*')
_MIGRATION_CARD_RX = re.compile('.*migration.*')


class PhotoLoadSortWorkerView(CustomLoginRequired, DetailView):
    template_name = 'the_redhuman_is/photo_load_sort_worker.html'
    model = PhotoLoadSession
    context_object_name = 'session'
    success_url = reverse_lazy('the_redhuman_is:photo_load_session_list')

    def get_context_data(self, **kwargs):
        self.object = self.get_object()
        context = super().get_context_data(**kwargs)
        title = 'Обработка фотографий сессии №{}'.format(self.object.pk)
        context['head_title'] = title
        context['title'] = title
        context['photo2session'] = models.get_photos(self.object)
        context['worker_search'] = all_worker_search_form()
        context['comment_form'] = PhotoLoadSessionCommentForm()
        if self.request.method == 'GET':
            worker_form_initial = {}

            user_phone = models.UserPhone.objects.filter(user=self.object.sender)
            if user_phone.exists():
                user_phone = user_phone.get()
                worker_form_initial['tel_number'] = user_phone.phone

            citizenship = models.PhotoSessionCitizenship.objects.filter(session=self.object)
            if citizenship.exists():
                citizenship = citizenship.get()
                worker_form_initial['citizenship'] = citizenship.citizenship

            context['worker_form'] = WorkerFormWOutImages(
                prefix='worker',
                initial=worker_form_initial
            )
            context['passport_form'] = WorkerPassportForm(prefix='pass')
            context['reg_form'] = WorkerRegistrationWithCitizenshipForm(
                prefix='reg'
            )
            context['patent_form'] = WorkerPatentWithCitizenshipForm(
                prefix='pat'
            )
        return context

    def get_success_url(self):
        return self.request.get_full_path()

    def form_invalid(self, forms):
        error_message = 'Исправьте ошибки на форме {}'
        if not forms['worker_form'].is_valid():
            messages.error(self.request, error_message.format('Рабочий'),
                           extra_tags='alert-danger')
        if not forms['passport_form'].is_valid():
            messages.error(self.request, error_message.format('Паспорт'),
                           extra_tags='alert-danger')
        if not forms['reg_form'].is_valid():
            messages.error(self.request, error_message.format('Регистрация'),
                           extra_tags='alert-danger')
        if not forms['patent_form'].is_valid():
            messages.error(self.request, error_message.format('Патент'),
                           extra_tags='alert-danger')
        return self.render_to_response(self.get_context_data(**forms))

    @transaction.atomic()
    def form_valid(self, forms):
        session = self.get_object()
        if self.request.POST.get('session_comment', None):
            session.status = 'comment'
        elif self.request.POST.get('session_status', None):
            session.status = 'complete'
        else:
            session.status = 'work'
        session.handler = self.request.user
        session.save()

        if forms['worker_form'].instance.pk:
            new_worker = False
        else:
            new_worker = True

        worker = forms['worker_form'].save()

        if new_worker:
            models.create_worker_operating_account(worker)
        if forms['passport_form'].has_changed():
            pass_form = forms['passport_form'].save(commit=False)
            pass_form.workers_id = worker
            pass_form.save()
        if forms['reg_form'].has_changed():
            reg_form = forms['reg_form'].save(commit=False)
            reg_form.workers_id = worker
            reg_form.save()
        if forms['patent_form'].has_changed():
            pat_form = forms['patent_form'].save(commit=False)
            pat_form.workers_id = worker
            pat_form.save()

        # link photo
        photo_ids = self.request.POST.getlist('images')
        if photo_ids:
            # delete old photos
            models.get_photos(worker).delete()

            for pk in photo_ids:
                photo = Photo.objects.get(pk=pk)

                if _PASSPORT_RX.match(photo.image.path):
                    passport = worker.actual_passport
                    photo.change_target(passport)
                elif _MIGRATION_CARD_RX.match(photo.image.path):
                    migration_card, _ = models.WorkerMigrationCard.objects.get_or_create(
                        worker=worker
                    )
                    photo.change_target(migration_card)
                else:
                    photo.change_target(worker)

        # if photos are from mobile app
        user_phone = models.UserPhone.objects.filter(user=session.sender)
        if user_phone.exists():
            user_phone = user_phone.get()

            # just in case
            worker.tel_number = user_phone.phone
            worker.save()

            models.WorkerUser.objects.create(
                worker=worker,
                user=session.sender
            )

            user_phone.delete()

            try:
                zone_group_id = get_mobile_app_zone(worker)
            except (TooManyZones, NoWorkerZoneData):
                pass
            else:
                WorkerZone.objects.get_or_create(
                    worker=worker,
                    defaults={
                        'zone_id': zone_group_id
                    }
                )

            MobileAppWorker.objects.get_or_create(worker_id=worker.pk)
            WorkerRating.objects.get_or_create(worker=worker)

            send_push_notification_to_user(
                'К работе готов!',
                'Документы проверены, скоро вам начнут поступать заявки',
                'ready_to_work',
                session.sender
            )

            url = self.request.build_absolute_uri(
                reverse('the_redhuman_is:worker_detail', kwargs={'pk': worker.pk})
            )
            message = f'Новый рабочий <a href="{url}">{worker}</a>, тел. {worker.tel_number}'
            send_tg_message_to_dispatchers(message)
            send_tg_message_to_clerks(message)

        messages.success(
            self.request,
            'Рабочий {} успешно сохранен'.format(worker),
            extra_tags='alert-success'
        )

        return HttpResponseRedirect(self.get_success_url())

    def post(self, request, *args, **kwargs):
        updated_request = self.request.POST.copy()
        updated_request.update({
            'reg-citizenship': updated_request.get('worker-citizenship', None),
            'pat-citizenship': updated_request.get('worker-citizenship', None),
        })
        worker_id = updated_request.get('worker_id', None)
        if worker_id.isdigit():
            worker = Worker.objects.get(pk=worker_id)
            passport = worker.actual_passport
            reg = worker.actual_registration
            patent = worker.actual_patent
        else:
            worker = None
            passport = None
            reg = None
            patent = None
        forms = {
            'worker_form': WorkerFormWOutImages(updated_request,
                                                instance=worker,
                                                prefix='worker'),
            'passport_form': WorkerPassportForm(
                updated_request,
                initial=passport.__dict__ if passport else None,
                prefix='pass'
            ),
            'reg_form': WorkerRegistrationWithCitizenshipForm(
                updated_request,
                initial=reg.__dict__ if reg else None,
                prefix='reg'
            ),
            'patent_form': WorkerPatentWithCitizenshipForm(
                updated_request,
                initial=patent.__dict__ if patent else None,
                prefix='pat'
            )
        }

        if forms['worker_form'].is_valid() and \
                forms['passport_form'].is_valid() and \
                forms['reg_form'].is_valid() and \
                forms['patent_form'].is_valid():
            return self.form_valid(forms)
        else:
            return self.form_invalid(forms)


class PhotoLoadCloseView(LoginRequiredMixin, RedirectView):
    url = reverse_lazy('the_redhuman_is:photo_load_session_list')

    def get(self, request, *args, **kwargs):
        obj = PhotoLoadSession.objects.get(pk=kwargs['pk'])
        obj.status = 'complete'
        obj.save()
        return HttpResponseRedirect(self.url)


def worker_turnout_output(request):
    worker_pk = request.GET['worker']
    service_pk = request.GET['service']
    timesheet_pk = request.GET['timesheet']

    turnout = models.WorkerTurnout.objects.filter(
        timesheet__pk=timesheet_pk,
        worker__pk=worker_pk
    )
    if turnout.exists():
        turnout = turnout.get()
    else:
        turnout = None

    items = []
    if service_pk:
        customer_service = models.CustomerService.objects.get(pk=service_pk)
        box_types = models.BoxType.objects.filter(customer=customer_service.customer)
        for box_type in box_types:
            amount = 0
            output = models.TurnoutOutput.objects.filter(
                turnout=turnout,
                box_type=box_type
            )
            if output.exists():
                amount = output.get().amount
            items.append(
                {
                    'box_type': box_type,
                    'turnout': turnout,
                    'amount': amount
                }
            )

    return render(
        request,
        'the_redhuman_is/photo_load/worker_turnout_output.html',
        {
            'worker_pk': worker_pk,
            'timesheet_pk': timesheet_pk,
            'index': request.GET['index'],
            'items': items,
        }
    )


@exception_to_500
def bad_photo_alert(request):
    photo = models.Photo.objects.get(pk=_get_value(request, 'id'))
    session = PhotoLoadSession.objects.get(pk=photo.object_id)

    # if photos are from mobile app
    if models.UserPhone.objects.filter(user=session.sender).exists():
        rejected_photos, created = models.PhotoSessionRejectedPhotos.objects.get_or_create(
            session=session
        )
        photo.change_target(rejected_photos)

        send_push_notification_to_user(
            'Фото отклонено',
            'Документ необходимо сфотографировать еще раз',
            'document_rejected',
            session.sender
        )

        return JsonResponse(
            {'message': 'Фото отклонено, в приложение отправлено уведомление'}
        )

    else:
        user_chat_id = session.sender.telegramuser.chat_id
        session_url = reverse_lazy(
            'the_redhuman_is:photo_load_session_update',
            kwargs={'pk': session.id, 'name': 'worker'}
        )
        message = 'Нечитаемое фото в '
        message += ' <a href="https://{}/{}">cессии №{}</a>.'.format(
            request.META['HTTP_HOST'],
            session_url,
            session.id
        )
        bot = send_message(user_chat_id, message)
        if bot is not None:
            bot.sendPhoto(user_chat_id, photo=photo.image)

            return JsonResponse(
                {'message': 'Сообщение бригадиру успешно отправлено'}
            )

    return JsonResponse({'message': 'Ничего не произошло'})
