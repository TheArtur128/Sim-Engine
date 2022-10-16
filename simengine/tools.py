from abc import ABC, abstractmethod, ABCMeta
from dataclasses import dataclass
from time import sleep, time, ctime
from threading import Thread
from typing import Iterable, Callable
from math import floor, copysign
from enum import IntEnum
from functools import wraps

from beautiful_repr import StylizedMixin, Field, TemplateFormatter

from simengine.interfaces import IUpdatable, ILoop, ILoopFactory
from simengine.errors.tool_errors import *


def get_collection_with_reduced_nesting_level_by(
    nesting_level: int,
    collection: Iterable
) -> list:
    is_reduced = False

    while not is_reduced and nesting_level > 0:
        new_collection = list()
        is_reduced = True

        for item in collection:
            if isinstance(item, Iterable):
                is_reduced = False
                new_collection.extend(item)
            else:
                new_collection.append(item)

        nesting_level -= 1
        collection = new_collection

    return collection


class IValueTransformer(ABC):
    @abstractmethod
    def __call__(self, attribute_keeper: object, original_value: any) -> any:
        pass


class ForwardableValueTransformer(IValueTransformer):
    def __call__(self, attribute_keeper: object, original_value: any) -> any:
        return original_value


class AttributesTransmitterMeta(ABCMeta):
    _attribute_names_to_parse: Iterable[str] | dict[str, IValueTransformer | None]
    _default_value_transformer: IValueTransformer = ForwardableValueTransformer()

    def __new__(cls, class_name: str, super_classes: tuple, attributes: dict):
        isinstance_type = super().__new__(cls, class_name, super_classes, attributes)

        isinstance_type._update_attribute_names()

        for attribute_name_to_parse in isinstance_type._deeply_get_attribute_names().keys():
            setattr(
                isinstance_type,
                attribute_name_to_parse,
                isinstance_type._parse_collection_by_attribute_name_from(
                    attributes,
                    attribute_name_to_parse
                )
            )

        return isinstance_type

    def _update_attribute_names(cls) -> None:
        if not isinstance(cls._attribute_names_to_parse, dict):
            cls._attribute_names_to_parse = dict.fromkeys(cls._attribute_names_to_parse)

        cls._attribute_names_to_parse = dict(
            item for parent_type in (*cls.__bases__, cls)
            if hasattr(parent_type, '_attribute_names_to_parse')
            for item in parent_type._attribute_names_to_parse.items()
        )

    def _deeply_get_attribute_names(cls) -> dict[str, Callable[[any], any]]:
        if '_deeply_attribute_names' in cls.__dict__:
            return cls._deeply_attribute_names

        parent_attribute_names = dict(get_collection_with_reduced_nesting_level_by(
            1,
            (
                parent_type._deeply_get_attribute_names().items()
                for parent_type in cls.__bases__
                if hasattr(parent_type, '_deeply_get_attribute_names')
            )
        ))

        result = parent_attribute_names | cls._attribute_names_to_parse
        cls._deeply_attribute_names = result

        return result

    def _parse_collection_by_attribute_name_from(cls, attributes: dict, attribute_name_to_parse: str) -> tuple:
        return (
            tuple(get_collection_with_reduced_nesting_level_by(
                1,
                (
                    getattr(parent_type, attribute_name_to_parse)
                    for parent_type in cls.__bases__
                    if hasattr(parent_type, attribute_name_to_parse)
                )
            ))
            + cls._get_collection_by_attribute_name_from(
                attribute_name_to_parse,
                is_changing=True
            )
        )

    def _get_collection_by_attribute_name_from(
        cls,
        attribute_name_to_parse: str,
        is_changing: bool = False
    ) -> tuple:
        value_getter = cls._deeply_get_attribute_names()[attribute_name_to_parse]

        return tuple(
            (value_getter if value_getter is not None else cls._default_value_transformer)(cls, item)
            for item in cls.__dict__.get(attribute_name_to_parse, tuple())
        )


class CreatingAttributesTransmitterMeta(AttributesTransmitterMeta):
    _default_value_transformer = lambda attribute_keeper, original_value: (
        original_value() if isinstance(original_value, CustomArgumentFactory)
        else original_value
    )


class SeparateThreadedLoop(ILoop):
    _thread_factory: Callable[[Callable], Thread] = Thread

    def __init__(self, loop: ILoop):
        self._loop = loop
        self._thread = self._thread_factory(target=loop.run)

    @property
    def thread(self) -> Thread:
        return self._thread

    def run(self) -> None:
        self._thread.start()

    def finish(self) -> None:
        self._loop.finish()
        self._thread.join()


class Loop(ILoop):
    _is_working = False

    def run(self) -> None:
        self._is_working = True

        while self._is_working:
            self._handle()

    def finish(self) -> None:
        self._is_working = False

    @abstractmethod
    def _handle(self) -> None:
        pass


class HandlerLoop(Loop, ABC):
    _handlers_factories: Iterable[Callable[['HandlerLoop'], 'LoopHandler']]

    def __init__(self):
        self.__handlers = tuple(
            handlers_factory(self)
            for handlers_factory in self._handlers_factories
        )

    @property
    def handlers(self) -> tuple['LoopHandler', ]:
        return self.__handlers

    def _handle(self) -> None:
        for handler in self.handlers:
            handler.update()


class StrictHandlerLoop(HandlerLoop, metaclass=AttributesTransmitterMeta):
    _attribute_names_to_parse = ('_handlers_factories', )


class CustomHandlerLoop(HandlerLoop):
    def __init__(self, handlers_factories: Iterable[Callable[['HandlerLoop'], 'LoopHandler']]):
        self._handlers_factories = handlers_factories
        super().__init__()


class LoopHandler(IUpdatable, ABC):
    def __init__(self, loop: HandlerLoop):
        self._loop = loop

    @property
    def loop(self) -> HandlerLoop:
        return self._loop


class UpdaterLoopHandler(LoopHandler):
    def __init__(self, loop: HandlerLoop, units: Iterable[IUpdatable]):
        self.units = tuple(units)

    def update(self) -> None:
        for unit in self.units:
            unit.update()


class SleepLoopHandler(LoopHandler, ABC):
    def update(self) -> None:
        self._handle_sleep_conditions()

        if self.is_ready_to_sleep():
            self._sleep()

    @abstractmethod
    def is_ready_to_sleep(self) -> bool:
        pass

    @abstractmethod
    def _handle_sleep_conditions(self) -> None:
        pass

    @abstractmethod
    def _sleep(self) -> None:
        pass


class AlwaysReadyForSleepLoopHandler(SleepLoopHandler):
    def is_ready_to_sleep(self) -> bool:
        return True

    def _handle_sleep_conditions(self) -> None:
        pass


class RollbackSleepLoopHandler(SleepLoopHandler):
    def update(self) -> None:
        super().update()

        if self.is_ready_to_sleep():
            self._sleep_rollback()

    @abstractmethod
    def _sleep_rollback(self) -> None:
        pass


class TicksSleepLoopHandler(SleepLoopHandler):
    _sleep_function: Callable[[int | float], any]

    def __init__(self, loop: HandlerLoop, ticks_to_sleep: int | float):
        super().__init__(loop)
        self.ticks_to_sleep = ticks_to_sleep

    def _sleep(self) -> None:
        self._sleep_function(self.ticks_to_sleep)


class CustomTicksSleepLoopHandler(TicksSleepLoopHandler):
    def __init__(
        self,
        loop: HandlerLoop,
        ticks_to_sleep: int | float,
        sleep_function: Callable[[int | float], None]
    ):
        self._sleep_function = sleep_function
        super().__init__(loop, ticks_to_sleep)


class TickerSleepLoopHandler(TicksSleepLoopHandler, RollbackSleepLoopHandler, ABC):
    _real_ticks_to_sleep: int | float = 0
    _tick: int | float = 1

    @property
    def real_ticks_to_sleep(self) -> int | float:
        return self._real_ticks_to_sleep

    @property
    def ticks_to_sleep(self) -> int | float:
        return self.__ticks_to_sleep

    @ticks_to_sleep.setter
    def ticks_to_sleep(self, ticks_to_sleep: int | float) -> None:
        if self._real_ticks_to_sleep > ticks_to_sleep:
            self._real_ticks_to_sleep = ticks_to_sleep

        self.__ticks_to_sleep = ticks_to_sleep

    def is_ready_to_sleep(self) -> bool:
        return self._real_ticks_to_sleep <= 0

    def _handle_sleep_conditions(self) -> None:
        self._real_ticks_to_sleep -= self._tick

    def _sleep_rollback(self) -> None:
        self._real_ticks_to_sleep = self.ticks_to_sleep



class DecoratorFactory(ABC):
    _decorator_factory: Callable[[Callable], any]
    _nested_factory: Callable

    def __call__(self, *args_for_nested_factory, **kwargs_for_nested_factory) -> any:
        return self._decorator_factory(
            self._nested_factory(
                *args_for_nested_factory,
                **kwargs_for_nested_factory
            )
        )


class CustomDecoratorFactory(DecoratorFactory):
    def __init__(self, decorator_factory: Callable, nested_factory: Callable):
        self._decorator_factory = decorator_factory
        self._nested_factory = nested_factory

    @property
    def decorator_factory(self) -> Callable[[Callable], any]:
        return self._decorator_factory

    @property
    def nested_factory(self) -> Callable:
        return self._nested_factory


class CustomArgumentFactory(ABC):
    factory: Callable
    is_stored_arguments_first: bool = False

    def __init__(self, *args_for_factory, **kwargs_for_factory):
        self.arguments_for_factory = Arguments.create_via_call(
            *args_for_factory,
            **kwargs_for_factory
        )

    def __call__(self, *args, **kwargs) -> any:
        argument_groups = [args, self.arguments_for_factory.args]

        if self.is_stored_arguments_first:
            argument_groups.reverse()

        return self.factory(
            *argument_groups[0],
            *argument_groups[1],
            **kwargs,
            **self.arguments_for_factory.kwargs
        )


class CustomFactory(CustomArgumentFactory):
    def __init__(
        self,
        factory: Callable,
        *args_for_factory,
        is_stored_arguments_first: bool = False,
        **kwargs_for_factory
    ):
        self.factory = factory
        self.is_stored_arguments_first = is_stored_arguments_first
        super().__init__(*args_for_factory, **kwargs_for_factory)


class CustomLoopFactory(CustomArgumentFactory, ILoopFactory):
    def __call__(self, units: Iterable[IUpdatable, ], *args, **kwargs) -> LoopUpdater:
        return super().__call__(units, *args, **kwargs)


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


class Timer(StylizedMixin):
    _repr_fields = (
        Field('period', value_transformer=lambda value: f"{value} second{'s' if value > 1 else ''}"),
        Field('end_time', value_transformer=ctime)
    )

    def __init__(self, seconds_of_period: int):
        self.period = seconds_of_period
        self._end_time = 0
        self.start()

    @property
    def end_time(self) -> float:
        return self._end_time

    def is_time_over(self) -> bool:
        return self._end_time <= time()

    def start(self):
        if not self.is_time_over():
            raise TimerError(f"Timer {self} has already started")

        self._end_time = time() + self.period
