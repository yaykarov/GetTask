from django import template

from the_redhuman_is.views.backoffice_app.common import menu_data

register = template.Library()


@register.filter('menu')
def get_user_menu_data(request):
    return menu_data(request, keep_keys=False)
