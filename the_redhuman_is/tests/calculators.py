from copy import deepcopy
from datetime import (
    date,
    time,
    timedelta,
)
from decimal import Decimal

from django.test import SimpleTestCase

from the_redhuman_is.models.delivery import DeliveryRequest
from the_redhuman_is.models.turnout_calculators import (
    EstimateSumItem,
    EstimateSumRequest,
    calculate_delivery_request_hours,
    estimate_delivery_request_sum,
)
from utils.numbers import ZERO_OO


class EstimateSumTest(SimpleTestCase):
    BASE_TEST_DATA = EstimateSumRequest(
        hours=Decimal(4),
        zone='ufa_45',
        status=DeliveryRequest.COMPLETE,
        date=date(2021, 12, 17),
        items=[
            EstimateSumItem(
                mass=50.,
                has_elevator=True,
                floor=7,
                carrying_distance=20,
            )
        ]
    )
    BASE_RESULT = estimate_delivery_request_sum(BASE_TEST_DATA)

    def get_test_result(self, item_count=1, apply_to=1, **kwargs):
        case = deepcopy(self.BASE_TEST_DATA)
        for _ in range(1, item_count):
            case.items.append(deepcopy(case.items[0]))
        for k, v in kwargs.items():
            if k in EstimateSumItem.__slots__:
                for j in range(apply_to):
                    setattr(case.items[j], k, v)
            else:
                setattr(case, k, v)
        return estimate_delivery_request_sum(case)

    def test_msk_spb(self):
        per_hour = 200
        ufa_amount = 350
        ufa_hours = -2
        msk_spb_amount = 400
        msk_spb_hours = -3
        diff = msk_spb_amount - ufa_amount + (msk_spb_hours - ufa_hours) * per_hour

        for zone in ['msk_60+', 'spb_15']:
            self.assertEqual(
                self.BASE_RESULT + diff,
                self.get_test_result(zone=zone),
            )

    def test_adler_sochi_krasn(self):
        per_hour = 200
        ufa_amount = 350
        ufa_hours = -2
        sochi_amount = 250
        sochi_hours = -1
        diff = sochi_amount - ufa_amount + (sochi_hours - ufa_hours) * per_hour

        for zone in ['sochi_15', 'adler', 'krasnodar_60+']:
            self.assertEqual(
                self.BASE_RESULT + diff,
                self.get_test_result(zone=zone),
            )

    def test_regions(self):
        for zone in [
            'orel_15', 'ulyanovsk', 'vyborg_15', 'lipetsk_45', 'kaliningrad_45',
            'nn', 'nn_15', 'tyumen_60', 'perm_60+', 'bataisk_30', 'rostov_on_don_15',
            'ryazan_60', 'voronezh', 'belgorod_30', 'petrozavodsk', 'kursk_45', 'dmitrov_60+',
            'novosibirsk_60+', 'serpukhov', 'omsk_15',
        ]:
            self.assertEqual(
                self.BASE_RESULT,
                self.get_test_result(zone=zone),
            )

        samara_diff = 400 - 350
        self.assertEqual(
            self.BASE_RESULT + samara_diff,
            self.get_test_result(zone='samara_30'),
        )

    def test_regional_raise(self):
        raise_day = date(day=7, month=9, year=2021)
        raise_amount = 350 - 300

        self.assertEqual(
            self.BASE_RESULT - raise_amount,
            self.get_test_result(date=raise_day - timedelta(days=1)),
        )

    def test_samara_raise(self):
        raise_day_1 = date(day=7, month=9, year=2021)
        raise_amount_1 = 400 - 300
        raise_day_2 = date(day=19, month=11, year=2021)
        raise_amount_2 = 400 - 350

        samara_result = self.get_test_result(zone='samara_30')

        self.assertEqual(
            samara_result - raise_amount_1,
            self.get_test_result(zone='samara_30', date=raise_day_1 - timedelta(days=1)),
        )
        self.assertEqual(
            samara_result - raise_amount_2,
            self.get_test_result(zone='samara_30', date=raise_day_2 - timedelta(days=1)),
        )

    def test_sochi_no_raise(self):
        raise_day = date(day=7, month=9, year=2021)
        for zone in ['sochi_15', 'adler', 'krasnodar_60+']:
            self.assertEqual(
                self.get_test_result(zone=zone),
                self.get_test_result(zone=zone, date=raise_day - timedelta(days=1)),
            )

    def test_moscow_onetime_bonus(self):
        magic_day = date(day=28, month=6, year=2021)
        bonus = 200

        self.assertEqual(
            self.get_test_result(zone='msk_15'),
            self.get_test_result(zone='msk', date=magic_day - timedelta(days=1)),
        )
        self.assertEqual(
            self.get_test_result(zone='msk_15', date=magic_day + timedelta(days=1)),
            self.get_test_result(zone='msk', date=magic_day - timedelta(days=1)),
        )
        self.assertEqual(
            self.get_test_result(zone='msk_15') + bonus,
            self.get_test_result(zone='msk', date=magic_day),
        )

    def test_hours(self):
        ufa_hours = -2
        per_hour = 200

        for hours in range(0, 10):
            diff = per_hour * (
                max(hours + ufa_hours, ZERO_OO) -
                max(self.BASE_TEST_DATA.hours + ufa_hours, ZERO_OO)
            )
            self.assertEqual(
                self.BASE_RESULT + diff,
                self.get_test_result(hours=hours),
            )

    def test_not_negative(self):
        self.assertGreaterEqual(
            self.get_test_result(hours=0),
            0,
        )

    def test_heavy(self):
        mass_bonus = 200

        self.assertEqual(
            self.BASE_RESULT + mass_bonus,
            self.get_test_result(mass=500),
        )
        # Todo: figure out wtf is this
        # self.assertEqual(
        #     self.BASE_RESULT + mass_bonus,
        #     self.get_test_result(mass=500, status=DeliveryRequest.CANCELLED_WITH_PAYMENT),
        # )
        self.assertEqual(
            self.get_test_result(zone='adler'),
            self.get_test_result(zone='adler', mass=500),
        )
        self.assertEqual(
            self.get_test_result(mass=1000, item_count=2),
            self.get_test_result(item_count=2),
        )

    def test_no_elevator(self):
        bonus = 50
        elevator_min = 4
        elevator_max = 15

        self.assertEqual(
            self.BASE_RESULT,
            self.get_test_result(has_elevator=None),
        )
        self.assertEqual(
            self.BASE_RESULT,
            self.get_test_result(has_elevator=False, floor=None),
        )
        self.assertEqual(
            self.BASE_RESULT + (self.BASE_TEST_DATA.items[0].floor - elevator_min) * bonus,
            self.get_test_result(has_elevator=False),
        )
        self.assertEqual(
            self.get_test_result(has_elevator=False, floor=-10),
            self.get_test_result(has_elevator=False, floor=elevator_min),
        )
        self.assertEqual(
            self.get_test_result(has_elevator=False, floor=elevator_max),
            self.get_test_result(has_elevator=False, floor=1000),
        )

    def test_distance(self):
        bonus = 50
        distance_max = 250

        self.assertEqual(
            self.BASE_RESULT,
            self.get_test_result(carrying_distance=None),
        )
        self.assertEqual(
            self.get_test_result(carrying_distance=70) + bonus * 2,
            self.get_test_result(carrying_distance=170)
        )
        self.assertEqual(
            self.BASE_RESULT,
            self.get_test_result(carrying_distance=70)
        )
        self.assertEqual(
            self.get_test_result(carrying_distance=distance_max),
            self.get_test_result(carrying_distance=100000000),
        )

    def test_route_bonus(self):
        ufa_route_bonus = 150
        msk_route_bonus = 200

        self.assertEqual(
            self.BASE_RESULT + ufa_route_bonus,
            self.get_test_result(item_count=2),
        )
        self.assertEqual(
            self.get_test_result(zone='msk_15') + msk_route_bonus,
            self.get_test_result(zone='msk_30', item_count=2),
        )
        self.assertEqual(
            self.BASE_RESULT,
            self.get_test_result(status=DeliveryRequest.CANCELLED_WITH_PAYMENT),
        )

    def test_elevator_distance_route(self):
        ufa_route_bonus = 150
        elevator_diff = self.get_test_result(has_elevator=False) - self.BASE_RESULT
        distance_diff = self.get_test_result(carrying_distance=10000) - self.BASE_RESULT
        both_diff = (
            self.get_test_result(carrying_distance=10000, has_elevator=False) -
            self.BASE_RESULT
        )

        for item_count in range(2, 5):
            for apply_to in range(0, item_count + 1):
                self.assertEqual(
                    self.BASE_RESULT + apply_to * elevator_diff + ufa_route_bonus,
                    self.get_test_result(
                        has_elevator=False,
                        item_count=item_count,
                        apply_to=apply_to,
                    )
                )
                self.assertEqual(
                    self.BASE_RESULT + apply_to * distance_diff + ufa_route_bonus,
                    self.get_test_result(
                        carrying_distance=10000,
                        apply_to=apply_to,
                        item_count=item_count,
                    )
                )
                self.assertEqual(
                    self.BASE_RESULT + apply_to * both_diff + ufa_route_bonus,
                    self.get_test_result(
                        has_elevator=False,
                        carrying_distance=10000,
                        item_count=item_count,
                        apply_to=apply_to,
                    )
                )


class CalculateHoursTest(SimpleTestCase):
    NIGHT_SURCHARGE = 2
    day_start = time(7, 0)
    night_start = time(22, 0)

    def test_daytime(self):
        self.assertSequenceEqual(
            calculate_delivery_request_hours(7, 4, time(10, 0)),
            (3, 4, 0),
        )
        self.assertSequenceEqual(
            calculate_delivery_request_hours(7, 4, time(7, 0)),
            (3, 4, 0),
        )
        self.assertSequenceEqual(
            calculate_delivery_request_hours(7, 4, time(21, 59)),
            (3, 4, 0),
        )

    def test_night(self):
        self.assertEqual(
            calculate_delivery_request_hours(7, 4, time(22, 0)),
            (3, 4, 2),
        )
        self.assertEqual(
            calculate_delivery_request_hours(7, 4, time(23, 59)),
            (3, 4, 2),
        )
        self.assertEqual(
            calculate_delivery_request_hours(7, 4, time(0, 0)),
            (3, 4, 2),
        )
        self.assertEqual(
            calculate_delivery_request_hours(7, 4, time(0, 1)),
            (3, 4, 2),
        )

    def test_min_hours_exceeded(self):
        self.assertEqual(
            calculate_delivery_request_hours(7, 4, time(10, 0), base_hours=Decimal(9)),
            (9, 4, 0),
        )

    def test_less_than_min_hours(self):
        self.assertEqual(
            calculate_delivery_request_hours(7, 4, time(10, 0), base_hours=Decimal(1)),
            (3, 4, 0),
        )

    def test_min_hours_exact(self):
        self.assertEqual(
            calculate_delivery_request_hours(7, 4, time(10, 0), base_hours=Decimal(3)),
            (3, 4, 0),
        )
