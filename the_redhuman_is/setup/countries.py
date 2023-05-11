from the_redhuman_is.models import Country


COUNTRIES = [
    'Белоруссия',
    'Казахстан',
    'Киргизия',
    'РФ',
    'Республика Армения',
    'Республика Молдова',
    'Таджикистан',
    'Узбекистан',
    'Украина',
]


def create_countries():
    Country.objects.bulk_create(
        [Country(name=name) for name in COUNTRIES]
    )
