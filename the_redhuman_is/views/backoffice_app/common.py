from django.http import JsonResponse

from django.urls import reverse

from redhuman.middleware import is_page_allowed

from the_redhuman_is.services.app_flavors import is_app_flavor_master

from the_redhuman_is.views.backoffice_app.auth import bo_api


_FULL_MENU_COMMON = [
    {
        'label': 'Финансы',
        'items': [
            {
                'label': 'Рентабельность',
                'path': ('the_redhuman_is', 'report_efficiency'),
            },
            {
                'label': 'Расходы',
                'path': ('the_redhuman_is', 'expenses_index'),
                'rf_path': '/rf/expenses/',
                'key': 'expenses_page',
            },
            {
                'label': 'Учёт операций',
                'path': ('the_redhuman_is', 'expense_page'),
            },
            {
                'label': 'Импорт выписок',
                'path': ('import1c', 'upload-1c-file'),
            },
            {
                'label': 'Баланс',
                'path': ('the_redhuman_is', 'operating_account_tree'),
            },
        ]
    },
    {
        'label': 'Отчеты',
        'items': [
            {
                'label': 'Заявки за период',
                'path': ('the_redhuman_is', 'delivery_requests_count_report'),
                'rf_path': '/rf/delivery/requests_count/',
                'key': 'requests_count'
            },
            {
                'label': 'Загруженность исполнителей',
                'path': ('the_redhuman_is', 'delivery_turnouts_report'),
            },
        ]
    },
    {
        'label': 'Взаиморасчеты',
        'items': [
            {
                'label': 'Ведомости',
                'path': ('the_redhuman_is', 'paysheet_v2_list'),
            },
            {
                'label': 'Сверки',
                'path': ('the_redhuman_is', 'reconciliation_list'),
                'path_suffix': '?is_closed=False',
            },
        ]
    },
    {
        'label': 'Заявки',
        'items': [
            {
                'label': 'Список',
                'path': ('the_redhuman_is', 'delivery_index'),
                'rf_path': '/rf/delivery/',
                'key': 'requests_page',
            },
            {
                'label': 'Карта',
                'path': ('the_redhuman_is', 'delivery_requests_on_map'),
                'rf_path': '/rf/delivery/requests_on_map/',
                'key': 'delivery_requests_on_map',
            },
            {
                'label': 'История импорта',
                'path': ('the_redhuman_is', 'delivery_imports_report'),
                'rf_path': '/rf/delivery/imports_report/',
                'key': 'imports_report',
            },
        ]
    },
    {
        'label': 'Исполнители',
        'items': [
            {
                'label': 'На регистрации',
                'path': ('the_redhuman_is', 'photo_load_session_list'),
            },
            {
                'label': 'Зарегистрированные',
                'path': ('the_redhuman_is', 'delivery_workers_report'),
                'rf_path': '/rf/delivery/workers_report/',
                'key': 'workers_report',
            },
            {
                'label': 'Подтвердились на завтра',
                'path': ('the_redhuman_is', 'delivery_online_status_report'),
            },
            {
                'label': 'Должники',
                'path': ('the_redhuman_is', 'workers_debtors'),
            },
            {
                'label': 'Мы должны',
                'path': ('the_redhuman_is', 'workers_creditors'),
            },
            {
                'label': 'Компенсация проживания',
                'path': ('the_redhuman_is', 'hostel_expenses_report'),
            },
            {
                'label': 'Компенсация проживания, статистика',
                'path': ('the_redhuman_is', 'hostel_list'),
            },
        ]
    },
    {
        'label': 'Клиенты',
        'items': [
            {
                'label': 'Список',
                'path': ('the_redhuman_is', 'customer_list'),
            },
            {
                'label': 'Аналитика',
                'path': ('the_redhuman_is', 'report_customer_summary'),
            },
        ]
    },
    {
        'label': 'Настройки',
        'items': [
            {
                'label': 'Справочники',
                'path': ('the_redhuman_is', 'catalogs'),
            },
            {
                'label': 'Автоначисления',
                'path': ('the_redhuman_is', 'autocharge_settings'),
            },
            {
                'label': 'Моя страница',
                'path': ('the_redhuman_is', 'my_page'),
            },
            {
                'label': 'Выйти',
                'path': ('the_redhuman_is', 'logout'),
                'key': 'logout'
            },
        ]
    },
]


_FULL_MENU_EXTRA = [
    {
        'label': 'Старые страницы',
        'items': [
            {
                'label': 'Заявки - Заявки',
                'path': ('the_redhuman_is', 'orders_dashboard'),
            },
            {
                'label': 'Кадры - Список работников',
                'path': ('the_redhuman_is', 'list_workers'),
            },
            {
                'label': 'Кадры - Список самозанятых',
                'path': ('the_redhuman_is', 'self_employment_list'),
            },
            {
                'label': 'Кадры - Договоры',
                'path': ('the_redhuman_is', 'contracts_list'),
                'path_suffix': '?display=to_register',
            },
            {
                'label': 'Кадры - Сводка по подрядчикам',
                'path': ('the_redhuman_is', 'contractors_summary'),
            },
            {
                'label': 'Кадры - Документы',
                'path': ('the_redhuman_is', 'workers_documents'),
            },
            {
                'label': 'Кадры - Телеграм-пользователи',
                'path': ('telegram_bot', 'users_list'),
            },
            {
                'label': 'Подбор - Соискатели',
                'path': ('applicants', 'list'),
                'path_suffix': '?display=to_register',
            },
            {
                'label': 'Учет - Закрытие месяца',
                'path': ('the_redhuman_is', 'period_close_document'),
            },
            {
                'label': 'Учет - Начислить',
                'path': ('the_redhuman_is', 'make_payroll'),
            },
            {
                'label': 'Учет - Ведомости - календарь',
                'path': ('the_redhuman_is', 'paysheet_calendar'),
            },
            {
                'label': 'Учет - Внести вычеты',
                'path': ('the_redhuman_is', 'fine_utils_import_fines'),
            },
            {
                'label': 'Отчеты - Платежный календарь',
                'path': ('the_redhuman_is', 'payment_schedule_index'),
            },
            {
                'label': 'Отчеты - Календарь',
                'path': ('the_redhuman_is', 'workers_in_calendar'),
            },
            {
                'label': 'Отчеты - Невыходы',
                'path': ('the_redhuman_is', 'report_absent'),
            },
            {
                'label': 'Отчеты - Поток персонала',
                'path': ('the_redhuman_is', 'report_hired_fired'),
            },
            {
                'label': 'Отчеты - Воронка подбора',
                'path': ('applicants', 'funnel'),
            },
            {
                'label': 'Отчеты - Производительность подбора',
                'path': ('applicants', 'conveyor_report'),
            },
            {
                'label': 'Отчеты - Требующие линковки',
                'path': ('the_redhuman_is', 'workers_to_link_with_applicants'),
            },
            {
                'label': 'Отчеты - Города соискателей',
                'path': ('the_redhuman_is', 'report_applicants_cities'),
            },
            {
                'label': 'Отчеты - Своевременность обработки табелей',
                'path': ('the_redhuman_is', 'timesheet_timeliness'),
            },
            {
                'label': 'Отчеты - Распр-е рабочих по кол-ву выходов',
                'path': ('the_redhuman_is', 'reports_workers_count'),
            },
            {
                'label': 'Отчеты - Продолжительность жизни рабочих',
                'path': ('the_redhuman_is', 'reports_workers_lifetime'),
            },
            {
                # основным рабочим считается рабочий, у которого не менее Х выходов
                # на данном временном интервале
                'label': 'Отчеты - Распр-е основных рабочих по клиентам',
                'path': ('the_redhuman_is', 'reports_main_workers_distribution'),
            },
            {
                'label': 'Отчеты - Работники с депозитами',
                'path': ('the_redhuman_is', 'workers_with_deposits'),
            },
            {
                'label': 'Доставка - Ежедневные сверки',
                'path': ('the_redhuman_is', 'delivery_daily_reconciliations'),
                'rf_path': '/rf/delivery/calendar/',
                'key': 'daily_reconciliations',
            },
            {
                'label': 'Доставка - Выходы с расхождениями',
                'path': ('the_redhuman_is', 'delivery_turnouts_period_report'),
            },
            {
                'label': 'Доставка - Новые клиенты',
                'path': ('the_redhuman_is', 'delivery_new_customers_report'),
            },
            {
                'label': 'Доставка - Разное',
                'path': ('the_redhuman_is', 'delivery_other'),
            },
        ]
    },
]


def _full_menu():
    if is_app_flavor_master():
        return _FULL_MENU_COMMON + _FULL_MENU_EXTRA
    else:
        return _FULL_MENU_COMMON


def _is_page_allowed(user, groups, page):
    if user.is_superuser:
        return True

    if is_page_allowed(groups, page):
        return True

    return False


# Нам надо формировать меню для 2 пользователей:
# 1. keep_keys=False. Шаблон general_menu.html для джанго - туда не надо передавать key,
# надо брать rf_path, если он есть, если его нет - path
# 2. keep_keys=True. Запрос из нового фронтенда. Просто возвращать key как есть.
def menu_data(request, keep_keys=False):
    user_groups = list(request.user.groups.values_list('name', flat=True))

    menu = []

    def _url(path, suffix):
        app, name = path
        url = request.build_absolute_uri(reverse(f'{app}:{name}'))
        if suffix:
            url += suffix
        return url

    def _parse_item(item):
        path = item['path']
        if _is_page_allowed(request.user, user_groups, path):
            if keep_keys and 'key' in item:
                return {
                    'label': item['label'],
                    'key': item['key']
                }
            else:
                rf_path = item.get('rf_path')
                if rf_path:
                    url = request.build_absolute_uri(rf_path)
                else:
                    url = _url(path, item.get('path_suffix'))
                return {
                    'label': item['label'],
                    'url': url,
                }
        else:
            return None


    for top_menu_item in _full_menu():
        if 'path' in top_menu_item:
            item = _parse_item(top_menu_item)
            if item is not None:
                menu.append(item)

        elif 'items' in top_menu_item:
            items = []

            for menu_item in top_menu_item['items']:
                item = _parse_item(menu_item)
                if item is not None:
                    items.append(item)

            if len(items) > 0:
                menu.append(
                    {
                        'label': top_menu_item['label'],
                        'items': items,
                    }
                )

    return menu


@bo_api(['GET'])
def menu(request):
    return JsonResponse({'menu': menu_data(request, keep_keys=True)})
