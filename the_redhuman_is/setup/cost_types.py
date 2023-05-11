from the_redhuman_is.models import IndustrialCostType


STANDARD_INDUSTRIAL_COST_TYPES = [
    'Бригадиры',
    'Прочее',
]


def create_standard_cost_types():
    IndustrialCostType.objects.bulk_create(
        [IndustrialCostType(name=name) for name in STANDARD_INDUSTRIAL_COST_TYPES]
    )

