# -*- coding: utf-8 -*-

import secrets
import string
import uuid

from django.db import models
from django.db import transaction

from django.core.exceptions import ObjectDoesNotExist

from django.contrib.auth.models import User

from django.utils import timezone

from utils.phone import normalized_phone


class OneOffCode(models.Model):
    timestamp = models.DateTimeField(
        verbose_name='Время создания',
        default=timezone.now
    )
    user = models.OneToOneField(
        User,
        on_delete=models.PROTECT
    )
    # Todo: don't store this password as a plain text
    code = models.TextField(
        verbose_name='Код'
    )


def _random_code():
    return ''.join(secrets.choice(string.digits) for i in range(6))


def _code_for_phone(phone: str):
    SPECIAL_PHONES = [
        '70000000001',
        '70000000002',
        '70000000003',
        '70000000004',
        '70000000005',
    ]

    if phone in SPECIAL_PHONES:
        return '837482'
    else:
        return _random_code()


def create_user_with_prefix(prefix):
    max_pk = User.objects.all().order_by('pk').last().pk
    user = User.objects.create_user('tmp_{}_{}'.format(prefix, max_pk))
    try:
        user.username = '{}_{}'.format(prefix, user.pk)
        user.save()
    except Exception as e:
        pass

    return user


@transaction.atomic
def create_user_with_one_off_code(phone: str):
    user = create_user_with_prefix('user')
    return OneOffCode.objects.create(user=user, code=_code_for_phone(phone))


def update_one_off_code(user: User, phone: str):
    user_phone, _ = UserPhone.objects.update_or_create(
        user=user,
        defaults={'phone': phone}
    )
    try:
        code = OneOffCode.objects.get(user=user)
        code.timestamp = timezone.now()
        code.code = _code_for_phone(user_phone.phone)
        code.save()

    except ObjectDoesNotExist as e:
        code = OneOffCode.objects.create(user=user, code=_code_for_phone(user_phone.phone))

    return code


class UserPhone(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.PROTECT
    )
    phone = models.TextField(
        verbose_name='Телефон'
    )

    def __str__(self):
        return '{} {}'.format(
            self.phone,
            self.user
        )


@transaction.atomic
def user_with_one_off_code_by_phone(phone):
    phone = normalized_phone(phone)
    try:
        user_phone = UserPhone.objects.get(phone=phone)
        return update_one_off_code(user_phone.user, phone)

    except ObjectDoesNotExist as e:
        code = create_user_with_one_off_code(phone)
        UserPhone.objects.create(user=code.user, phone=phone)
        return code


class UserRegistrationInfo(models.Model):
    timestamp = models.DateTimeField(
        verbose_name='Время создания',
        default=timezone.now
    )
    full_name = models.TextField(
        verbose_name='ФИО',
        default='-'
    )
    organization_name = models.TextField(
        verbose_name='Организация',
        default='-'
    )
    phone = models.TextField(
        verbose_name='Телефон',
        default='-'
    )
    email = models.TextField(
        verbose_name='Почта',
        unique=True
    )
    password = models.TextField(
        verbose_name='Пароль'
    )
    key = models.UUIDField(
        default=uuid.uuid4,
        editable=False
    )


def start_registration(
        full_name,
        organization_name,
        phone,
        email,
        password,
):
    return UserRegistrationInfo.objects.create(
        full_name=full_name,
        organization_name=organization_name,
        phone=phone,
        email=email,
        password=password,
    )


@transaction.atomic
def finish_registration(key, user_prefix):
    reg_info = UserRegistrationInfo.objects.select_for_update().get(
        key=uuid.UUID(key)
    )

    user = create_user_with_prefix(user_prefix)
    user.email = reg_info.email
    user.first_name = reg_info.full_name
    user.set_password(reg_info.password)
    user.save()

    organization_name = reg_info.organization_name
    phone = reg_info.phone

    reg_info.delete()

    return user, organization_name, phone


class ResetPasswordRequest(models.Model):
    timestamp = models.DateTimeField(
        verbose_name='Время создания',
        default=timezone.now
    )
    user = models.OneToOneField(
        User,
        on_delete=models.PROTECT
    )
    key = models.UUIDField(
        default=uuid.uuid4,
        editable=False
    )

    def __str__(self):
        return '{} {} {}'.format(self.user, self.user.email, self.key)


@transaction.atomic
def request_password_reset(user):
    try:
        request = ResetPasswordRequest.objects.select_for_update().get(user=user)

        request.timestamp = timezone.now()
        request.key = uuid.uuid4()

        request.save()

    except ObjectDoesNotExist:
        request = ResetPasswordRequest.objects.create(user=user)

    return request


@transaction.atomic
def update_password(key, password):
    request = ResetPasswordRequest.objects.select_for_update().get(
        key=uuid.UUID(key)
    )

    user = request.user

    user.set_password(password)
    user.save()

    request.delete()

    return user
