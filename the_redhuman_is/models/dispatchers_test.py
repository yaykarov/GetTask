from django.db import models

from django.contrib.auth.models import User


# Todo: remove this after all
class TestDispatcherPassword(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.PROTECT,
        verbose_name='Диспетчер'
    )
    password = models.TextField(
        verbose_name='Пароль'
    )


class TestDispatcherComment(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.PROTECT,
        verbose_name='Диспетчер'
    )
    comment = models.TextField(
        verbose_name='Комментарий'
    )
