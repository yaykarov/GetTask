import uuid

from django.db import models

from .worker import Worker


class WorkerTelegramUserId(models.Model):
    worker = models.OneToOneField(
        Worker,
        on_delete=models.PROTECT,
        verbose_name='Работник'
    )
    telegram_user_id = models.BigIntegerField(
        verbose_name = 'id пользователя в телеграме'
    )

    def __str__(self):
        return f'{self.worker}/{self.telegram_user_id}'


class WorkerRocketchatVisitor(models.Model):
    worker = models.OneToOneField(
        Worker,
        on_delete=models.PROTECT,
        verbose_name='Работник'
    )
    rocketchat_visitor_token = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
    )
    rocketchat_visitor_room_id = models.TextField(
        unique=True,
    )

    def __str__(self):
        return f'{self.worker}'
