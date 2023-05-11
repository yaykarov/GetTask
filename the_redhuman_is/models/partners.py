from django.db import models


class MobileAppPartner(models.Model):
    name = models.TextField(
        verbose_name='Имя партнера'
    )
    api_entry = models.TextField(
        verbose_name='Корень API для мобильного приложения'
    )

    def __str__(self):
        return f'{self.name} {self.api_entry}'
