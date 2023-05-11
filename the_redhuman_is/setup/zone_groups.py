from the_redhuman_is.models import ZoneGroup


ZONE_GROUPS = [
    ('arkhangelsk', 'Архангельск'),
    ('bataisk', 'Батайск'),
    ('belgorod', 'Белгород'),
    ('dmitrov', 'Дмитров'),
    ('kaliningrad', 'Калининград'),
    ('krasnodar', 'Краснодар'),
    ('kursk', 'Курск'),
    ('lipetsk', 'Липецк'),
    ('msk', 'Москва и МО'),
    ('nn', 'Нижний Новгород'),
    ('novosibirsk', 'Новосибирск'),
    ('omsk', 'Омск'),
    ('orel', 'Орёл'),
    ('perm', 'Пермь'),
    ('petrozavodsk', 'Петрозаводск'),
    ('rostov_on_don', 'Ростов-на-Дону'),
    ('ryazan', 'Рязань'),
    ('samara', 'Самара'),
    ('serpukhov', 'Серпухов'),
    ('severodvinsk', 'Северодвинск'),
    ('sochi', 'Сочи'),
    ('spb', 'Санкт-Петербург'),
    ('tyumen', 'Тюмень'),
    ('ufa', 'Уфа'),
    ('ulyanovsk', 'Ульяновск'),
    ('voronezh', 'Воронеж'),
    ('vyborg', 'Выборг'),
]


def create_zone_groups():
    ZoneGroup.objects.bulk_create(
        [
            ZoneGroup(code=code, name=name)
            for code, name in ZONE_GROUPS
        ]
    )
