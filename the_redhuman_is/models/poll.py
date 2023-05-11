# -*- coding: utf-8 -*-


from django.db import models

from django.contrib.auth.models import User

from django.utils import timezone

from .worker import Worker


class WorkerPoll(models.Model):
    timestamp = models.DateTimeField(
        verbose_name='Время отправки вопроса',
        default=timezone.now
    )
    author = models.ForeignKey(
        User,
        verbose_name='Автор',
        on_delete=models.PROTECT
    )

    worker = models.ForeignKey(
        Worker,
        verbose_name='Рабочий',
        on_delete=models.PROTECT,
    )
    question_code = models.TextField(
        verbose_name='Код опроса (для группировки)'
    )
    question_title = models.TextField(
        verbose_name='Заголовок вопроса',
    )
    question = models.TextField(
        verbose_name='Вопрос',
    )

    answer_timestamp = models.DateTimeField(
        verbose_name='Время ответа',
        blank=True,
        null=True,
    )
    answer = models.TextField(
        verbose_name='Ответ',
        blank=True,
        null=True,
    )
