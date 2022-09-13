from time import sleep
from typing import Iterable
from math import ceil

from interfaces import IUpdatable


class LoopUpdater:
    def __init__(self, updated_object: IUpdatable, timeout: int = 0):
        self.updated_object = updated_object
        self.timeout = timeout

    def run(self) -> None:
        while True:
            self.updated_object.update()

            if self.timeout > 0:
                sleep(self.timeout)


def round_number_with_comma_shift(number: int | float, comma_shift: int) -> float:
    return _move_point_in_number(
        round(_move_point_in_number(number, comma_shift)),
        -comma_shift
    )


def round(number: int | float) -> float:
    number_after_point = int(str(float(number)).split('.')[1][0])

    if number_after_point >= 5:
        return int(number) + 1
    else:
        return int(number)


def _move_point_in_number(number: int | float, shift: int) -> float: # Will be redone
    letters_of_number = list(str(float(number)))
    point_index = letters_of_number.index('.')
    letters_of_number.pop(point_index)

    point_index += shift

    if point_index > len(letters_of_number):
        point_index = len(letters_of_number)
    elif point_index < 0:
        point_index = 0

    letters_of_number.insert(point_index, '.')

    return float(''.join(letters_of_number))
