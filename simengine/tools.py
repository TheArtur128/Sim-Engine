from abc import ABC, abstractmethod
from dataclasses import dataclass
from time import sleep
from typing import Iterable, Callable
from math import floor, copysign
from enum import IntEnum
from functools import wraps

from interfaces import IUpdatable, ILoop
from errors.tool_error import UnableToDivideError, ColorCoordinateError, AlphaChannelError


class LoopUpdater(ILoop):
    def __init__(self, unit: IUpdatable):
        self.unit = unit

    def run(self) -> None:
        while True:
            self._handle()

    def _handle(self) -> None:
        self.unit.update()


class StoppingLoopUpdater(LoopUpdater, ABC):
    def _handle(self) -> None:
        super()._handle()
        self._handle_stop()

    @abstractmethod
    def _handle_stop(self) -> None:
        self._stop()

    @abstractmethod
    def _stop(self) -> None:
        pass


class TickerLoopUpdater(StoppingLoopUpdater):
    _tick_factor: int | float = 1

    def __init__(self, unit: IUpdatable, ticks_to_timeout: int):
        super().__init__(unit)
        self._ticks_to_timeout = self._clock = ticks_to_timeout

    def _handle_stop(self) -> None:
        self._clock -= 1 * self._tick_factor

        if self._clock <= 0:
            self._clock = self._ticks_to_timeout
            self._stop()


class SleepLoopUpdater(TickerLoopUpdater):
    def __init__(self, unit: IUpdatable, ticks_to_timeout: int, sleep_seconds: int | float):
        super().__init__(unit, ticks_to_timeout)
        self.sleep_seconds = sleep_seconds

    def _stop(self) -> None:
        sleep(self.sleep_seconds)


class NumberRounder(ABC):
    def __call__(self, number: any) -> any:
        return self._round(number)

    @abstractmethod
    def _round(self, number: int | float) -> float:
        pass


class FastNumberRounder(NumberRounder):
    def _round(self, number: int | float) -> float:
        return floor(number)


class AccurateNumberRounder(NumberRounder):
    def _round(self, number: int | float) -> float:
        number_after_point = int(str(float(number)).split('.')[1][0])

        if number_after_point >= 5:
            return int(number) + copysign(1, number)
        else:
            return int(number)


class ProxyRounder(NumberRounder):
    def __init__(self, rounder: NumberRounder):
        self.rounder = rounder

    def _round(self, number: int | float) -> float:
        return self.rounder(number)


class ShiftNumberRounder(ProxyRounder):
    def __init__(self, rounder: NumberRounder, comma_shift: int):
        super().__init__(rounder)
        self.comma_shift = comma_shift

    def _round(self, number: int | float) -> float:
        return self.__move_point_in_number(
            super()._round(
                self.__move_point_in_number(number, self.comma_shift)
            ),
            -self.comma_shift
        )

    def __move_point_in_number(self, number: int | float, shift: int) -> float:
        letters_of_number = list(str(float(number)))
        point_index = letters_of_number.index('.')
        letters_of_number.pop(point_index)

        point_index += shift

        if point_index > len(letters_of_number):
            letters_of_number.extend(
                ('0' for _ in range(point_index - len(letters_of_number)))
            )
        elif point_index < 0:
            point_index = 0

        letters_of_number.insert(point_index, '.')

        return float(''.join(letters_of_number))


@dataclass
class Report:
    sign: bool
    message: str | None = None
    error: Exception | None = None

    def __bool__(self) -> bool:
        return self.sign

    @classmethod
    def create_error_report(cls, error: Exception) -> 'Report':
        return cls(
            False,
            error=error
        )


class ReportHandler(ABC):
    @abstractmethod
    def __call__(self, report: Report) -> None:
        pass

    def is_supported_report(self, report: Report) -> bool:
        return True


class BadReportHandler(ReportHandler):
    def __init__(
        self,
        default_error_type: type,
        default_error_message: str = ''
    ):
        self.default_error_type = default_error_type
        self.default_error_message = default_error_message

    def __call__(self, report: Report) -> None:
        if report.error:
            raise report.error

        raise self.default_error_type(
            report.message if report.message else self.default_error_message
        )

    def is_supported_report(self, report: Report) -> bool:
        return not report.sign


class ReportAnalyzer:
    def __init__(self, report_handlers: Iterable[ReportHandler, ]):
        self.report_handlers = frozenset(report_handlers)

    def __call__(self, report: Report) -> None:
        for report_handler in self.report_handlers:
            if report_handler.is_supported_report(report):
                report_handler(report)


class StrictToStateMixin(ABC):
    _report_analyzer: ReportAnalyzer

    @abstractmethod
    def _is_correct(self) -> Report:
        pass

    def _check_state_errors(self) -> None:
        self._report_analyzer(self._is_correct())


class Divider(ABC):
    _report_analyzer = ReportAnalyzer((BadReportHandler(UnableToDivideError), ))

    def __call__(self, data: any) -> None:
        self._report_analyzer(self.is_possible_to_divide(data))
        return self._divide(data)

    def is_possible_to_divide(self, data: any) -> Report:
        return Report(True)

    @abstractmethod
    def _divide(self, data: any) -> None:
        pass


class ComparisonResult(IntEnum):
    less = -1
    equals = 0
    more = 1


def compare(main: any, relatival: any) -> ComparisonResult:
    if main > relatival:
        return ComparisonResult.more
    elif main < relatival:
        return ComparisonResult.less
    else:
        return ComparisonResult.equals


@dataclass(frozen=True)
class RGBAColor:
    red: int = 0
    green: int = 0
    blue: int = 0
    alpha_channel: float = 1.

    def __post_init__(self) -> None:
        if any(
            not (0 <= color_coordinate <= 255)
            for color_coordinate in (self.red, self.green, self.blue)
        ):
            raise ColorCoordinateError(
                f"Color coordinate must be between 0 and 255"
            )
        elif not 0 <= self.alpha_channel <= 1:
            raise AlphaChannelError("Alpha channel must be between 0 and 1")

    def __iter__(self) -> iter:
        return iter((self.red, self.green, self.blue, self.alpha_channel))


@dataclass(frozen=True)
class Arguments:
    args: tuple
    kwargs: dict

    @classmethod
    def create_via_call(cls, *args, **kwargs) -> 'Arguments':
        return cls(args, kwargs)


def like_object(func: Callable) -> Callable:
    @wraps(func)
    def wrapper(*args, **kwargs) -> any:
        return func(func, *args, **kwargs)

    return wrapper
