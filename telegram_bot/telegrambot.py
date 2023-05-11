import logging
import re
import telegram

from importlib import import_module

from django.conf import settings
from django.urls import reverse
from django_telegrambot.apps import DjangoTelegramBot
from telegram import InlineKeyboardButton
from telegram.ext import CommandHandler, MessageHandler, filters

from telegram_bot.models import (
    OFFICE_BOT,
    TelegramUser,
)

from the_redhuman_is.services.delivery_requests import send_new_invitation_sms

SessionStore = import_module(settings.SESSION_ENGINE).SessionStore

logger = logging.getLogger(__name__)


def start(update, context):
    button_name = 'Отправить номер телефона'
    message = 'Для правильной работы нам нужен Ваш номер телефона. ' \
              'Нажмите на кнопку "{}"'.format(button_name)
    contact_keyboard = telegram.KeyboardButton(
        text=button_name,
        request_contact=True
    )
    reply_markup = telegram.ReplyKeyboardMarkup(
        [[contact_keyboard, ]],
        one_time_keyboard=True
    )
    context.bot.sendMessage(
        update.message.chat_id,
        text=message,
        reply_markup=reply_markup
    )


def contact_callback(update, context):
    chat_id = update.message.chat_id
    contact = update.effective_message.contact
    phone = re.sub('[^0-9]', '', contact.phone_number)
    t_user = TelegramUser.objects.filter(
        phone=phone,
        user__is_active=True,
        bot=OFFICE_BOT,
    ).order_by(
        'pk'
    ).last()
    if t_user:
        t_user.chat_id = chat_id
        t_user.save()
        context.bot.sendMessage(
            chat_id,
            text='Спаcибо, теперь Вы сможете получать сообщения от бота.',
        )
        rh_help(update, context)
    else:
        context.bot.sendMessage(
            chat_id,
            text='К сожалению Вашего номера телефона нет в базе данных.',
        )


def error(update, context):
    logger.warning('Update "%s" caused error "%s"' % (update, context.error))


def rh_help(update, context):
    chat_id = update.message.chat_id
    t_user = TelegramUser.objects.filter(
        chat_id=chat_id,
        user__is_active=True,
        bot=OFFICE_BOT,
    ).order_by(
        'pk'
    ).first()
    if t_user:
        session = SessionStore()
        session['_auth_user_id'] = t_user.user.pk
        session.create()
        session_id = session.session_key
        url_worker = 'http://{}{}?session_id={}'.format(
            settings.SITE_NAME,
            reverse('the_redhuman_is:photo_load_session_add',
                    kwargs={'name': 'worker'}),
            session_id
        )
        url_contract = 'http://{}{}?session_id={}'.format(
            settings.SITE_NAME,
            reverse('the_redhuman_is:photo_load_session_add',
                    kwargs={'name': 'contract'}),
            session_id
        )
        url_timesheet = 'http://{}{}?session_id={}'.format(
            settings.SITE_NAME,
            reverse('the_redhuman_is:photo_load_session_add',
                    kwargs={'name': 'timesheet'}),
            session_id
        )
        reply_markup = telegram.InlineKeyboardMarkup([
            [InlineKeyboardButton(
                "Добавить фото рабочего",
                url=url_worker
            )],
            [InlineKeyboardButton(
                "Добавить фото договора",
                url=url_contract
            )],
            [InlineKeyboardButton(
                "Добавить фото табеля",
                url=url_timesheet
            )]
        ])
        context.bot.sendMessage(
            chat_id,
            text='Дальнейшие действия:',
            reply_markup=reply_markup
        )


def invite(update, context):
    args = context.args

    if len(args) == 1:
        phone = args[0]

        try:
            send_new_invitation_sms(phone)
            message = f'Смс на номер {phone} отправлено.'
        except Exception:
            message = 'Смс отправить не удалось. Что-то пошло не так.'
    elif len(args) == 0:
        message = (
            'Укажите номер, куда надо отправить пригласительное смс.'
            ' (/invite 792612312333)'
        )
    else:
        message = 'Слишком много аргументов. Укажите 1 номер телефона.'

    chat_id = update.message.chat_id
    context.bot.sendMessage(chat_id, message)


def main():
    print('Loading handlers for office telegram bot')

    if settings.OFFICE_TELEGRAMBOT_TOKEN is None:
        return

    office_dispatcher = DjangoTelegramBot.get_dispatcher(
        settings.OFFICE_TELEGRAMBOT_TOKEN
    )

    # on different commands - answer in Telegram
    office_dispatcher.add_handler(CommandHandler('start', start))
    office_dispatcher.add_handler(CommandHandler('help', rh_help))
    office_dispatcher.add_handler(CommandHandler('invite', invite))

    # on noncommand i.e message - echo the message on Telegram
    # dp.add_handler(MessageHandler([filters.text], echo))
    office_dispatcher.add_handler(MessageHandler(filters.contact, contact_callback))

    # log all errors
    office_dispatcher.add_error_handler(error)
