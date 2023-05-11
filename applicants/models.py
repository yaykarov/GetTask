# -*- coding: utf-8 -*-

import datetime

from django.contrib.auth.models import User
from django.db import models
from django.db import transaction
from django.utils import timezone

from the_redhuman_is.models.worker import (
    Country,
    Metro,
    Worker,
)
from the_redhuman_is.models.models import (
    CustomerLocation,
    WorkerTurnout,
)

from utils.phone import normalized_phone


class Status(models.Model):
    name = models.CharField(max_length=100, verbose_name='Название')
    active = models.BooleanField(
        default=True,
        verbose_name='Активен')

    class Meta:
        verbose_name = 'Статус'
        verbose_name_plural = 'Статусы'

    def __str__(self):
        template = '(неактивный) {}'
        if self.active:
            template = '{}'
        return template.format(self.name)

    @property
    def children(self):
        queryset = self.statuses_from.all()
        queryset = queryset.values('status_to__id', 'status_to__name')
        data = []
        for item in queryset:
            data.append(
                {'id': item['status_to__id'], 'name': item['status_to__name']}
            )
        return data


class StatusInitial(models.Model):
    status = models.OneToOneField(
        Status,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name='initial',
        verbose_name='Начальный статус')

    def __str__(self):
        return str(self.status)


class StatusFinal(models.Model):
    status = models.OneToOneField(
        Status,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name='final',
        verbose_name='Конечный статус')

    def __str__(self):
        return str(self.status)


class StatusOrder(models.Model):
    status = models.OneToOneField(
        Status,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name='order',
        verbose_name='Порядок')

    order_int = models.IntegerField(verbose_name='Порядок')


class ApplicantSource(models.Model):
    name = models.CharField(max_length=250, verbose_name='Название')

    class Meta:
        verbose_name = 'Источник информации'
        verbose_name_plural = 'Источники информации'

    def __str__(self):
        return self.name


class Applicant(models.Model):
    TYPES = (
        ('in', 'Вх.'),
        ('out', 'Иcх.')
    )

    WORK_TYPES = (
        ('full', 'Постоянная'),
        ('part', 'Подработка'),
        ('shift', 'Вахта'),
    )

    SEX_TYPES = (
        ('male', 'Мужской'),
        ('female', 'Женский'),
        ('couple', 'Семейная пара')
    )

    active = models.BooleanField(
        default=True,
        verbose_name='Активен')

    init_date = models.DateField(
        default=timezone.now,
        verbose_name='Дата первого контакта')

    phone = models.CharField(
        max_length=15,
        verbose_name='Телефон')

    type = models.CharField(
        max_length=3,
        choices=TYPES,
        verbose_name='Тип звонка')

    author = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        verbose_name='Автор',
        null=True,
        blank=True)

    status = models.ForeignKey(
        Status,
        on_delete=models.PROTECT,
        related_name='applicants',
        verbose_name='Статус',
        null=True,
        blank=True)

    name = models.CharField(
        max_length=250,
        verbose_name='ФИО',
        null=True,
        blank=True)

    sex = models.CharField(
        max_length=64,
        choices=SEX_TYPES,
        verbose_name='Пол',
        null=True,
        blank=True)

    source = models.ForeignKey(
        ApplicantSource,
        on_delete=models.CASCADE,
        related_name='applicants',
        verbose_name='Источник',
        null=True,
        blank=True)

    age = models.IntegerField(
        verbose_name='Возраст',
        null=True,
        blank=True)

    have_docs = models.BooleanField(
        default=False,
        verbose_name='С документами?')

    have_bank_card = models.BooleanField(
        default=False,
        verbose_name='Есть банковская карта')

    metro = models.ForeignKey(
        Metro,
        on_delete=models.PROTECT,
        verbose_name='Метро',
        null=True,
        blank=True)

    location = models.ForeignKey(
        CustomerLocation,
        on_delete=models.PROTECT,
        verbose_name='Объект',
        null=True,
        blank=True)

    work_type = models.CharField(
        max_length=5,
        choices=WORK_TYPES,
        verbose_name='Тип работы',
        null=True,
        blank=True)

    citizenship = models.ForeignKey(
        Country,
        on_delete=models.CASCADE,
        verbose_name='Гражданство',
        null=True,
        blank=True)

    city = models.CharField(
        max_length=50,
        verbose_name='Город проживания',
        null=True,
        blank=True)

    next_date = models.DateField(
        verbose_name='Дата следующего контакта',
        null=True,
        blank=True)

    comment = models.CharField(
        max_length=1024,
        verbose_name='Комментарий',
        null=True,
        blank=True)

    last_edited = models.DateTimeField(
        default=timezone.now,
        verbose_name="Время последнего редактирования")

    passport_series = models.CharField(
        "Серия паспорта",
        max_length=5,
        blank=True,
        null=True
    )

    passport_number = models.CharField(
        "Номер паспорта",
        max_length=11,
        blank=True,
        null=True
    )

    class Meta:
        verbose_name = 'Соискатель'
        verbose_name_plural = 'Соискатели'

    def __str__(self):
        return '{} {}'.format(self.phone, self.pk)

    def save(self, save_history=True, update_last_edited=True, *args, **kwargs):
        if self.phone:
            self.phone = normalized_phone(self.phone)

        if update_last_edited:
            self.last_edited = timezone.now()
        super().save(*args, **kwargs)

        if save_history:
            if hasattr(self, 'history'):
                self._create_history_record()
            else:
                self._create_history_head()

    def is_valid_to_save(self):
        if hasattr(self, 'worker_link'):
            return True
        for worker in self.linked_workers():
            if worker.get_turnouts().exists():
                # Создание заявки задним числом - запрещено.
                return False
        return True

    def try_set_final_status(self, force=False):
        if not hasattr(self.status, 'final'):
            turnouts = self.worker_link.worker.worker_turnouts.all()
            if not force:
                turnouts = turnouts.filter(
                    timesheet__sheet_date__gt=(
                        self.init_date -
                        datetime.timedelta(days=5)
                    )
                )
            if turnouts.exists():
                self.status = StatusFinal.objects.get().status
                self.location = turnouts.first().timesheet.cust_location
                self.save()

    def try_link_to_worker(self, author, comment, worker=None):
        if hasattr(self, 'worker_link'):
            return False

        if not worker:
            workers = self.linked_workers()
            if workers.count() != 1:
                return False
            worker = workers.get()

            duplicates = active_applicants().filter(
                models.Q(phone=self.phone) |
                (
                    models.Q(passport_series__isnull=False) &
                    models.Q(passport_number__isnull=False) &
                    models.Q(passport_series=self.passport_series) &
                    models.Q(passport_number=self.passport_number)
                ),
                worker_link__isnull=True,
            ).exclude(
                pk=self.pk
            )
            if duplicates.exists():
                return False

        if hasattr(worker, 'applicant_link'):
            return False

        ApplicantWorkerLink.objects.create(
            author=author,
            comment=comment,
            applicant=self,
            worker=worker
        )
        return True

    def idle_time(self):
        first_edited = self._first_edited()

        applicant_with_author = self._first_set_author()
        if applicant_with_author:
            first_reaction = applicant_with_author.last_edited
        else:
            first_reaction = timezone.now()

        return first_reaction - first_edited

    # possible linked workers
    def linked_workers(self):
        return Worker.objects.filter(
            models.Q(tel_number=self.phone) |
            (
                models.Q(workerpassport__isnull=False) &
                models.Q(workerpassport__passport_series__isnull=False) &
                models.Q(workerpassport__another_passport_number__isnull=False) &
                models.Q(workerpassport__passport_series=self.passport_series) &
                models.Q(workerpassport__another_passport_number=self.passport_number)
            ),
            applicant_link__isnull=True,
        )

    def history_list(self):
        if hasattr(self, 'history'):
            return self.history.history_list()
        return [self]

    def filtered_history_list(self, is_same_enough):
        filtered_history = []
        for applicant in self.history_list():
            if len(filtered_history) != 0:
                if is_same_enough(applicant, filtered_history[-1]):
                    continue
            filtered_history.append(applicant)

        return filtered_history

    def first_turnout_date(self):
        if hasattr(self, 'worker_link'):
            worker = self.worker_link.worker
            turnouts = worker.get_turnouts()
            if turnouts.exists():
                return turnouts.first().timesheet.sheet_date
        return None

    def has_multiple_possible_links(self):
        if not hasattr(self, 'worker_link'):
            return self.linked_workers().exists()
        return False

    def is_status_final(self):
        return hasattr(self.status, 'final')

    def find_first_in_history(self, check):
        for applicant in self.history_list():
            if check(applicant):
                return applicant
        return None

    def _first_set_author(self):
        def _check(applicant):
            return applicant.author
        return self.find_first_in_history(_check)

    def _first_edited(self):
        if hasattr(self, 'history'):
            return self.history.tail().applicant.last_edited
        return self.last_edited

    def _clone(self):
        clone = Applicant.objects.get(pk=self.pk)
        clone.pk = None
        clone.id = None
        clone.save(save_history=False)
        return clone

    def _create_history_head(self):
        with transaction.atomic():
            node = ApplicantHistoryNode.objects.create(
                applicant=self._clone()
            )
            ApplicantHistoryHead.objects.create(
                applicant=self,
                node=node
            )

    def _create_history_record(self):
        with transaction.atomic():
            node = ApplicantHistoryNode.objects.create(
                applicant=self._clone(),
                previous=self.history.node
            )
            self.history.node = node
            self.history.save()


def active_applicants():
    return Applicant.objects.filter(
        active=True,
        applicanthistorynode__isnull=True,
    ).select_related(
        'author'
    )


class ApplicantHistoryNode(models.Model):
    timestamp = models.DateTimeField(
        default=timezone.now,
        verbose_name="Временная метка")

    previous = models.OneToOneField(
        'self',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        verbose_name='Предыдущие состояние')

    applicant = models.OneToOneField(
        Applicant,
        on_delete=models.CASCADE,
        verbose_name='Слепок состояния соискателя')

    def __str__(self):
        return '{} {}'.format(self.pk, self.applicant)

    def head(self):
        node = self
        while not hasattr(node, 'applicanthistoryhead'):
            if hasattr(node, 'applicanthistorynode'):
                node = node.applicanthistorynode
            else:
                return None
        return node.applicanthistoryhead


class ApplicantHistoryHead(models.Model):
    applicant = models.OneToOneField(
        Applicant,
        on_delete=models.CASCADE,
        related_name='history',
        verbose_name='Актуальное состояния соискателя')

    node = models.OneToOneField(
        ApplicantHistoryNode,
        on_delete=models.CASCADE,
        verbose_name='Голова списка состояний соискателя')

    def tail(self):
        t = self.node
        while t.previous:
            t = t.previous
        return t

    def history_list(self):
        history = []
        item = self.tail()
        while True:
            history.append(item.applicant)
            if hasattr(item, 'applicanthistorynode'):
                item = item.applicanthistorynode
            else:
                break
        history.append(self.applicant)
        return history

    def __str__(self):
        return '{} {}'.format(self.pk, self.applicant)


class VacantCustomerLocation(models.Model):
    location = models.OneToOneField(CustomerLocation, on_delete=models.CASCADE,
                                    verbose_name='Объект')

    class Meta:
        verbose_name = 'Доступные объекты'
        verbose_name_plural = 'Доступные объекты'

    def __str__(self):
        return self.location.full_name()


class AllowedStatusTransition(models.Model):
    status_from = models.ForeignKey(Status, on_delete=models.CASCADE,
                                    related_name='statuses_from',
                                    verbose_name='Из статуса')
    status_to = models.ForeignKey(Status, on_delete=models.CASCADE,
                                  related_name='statuses_to',
                                  verbose_name='В статус')

    class Meta:
        verbose_name = 'Переходы статусов'
        verbose_name_plural = 'Переходы статусов'

    def __str__(self):
        return 'из {} в {}'.format(self.status_from, self.status_to)


class ApplicantWorkerLink(models.Model):
    timestamp = models.DateTimeField(
        default=timezone.now,
        verbose_name="Временная метка")

    author = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        verbose_name='Автор',
        null=True,
        blank=True)

    comment = models.TextField(
        verbose_name='Комментарий')

    applicant = models.OneToOneField(
        Applicant,
        on_delete=models.CASCADE,
        related_name='worker_link',
        verbose_name='Соискатель')

    worker = models.OneToOneField(
        Worker,
        on_delete=models.CASCADE,
        related_name='applicant_link',
        verbose_name='Работник')

    def __str__(self):
        return '{} {}'.format(self.worker.tel_number, self.worker)

    def unlink(self):
        if hasattr(self.applicant.status, 'final'):
            self.applicant.status = StatusInitial.objects.get().status
            self.applicant.save()
        self.delete()


def possible_applicants_to_link(worker):
    if not hasattr(worker, 'applicant_link'):
        passport = worker.actual_passport
        if passport:
            applicants = active_applicants().filter(
                models.Q(phone=worker.tel_number) |
                (
                    models.Q(passport_series__isnull=False) &
                    models.Q(passport_number__isnull=False) &
                    models.Q(passport_series=passport.passport_series) &
                    models.Q(passport_number=passport.another_passport_number)
                ),
                worker_link__isnull=True,
            )
        else:
            applicants = active_applicants().filter(
                phone=worker.tel_number,
                worker_link__isnull=True,
            )

        return list(
            applicants.order_by(
                'init_date'
            )
        )
    return []


def _post_save_worker(sender, instance, created, *args, **kwargs):
    worker = instance
    if worker.tel_number and not hasattr(worker, 'applicant_link'):
        apps = possible_applicants_to_link(worker)
        if len(apps) == 1:
            applicant = apps[0]
            applicant.try_link_to_worker(
                None,
                'Автоматически при сохранении работника.'
            )

    if hasattr(worker, 'applicant_link'):
        worker.applicant_link.applicant.try_set_final_status()


def _post_save_turnout(sender, instance, created, *args, **kwargs):
    worker = instance.worker
    if hasattr(worker, 'applicant_link'):
        worker.applicant_link.applicant.try_set_final_status()


models.signals.post_save.connect(_post_save_worker, sender=Worker)
models.signals.post_save.connect(_post_save_turnout, sender=WorkerTurnout)
