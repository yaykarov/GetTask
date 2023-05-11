# -*- coding: utf-8 -*-

from django.db import models

from django.contrib.auth.models import User


class HomePage(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        verbose_name='Пользователь'
    )

    page_name = models.CharField(
        max_length=250,
        verbose_name='Домашняя страница'
    )

    def __str__(self):
        return '{}: {}'.format(
            self.user,
            self.page_name
        )
