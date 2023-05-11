from django.contrib.auth.models import User
from django.db import models


OFFICE_BOT = 'office'
ALERTS_BOT = 'alerts'


class TelegramUser(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        verbose_name='Пользователь'
    )
    chat_id = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        verbose_name='id пользователя в телеграме'
    )
    phone = models.CharField(
        max_length=12,
        verbose_name='Телефон'
    )
    date = models.DateTimeField(
        auto_now=True
    )
    bot = models.CharField(
        max_length=20,
        choices=[
            (OFFICE_BOT, 'Офисный'),
            (ALERTS_BOT, 'Разработческий'),
        ],
        verbose_name='Бот',
    )

    class Meta:
        db_table = 'telegram_bot_user'
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'bot'],
                name='unique_user_bot'
            ),
        ]

    def __str__(self):
        return '{}'.format(self.phone)
