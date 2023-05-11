# -*- coding: utf-8 -*-

import datetime
import pytz
import re
import smtplib

from email.headerregistry import Address
from email.message import EmailMessage

from django.utils import timezone

from applicants import models
from utils.phone import normalized_phone


IMAP_HOST = 'imap.yandex.ru'
IMAP_PORT = '993'

SMTP_HOST = 'smtp.yandex.ru'
SMTP_PORT = '465'

MAIL_USER = 'test@test.ru'
MAIL_PASSWORD = 'test'
MAIL_USER_DESCRIPTION = 'Bender Bending Rodriguez'

try:
    from .email_local import *
except ImportError:
    pass


NAME_RX = re.compile('.*<td><b>Имя</b>:</td><td>(.+)</td>.*')
PHONE_RX = re.compile('.*<td><b>Номер телефона</b>:</td><td>(.+)</td>.*')
COMMENT_RX = re.compile('.*<td><b>Вакансия</b>:</td><td>(.+)</td>.*')

def _parse_message(message):
    name = None
    phone = None
    comment = None
    for line in message.split('\n'):
        # just in case
        line = line.strip()
        m = NAME_RX.match(line)
        if m:
            name = m.group(1)
        m = PHONE_RX.match(line)
        if m:
            phone = m.group(1)
        m = COMMENT_RX.match(line)
        if m:
            comment = m.group(1)

    return name, phone, comment


def _make_applicant(message):
    payload = message.get_payload()
    if isinstance(payload, str):
        name, phone, comment = _parse_message(payload)

        phone = normalized_phone(phone, strict=True)

        # No need to store garbage
        if not phone or len(phone) < 9:
            return

        if not comment:
            comment = ''

        initial_status = models.StatusInitial.objects.get().status
        # Todo - remove hardcored db values
        source = models.ApplicantSource.objects.get(name='alphasklad.ru')
        now = timezone.now().astimezone(pytz.timezone('Europe/Moscow'))

        applicants = models.Applicant.objects.filter(phone=phone)
        if applicants.exists():
            # Todo: notification of multiple instances with same phones?
            applicant = applicants.first()

            applicant.status = initial_status
            applicant.next_date = now.date()
            applicant.comment += ', запрос из формы {}, {}'.format(
                now.strftime('%d.%m.%y %H:%M'),
                name
            )
            if comment:
                applicant.comment += (' ' + comment)

            applicant.save()
        else:
            models.Applicant.objects.create(
                phone=phone,
                type='out',
                status=initial_status,
                name=name,
                source=source,
                next_date=datetime.date.today(),
                comment=comment,
            )


#def check_email():
#    connection = IMAP4_SSL(host=IMAP_HOST, port=IMAP_PORT)
#    connection.login(user=MAIL_USER, password=MAIL_PASSWORD)
#    status, count = connection.select('INBOX')
#
#    if status != 'OK':
#        return
#
#    # Search criteria: https://gist.github.com/martinrusev/6121028
#    status, data = connection.search(None, 'UNSEEN') # UNSEEN / ALL
#    for num in data[0].split():
#        status, message_data = connection.fetch(num, '(RFC822)')
#        message = email.message_from_bytes(message_data[0][1])
#
#        _make_applicant(message)
#
#    connection.close()
#    connection.logout()


_MAIL_RX = re.compile('(\S+)@(\S+)')
_M = _MAIL_RX.match(MAIL_USER)
_MAIL_USER_NAME = _M.group(1)
_MAIL_USER_HOST = _M.group(2)

def send_email(to, subject, html):
    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = Address(MAIL_USER_DESCRIPTION, _MAIL_USER_NAME, _MAIL_USER_HOST)
    msg['To'] = to
    msg.add_alternative(html, subtype='html')

    server = smtplib.SMTP_SSL('{}:{}'.format(SMTP_HOST, SMTP_PORT))
    server.login(MAIL_USER, MAIL_PASSWORD)
    server.send_message(msg)
    server.quit()
