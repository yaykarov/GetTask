from the_redhuman_is.models import Service


STANDARD_SERVICES = [
    'Погрузка/разгрузка',
    'Комплектовка',
    'Подготовка и уборка',
    'Маркировка/стикеровка',
]


def create_standard_services():
    Service.objects.bulk_create(
        [Service(name=name) for name in STANDARD_SERVICES]
    )

