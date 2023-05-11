from the_redhuman_is.models.worker import Position


STANDARD_POSITIONS = [
    'Бригадир',
    'Грузчик',
]


def create_standard_positions():
    Position.objects.bulk_create(
        [Position(name=name) for name in STANDARD_POSITIONS]
    )
