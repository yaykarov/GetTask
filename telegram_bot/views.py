# -*- coding: utf-8 -*-

import telegram

from django.core.exceptions import ObjectDoesNotExist

from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.shortcuts import redirect
from django.shortcuts import render
from django.urls import reverse_lazy
from django.views import View

from django_telegrambot.apps import DjangoTelegramBot

from telegram_bot.models import TelegramUser

from the_redhuman_is.auth import staff_account_required

from the_redhuman_is.models import Photo
from the_redhuman_is.models import PhotoLoadSession
from the_redhuman_is.models import Worker


# Todo: just remove this
class BadPhotoView(LoginRequiredMixin, View):
    def post(self, *args, **kwargs):
        status = True
        status_message = 'Ошибка при отправлении сообщения.'
        try:
            photo_id = self.request.POST.get('id')
            photo = Photo.objects.get(id=photo_id)
        except ObjectDoesNotExist:
            status = False
            status_message = 'Сообщение не отправлено. Сессия не найдена'
        else:
            try:
                session = PhotoLoadSession.objects.get(pk=photo.object_id)
                user = session.sender
                user_chat_id = user.telegramuser.chat_id
            except:
                status = False
                status_message = 'Сообщение не отправлено. \
                                  Не найден номер телефона'
            else:
                session_url = reverse_lazy(
                    'the_redhuman_is:photo_load_session_update',
                    kwargs={'pk': session.id, 'name': 'worker'}
                )
                message = 'Нечитаемое фото в '
                message += ' <a href="http://{}/{}">cессии №{}</a>.'.format(
                    self.request.META['HTTP_HOST'],
                    session_url,
                    session.id
                )
                bot = DjangoTelegramBot.getBot(settings.OFFICE_TELEGRAMBOT_TOKEN)
                if bot:
                    bot.sendMessage(
                        user_chat_id,
                        text=message,
                        parse_mode=telegram.ParseMode.HTML
                    )
                    bot.sendPhoto(user_chat_id, photo=photo.image)
        if status:
            return JsonResponse(
                {'message': 'Сообщение бригадиру успешно отправлено'})
        else:
            return JsonResponse({'message': status_message}, status=500)


@staff_account_required
def users_list(request):
    result = []
    users = TelegramUser.objects.all()
    for user in users:
        workers = Worker.objects.filter(
            tel_number=user.phone
        )
        if workers.count() == 1:
            worker = workers.get()
        else:
            worker = None
        result.append((user, worker))

    return render(
        request,
        'telegram_bot/users_list.html',
        {
            'users': result
        }
    )


@staff_account_required
def delete_user(request, pk):
    user = TelegramUser.objects.get(pk=pk)
    user.user.is_active = False
    user.user.save()
    user.delete()

    return redirect('telegram_bot:users_list')
