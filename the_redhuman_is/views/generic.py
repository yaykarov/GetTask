# -*- coding: utf-8 -*-

import logging

from django.contrib import auth
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.http import HttpResponseNotFound
from django.shortcuts import redirect
from django.shortcuts import render

from django.views.decorators.csrf import csrf_exempt
from rest_framework import status

from rest_framework.decorators import api_view

from the_redhuman_is import models

from the_redhuman_is.views import utils


dev_logger = logging.getLogger('dev_logger')

@login_required(login_url='/rf/login/')
def main(request):
    # Todo: убрать эту недо-поддержку клиентов
    account = utils.get_customer_account(request)
    if account:
        timesheets = models.TimeSheet.objects.filter(
            customer=account.customer).order_by('-sheet_date')
        if timesheets.exists():
            # Для клиентов - главная страница - это последний табель
            return utils.render_timesheet(request, timesheets.first(), True)
        else:
            # Todo: proper template
            return HttpResponse('Нет данных')

    user_groups = request.user.groups.values_list('name', flat=True)
    def _show_applicants_list():
        applicants_groups = [
            'Подборщики',
            'Подборщики внешние',
            'Подборщики руководитель'
        ]
        for group in applicants_groups:
            if group in user_groups:
                return True

    homepage = None
    # Спец. страница имеет максимальный приоритет
    if hasattr(request.user, 'homepage'):
        homepage = request.user.homepage.page_name

    if not homepage and _show_applicants_list():
        homepage = 'applicants:list'

    if not homepage and 'Бухгалтеры внешние' in user_groups:
        homepage = 'the_redhuman_is:contracts_list'

    if not homepage and 'Доставка-диспетчер' in user_groups:
        homepage = '/rf/delivery/'

    if not homepage and 'Бригадиры' in user_groups:
        homepage = 'the_redhuman_is:photo_load_session_list'

    if not homepage:
        # Для обычных сотрудников - главная страница - это список рабочих
        homepage = 'the_redhuman_is:my_page'

    return redirect(homepage)


@csrf_exempt
def landing_login(request):
    try:
        username = request.POST['name']
        password = request.POST['password']
        user = auth.authenticate(username=username, password=password)
        if user is None:
            raise Exception('User not found')
        else:
            auth.login(request, user)
            return redirect('the_redhuman_is:main')

    except Exception as e:
        dev_logger.error(repr(e))
        return HttpResponseNotFound()


def logout(request):
    auth.logout(request)
    return redirect('the_redhuman_is:main')


@login_required
def void(request):
    customer_account = utils.get_customer_account(request)
    return render(
        request,
        'the_redhuman_is/void.html',
        {
            'is_for_customer': customer_account is not None,
            'void_menu': True
        }
    )


@api_view(['GET'])
def check_auth(request):
    if request.user.is_authenticated:
        return HttpResponse('')
    else:
        return HttpResponse(status=status.HTTP_401_UNAUTHORIZED)

