import firebase_admin
from firebase_admin import credentials
from firebase_admin import messaging


CERT_FILENAME = None

try:
    from .push_notifications_local import *
except ImportError:
    pass


if CERT_FILENAME:
    firebase_admin.initialize_app(credentials.Certificate(CERT_FILENAME))


def send_single_message(title, body, data, tag, token):
    if not CERT_FILENAME:
        return None

    if title is not None or body is not None:
        notification = messaging.AndroidNotification(
            title=title,
            body=body,
            tag=tag
        )
    else:
        notification = None
    android_config = messaging.AndroidConfig(
        collapse_key='status_update', # Todo: does it really matter?
        notification=notification,
        data=data
    )
    message = messaging.Message(
        android=android_config,
        token=token,
    )

    return messaging.send(message)
