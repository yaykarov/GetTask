# -*- coding: utf-8 -*-

import telegram

from django.conf import settings

from django_telegrambot.apps import DjangoTelegramBot

from . import models


def send_message(chat_id, message):
    bot = DjangoTelegramBot.getBot(settings.OFFICE_TELEGRAMBOT_TOKEN)
    if bot is not None:
        try:
            bot.sendMessage(
                chat_id,
                text=message,
                parse_mode=telegram.ParseMode.HTML
            )
        except telegram.TelegramError as e:
            print(chat_id)
            print(e)

    return bot


def send_message_to_group(message, group_name):
    users = models.TelegramUser.objects.filter(
        user__groups__name=group_name,
        chat_id__isnull=False,
        bot=models.OFFICE_BOT,
    )
    for user in users:
        chat_id = user.chat_id
        send_message(chat_id, message)
