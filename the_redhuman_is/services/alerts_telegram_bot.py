import telegram

from django.conf import settings

from django_telegrambot.apps import DjangoTelegramBot

from telegram.ext import (
    CommandHandler,
    Filters,
    MessageHandler,
)

from telegram_bot.models import (
    ALERTS_BOT,
    TelegramUser,
)

from .chat_telegram_bot import _request_phone

from utils.phone import normalized_phone


def send_alert(message):
    bot = DjangoTelegramBot.getBot(settings.ALERTS_TELEGRAMBOT_TOKEN)

    if bot is not None:
        users = TelegramUser.objects.filter(
            chat_id__isnull=False,
            bot=ALERTS_BOT
        )
        for user in users:
            chat_id = user.chat_id
            try:
                bot.send_message(
                    chat_id,
                    text=message,
                    parse_mode=telegram.ParseMode.HTML
                )
            except telegram.TelegramError as e:
                print(chat_id)
                print(e)

    return bot


def on_tg_start(update, context):
    _request_phone(update, context)


def on_tg_contact(update, context):
    phone = normalized_phone(update.effective_message.contact.phone_number)

    try:
        user = TelegramUser.objects.get(
            phone=phone,
            bot=ALERTS_BOT
        )
        user.chat_id = int(update.message.chat_id)
        user.save()

    except TelegramUser.DoesNotExist:
        # Todo: don't be so rude, response something
        pass


def tg_init():
    if settings.ALERTS_TELEGRAMBOT_TOKEN is None:
        return

    chat_dispatcher = DjangoTelegramBot.get_dispatcher(
        settings.ALERTS_TELEGRAMBOT_TOKEN
    )

    chat_dispatcher.add_handler(CommandHandler('start', on_tg_start))
    chat_dispatcher.add_handler(MessageHandler(Filters.contact, on_tg_contact))
