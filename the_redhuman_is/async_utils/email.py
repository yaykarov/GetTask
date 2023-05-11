# -*- coding: utf-8 -*-
import imaplib
import re
import smtplib

from email import encoders
from email.headerregistry import Address
from email.message import EmailMessage
from email.mime.base import MIMEBase

COMMASPACE = ', '

SENDERS = {
    'default': ('test@test.ru', 'test', 'Bender Bending Rodriguez', 'smtp.yandex.ru', '465', 'ssl'),
    'gt_noreply': ('test@test.ru', 'test', 'Bender Bending Rodriguez', 'smtp.yandex.ru', '465', 'ssl'),
    'gt_docs': ('test@test.ru', 'test', 'Bender Bending Rodriguez', 'smtp.yandex.ru', '465', 'ssl'),
}
RECEIVERS = {
    'gt_docs': ('test@test.ru', 'test', 'imap.yandex.ru', '993', 'INBOX'),
}

try:
    from .email_local import *
except ImportError:
    pass


def get_sender_params(key):
    params = SENDERS.get(key)
    if not params:
        params = SENDERS.get('default')
    return params


_MAIL_RX = re.compile('(\S+)@(\S+)')


def do_send_email(sender_params, to, subject, html, attachment=None):
    (
        mail_user,
        mail_password,
        mail_user_description,
        smtp_host,
        smtp_port,
        smtp_type,
    ) = sender_params

    m = _MAIL_RX.match(mail_user)
    mail_user_name = m.group(1)
    mail_user_host = m.group(2)

    msg = EmailMessage()
    address = Address(mail_user_description, mail_user_name, mail_user_host)
    msg['Subject'] = subject
    msg['From'] = address
    msg['To'] = COMMASPACE.join(to) if isinstance(to, list) else to
    msg.add_alternative(html, subtype='html')
    if attachment is not None:
        # Don't ask. See https://stackoverflow.com/questions/3902455/mail-multipart-alternative-vs-multipart-mixed
        del msg['Content-Type']
        msg['Content-Type'] = 'multipart/mixed'

        if not isinstance(attachment, list):
            attachment = [attachment]
        for item in attachment:
            mime_type = item.pop('mime_type', ('application', 'octet-stream'))
            part = MIMEBase(*mime_type)
            part.set_payload(item['body'])
            encoders.encode_base64(part)
            part.add_header(
                'Content-Disposition',
                'attachment',
                filename=('UTF-8', '', item['filename']),
            )
            msg.attach(part)

    if smtp_type == 'tls':
        with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
            server.connect('{}:{}'.format(smtp_host, smtp_port))
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(mail_user, mail_password)
            if attachment is None:
                server.send_message(msg)
            else:
                server.sendmail(address.addr_spec, to, msg.as_string())
    elif smtp_type == 'ssl':
        with smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=10) as server:
            server.connect('{}:{}'.format(smtp_host, smtp_port))
            server.ehlo()
            server.login(mail_user, mail_password)
            if attachment is None:
                server.send_message(msg)
            else:
                server.sendmail(address.addr_spec, to, msg.as_string())
            server.quit()
    else:
        raise NotImplemented


def send_email(to, subject, html, sender='default', attachment=None):
    sender_params = get_sender_params(sender)
    do_send_email(sender_params, to, subject, html, attachment=attachment)


class BadStatusError(Exception):
    pass


def _do_connect_to_mailbox(host, port, user, password, mailbox, readonly):
    # can raise TimeoutError, imaplib.IMAP4.error
    conn = imaplib.IMAP4_SSL(host=host, port=port)  # TimeoutError if wrong port
    status, _ = conn.login(user=user, password=password)
    if status != 'OK':  # TimeoutError if wrong credentials
        raise BadStatusError
    status, _ = conn.select(mailbox, readonly=readonly)
    if status != 'OK':  # status 'NO' if no such mailbox
        raise BadStatusError
    return conn


def do_connect_to_mailbox(receiver, readonly=True):
    user, password, host, port, mailbox = RECEIVERS[receiver]
    return _do_connect_to_mailbox(
        host=host,
        port=port,
        user=user,
        password=password,
        mailbox=mailbox,
        readonly=readonly,
    )
