from django.conf import settings

from django_telegrambot.apps import DjangoTelegramBot

from telegram.ext import (
    CommandHandler,
    Filters,
    MessageHandler,
)

from the_redhuman_is.services.chat_telegram_bot import (
    on_tg_contact,
    on_tg_start,
    on_tg_text_message,
)

from the_redhuman_is.services.alerts_telegram_bot import tg_init as alerts_tg_init


def main():
    print('Loading handlers for chat telegram bot')

    if settings.CHAT_TELEGRAMBOT_TOKEN is None:
        return

    chat_dispatcher = DjangoTelegramBot.get_dispatcher(
        settings.CHAT_TELEGRAMBOT_TOKEN
    )

    chat_dispatcher.add_handler(CommandHandler('start', on_tg_start))
    chat_dispatcher.add_handler(MessageHandler(Filters.contact, on_tg_contact))
    chat_dispatcher.add_handler(MessageHandler(Filters.text, on_tg_text_message))

    alerts_tg_init()
