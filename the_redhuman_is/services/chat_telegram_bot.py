import telegram

from django.conf import settings

from django_telegrambot.apps import DjangoTelegramBot

from the_redhuman_is.models.chat import WorkerTelegramUserId
from the_redhuman_is.models.worker import (
    BannedWorker,
    Worker,
    WorkerIsBannedException,
)

from the_redhuman_is.services import rocketchat

from utils.phone import normalized_phone


def send_message_to_worker(worker, message):
    try:
        worker_telegram_user_id = WorkerTelegramUserId.objects.get(worker=worker)
        chat_id = worker_telegram_user_id.telegram_user_id

        bot = DjangoTelegramBot.getBot(settings.CHAT_TELEGRAMBOT_TOKEN)
        if bot is not None:
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

    except WorkerTelegramUserId.DoesNotExist:
        return None


def _send_welcome_message(update, context, worker_name):
    context.bot.send_message(
        update.message.chat_id,
        text=f'Здравствуйте, {worker_name}.\nРады видеть Вас в чате!'
    )


def _send_banned_message(update, context):
    context.bot.send_message(
        update.message.chat_id,
        text='К сожалению, Вы забанены за нарушение правил пользования сервисом.'
    )


def _send_playmarket_link(update, context):
    playmarket_url = 'https://play.google.com/store/apps/details?id=ru.ozbs.selfemployers'
    message = (
        'К сожалению, Вашего номера телефона нет в нашей базе данных. '
        f'Зарегистрируйтесь в <a href="{playmarket_url}">приложении GetTask</> '
        'чтобы продолжить работу.'
    )
    context.bot.send_message(
        update.message.chat_id,
        text=message,
        parse_mode=telegram.ParseMode.HTML
    )


def _request_phone(update, context):
    button_label = 'Отправить номер телефона'
    message = (
        'Для начала работы нам нужно знать Ваш номер телефона. '
        f'Нажмите на кнопку "{button_label}".'
    )
    phone_button = telegram.KeyboardButton(
        text=button_label,
        request_contact=True,
    )
    context.bot.send_message(
        update.message.chat_id,
        text=message,
        reply_markup=telegram.ReplyKeyboardMarkup(
            [[phone_button]],
            one_time_keyboard=True
        )
    )


def _worker_for_chat(chat_id):
    telegram_user_id = int(chat_id)
    worker = WorkerTelegramUserId.objects.get(telegram_user_id=telegram_user_id).worker
    try:
        banned_worker = worker.banned
        raise WorkerIsBannedException()

    except BannedWorker.DoesNotExist:
        return worker


# Telegram commands

def on_tg_start(update, context):
    try:
        worker = _worker_for_chat(update.message.chat_id)
        _send_welcome_message(update, context, worker.name)

    except WorkerTelegramUserId.DoesNotExist:
        _request_phone(update, context)

    except WorkerIsBannedException:
        _send_banned_message(update, context)


def on_tg_text_message(update, context):
    print('on_tg_text_message')
    try:
        worker = _worker_for_chat(update.message.chat_id)

        print(update.message.text)
        print(update.message)
        rocketchat.send_message_from_worker(worker, update.message.text)

    except WorkerTelegramUserId.DoesNotExist:
        _request_phone(update, context)

    except WorkerIsBannedException:
        _send_banned_message(update, context)


def on_tg_contact(update, context):
    phone = normalized_phone(update.effective_message.contact.phone_number)

    try:
        worker = Worker.objects.get(tel_number=phone)

        try:
            worker_telegram_user_id = WorkerTelegramUserId.objects.get(worker=worker)
            worker_telegram_user_id.telegram_user_id = int(update.message.chat_id)
            worker_telegram_user_id.save()

        except WorkerTelegramUserId.DoesNotExist:
            WorkerTelegramUserId.objects.create(
                worker=worker,
                telegram_user_id=int(update.message.chat_id),
            )

        _send_welcome_message(update, context, worker.name)

    except Worker.DoesNotExist:
        _send_playmarket_link(update, context)
