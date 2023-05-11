import enum


class AppFlavor(enum.Enum):
    master = 'MASTER'
    external_user = 'EXTERNAL_USER'


APP_FLAVOR = AppFlavor.external_user

try:
    from .app_flavors_local import APP_FLAVOR_CODE
    APP_FLAVOR = AppFlavor(APP_FLAVOR_CODE)
except ImportError:
    pass


def is_app_flavor_master():
    return APP_FLAVOR == AppFlavor.master
