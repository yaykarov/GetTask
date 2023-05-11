# -*- coding: utf-8 -*-

from finance import models


def get_account(prefix, parent=None):
    if parent:
        return models.Account.objects.get(name__istartswith=prefix, parent=parent)
    else:
        return models.Account.objects.get(name__istartswith=prefix)


def get_root_account(prefix):
    return models.Account.objects.get(name__istartswith=prefix, parent=None)


def ensure_root_account(prefix, full_name):
    return models.Account.objects.get_or_create(
        name__istartswith=prefix,
        parent=None,
        defaults={'name': full_name}
    )[0]


def ensure_account(parent, name):
    return models.Account.objects.get_or_create(
        parent=parent,
        name=name
    )[0]


def ensure_accounts_chain(parent, names):
    account = None
    for name in names:
        account = ensure_account(parent, name)
        parent = account

    return account
