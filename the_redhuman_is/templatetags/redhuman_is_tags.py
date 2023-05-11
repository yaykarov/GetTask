from django import template

register = template.Library()

RECON_STATUS = {
    'new': 'Новая',
    'confirmed': 'Согласована',
    'in_payment': 'В оплате',
    'paid': 'Оплачена',
}


@register.filter('recon_status')
def get_ru_recon_status(value):
    try:
        return RECON_STATUS[value]
    except KeyError:
        return '???'
