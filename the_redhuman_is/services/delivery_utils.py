import datetime

from dataclasses import dataclass

from typing import (
    Any,
    List,
    Optional,
    Tuple,
)

from utils.date_time import as_default_timezone


# time slots packing

_first_slot = datetime.timedelta(hours=7, minutes=0)
_slot_duration = datetime.timedelta(minutes=30)
_slot_count = 34
slot_starts = [_first_slot + _slot_duration * i for i in range(_slot_count)]


def slot_index(timepoint: datetime.datetime) -> int:
    return (
        as_default_timezone(timepoint) - _first_slot - as_default_timezone(
            datetime.datetime.combine(
                timepoint.date(),
                datetime.time(0)
            )
        )
    ) // _slot_duration


def slots_indexes(
        start: datetime.datetime,
        finish: Optional[datetime.datetime]
) -> Tuple[int, int]:

    start_index = max(0, slot_index(start))
    if finish is not None:
        finish = max(start, finish)
        finish_index = min(
            max(0, slot_index(finish)) + (finish.date() - start.date()).days * _slot_count,
            _slot_count - 1
        )
    else:
        finish_index = start_index

    return start_index, finish_index


Interval = Tuple[datetime.datetime, Optional[datetime.datetime], Any]


@dataclass
class Item:
    start_index: int
    finish_index: int
    objects: List[Any]


def slots_chain(intervals: List[Interval]) -> List[Item]:
    chain = []
    for start, finish, obj in intervals:
        start_index, finish_index = slots_indexes(start, finish)
        if len(chain) == 0:
            if start_index > 0:
                chain.append(Item(0, start_index - 1, []))
        else:
            last_cell = chain[-1]
            if last_cell.finish_index >= finish_index:
                last_cell.objects.append(obj)
                continue
            else:
                if start_index > last_cell.finish_index + 1:
                    chain.append(Item(last_cell.finish_index + 1, start_index - 1, []))
                else:
                    start_index = max(start_index, last_cell.finish_index + 1)

        chain.append(Item(start_index, finish_index, [obj]))

    if len(chain) == 0:
        chain.append(Item(0, _slot_count - 1, []))
    else:
        last_cell = chain[-1]
        if last_cell.finish_index < _slot_count - 1:
            chain.append(Item(last_cell.finish_index + 1, _slot_count - 1, []))

    return chain
