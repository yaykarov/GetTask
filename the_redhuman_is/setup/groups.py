# -*- coding: utf-8 -*-

from django.contrib.auth.models import Group


# Todo: change to atomic rights, remove unused groups
STANDARD_GROUPS = [
    # Технические группы
    'Аналитика',
    'Интеграция с телефонией',

    # +-OK groups
    'Бан рабочих',
    'Доставка-диспетчер',
    'Доставка-руководитель',
    'Импорт банковских выписок',
    'Подача расходов',
    'Закрытие ведомостей',
    'Учет операций',

    # To change/split
    'Бригадиры', # Todo: split
    'Верификация новых пользователей',
    'Подборщики',
    'Управление расходами',
    'Доставка-проверяющий', # Контролер (?)
    'Касса', # Todo: split

    'Менеджеры', # Todo

    # To remove
    'hr_inspector', # Todo: remove
    'Бухгалтеры внешние', # Todo: remove
    'Операционисты',
    'Подборщики внешние',
    'Подборщики руководитель',
]


def create_standard_user_groups():
    Group.objects.bulk_create(
        [Group(name=name) for name in STANDARD_GROUPS]
    )
