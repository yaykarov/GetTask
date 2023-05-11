import datetime

from django.test import SimpleTestCase

from the_redhuman_is.services.delivery_utils import (
    slot_index,
    slots_chain,
    slots_indexes,
)

from utils.date_time import as_default_timezone


def _timepoint(hour: int, minute: int, extra_days: int=0) -> datetime.datetime:
    return as_default_timezone(
        datetime.datetime(
            year=2021,
            month=10,
            day=1 + extra_days,
            hour=hour,
            minute=minute,
        )
    )


class TimeSlotsTest(SimpleTestCase):
    def test_0_index(self) -> None:
        self.assertEqual(slot_index(_timepoint(7, 00)), 0)
        self.assertEqual(slot_index(_timepoint(7, 19)), 0)

    def test_last_index(self) -> None:
        self.assertEqual(slot_index(_timepoint(23, 30)), 33)
        self.assertEqual(slot_index(_timepoint(23, 59)), 33)

    def test_index_pair(self) -> None:
        start, finish = slots_indexes(_timepoint(7, 00), _timepoint(6, 00))
        self.assertEqual(start, 0)
        self.assertEqual(finish, 0)

        start, finish = slots_indexes(_timepoint(11, 49), _timepoint(11, 55))
        self.assertEqual(start, 9)
        self.assertEqual(finish, 9)

        start, finish = slots_indexes(_timepoint(7, 31), _timepoint(6, 00, 1))
        self.assertEqual(start, 1)
        self.assertEqual(finish, 33)

        start, finish = slots_indexes(_timepoint(7, 31), _timepoint(8, 00, 1))
        self.assertEqual(start, 1)
        self.assertEqual(finish, 33)

    def test_empty_chain(self) -> None:
        chain = slots_chain([])
        self.assertEqual(len(chain), 1)
        self.assertEqual(chain[0].start_index, 0)
        self.assertEqual(chain[0].finish_index, 33)
        self.assertEqual(chain[0].objects, [])


    def _assert_item_equal(self, item, start_index, finish_index, objects):
        self.assertEqual(item.start_index, start_index)
        self.assertEqual(item.finish_index, finish_index)
        self.assertEqual(item.objects, objects)

    def test_long_chain(self) -> None:
        intervals = [
            (_timepoint(7, 31), None, 1),
            (_timepoint(10, 00), _timepoint(11, 59), 2),
            (_timepoint(11, 00), _timepoint(11, 30), 3),
            (_timepoint(11, 40), _timepoint(12, 30), 4),
        ]

        chain = slots_chain(intervals)
        self.assertEqual(len(chain), 6)

        def _assert(item_index, start_index, finish_index, objects):
            self._assert_item_equal(chain[item_index], start_index, finish_index, objects)

        _assert(0, 0, 0, [])
        _assert(1, 1, 1, [1])
        _assert(2, 2, 5, [])
        _assert(3, 6, 9, [2, 3])
        _assert(4, 10, 11, [4])
        _assert(5, 12, 33, [])
