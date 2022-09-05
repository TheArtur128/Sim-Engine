from abc import ABC, abstractmethod
from typing import Iterable, Callable
from enum import Enum, auto

from interfaces import IProcess, IUpdatable, IAvatar
from errors.core_errors import *
from tools import SpawnContainer
from physics import Vector


class ProcessState(Enum):
    active = auto()
    sleep = auto()
    completed = auto()


class Process(IUpdatable, ABC):
    __ticks_to_activate = 0

    def __new__(cls, *args, **kwargs):
        instance = super().__new__(cls)
        instance._start()

        return instance

    @property
    def state(self) -> ProcessState:
        return self._state

    @property
    def ticks_to_activate(self) -> int:
        return self.__ticks_to_activate

    def sleep(self, ticks: int) -> None:
        self._state = ProcessState.sleep
        self.__ticks_to_activate += ticks

    def update(self) -> None:
        if self._state is ProcessState.sleep:
            self.__ticks_to_activate -= 1

        if self.__ticks_to_activate <= 0:
            self._state = ProcessState.active

        if self._state is ProcessState.active:
            self._handle()

    @abstractmethod
    def _handle(self) -> None:
        pass

    def _start(self) -> None:
        self._state = ProcessState.active


class Event(Process, ABC):
    pass


class Effect(Process, ABC):
    def __init__(self, subject: object):
        self.__subject = subject

    @property
    def subject(self) -> object:
        return self.__subject


class Action(Process, ABC):
    def __init__(self, initiator: object):
        self.__initiator = initiator

    @property
    def initiator(self) -> object:
        return self.__initiator


class Unit(IUpdatable, ABC):
    __action = None

    def __init__(self):
        self.effects = set()
        self.__previous_actions = list()

    @property
    def previous_actions(self) -> tuple:
        return tuple(self.__previous_actions)

    @property
    def action(self) -> Action | None:
        return self.__action

    @action.setter
    def action(self, action: Action) -> None:
        if not self.action.state is ProcessState.completed:
            raise ForcedReplacementOfActionError(
                f"Replacing the still active action {self.action} with another action {action}"
            )

        self.__previous_actions.append(self.__action)
        self.__action = action

    def clear_previous_actions(self) -> None:
        self.__previous_actions = list()


class MixinDiscrete(ABC):
    @property
    @abstractmethod
    def parts(self) -> frozenset:
        pass

    @property
    def deep_parts(self) -> frozenset:
        found_parts = set()

        for part in self.parts:
            found_parts.add(part)

            if hasattr(part, "deep_parts"):
                found_parts.update(part.deep_parts)

        return found_parts


class DiscreteUnit(Unit, MixinDiscrete, ABC):
    def __init__(self, *args_for_part_init, **kwargs_for_part_init):
        super().__init__()
        self.__init_parts__(*args_for_part_init, **kwargs_for_part_init)

    @abstractmethod
    def __init_parts__(self) -> None:
        pass


class PositionalUnit(Unit, ABC):
    avatar_factory: Callable[[Unit], IAvatar] = lambda unit: None

    def __init__(self, position: Vector):
        super().__init__()
        self.__position = self.__previous_position = position
        self.avatar = self.avatar_factory()

    @property
    def position(self) -> Vector:
        return self.__position

    @property
    def previous_position(self) -> Vector:
        return self.__previous_position

    @property
    @abstractmethod
    def next_position(self) -> Vector:
        pass

    def move(self) -> None:
        self.__previous_position = self.__position
        self.__position = self.next_position


class UnitHandler(ABC):
    def __call__(self, units: Iterable[Unit, ]) -> None:
        for unit in units:
            if self.is_unit_suitable(unit):
                raise UnsupportedUnitForHandlerError(f"Unit handler {self} unsupported unit {unit}")

        self._handle_units(units)

    def is_unit_suitable(self, unit: Unit) -> bool:
        return isinstance(unit, Unit)

    @abstractmethod
    def _handle_units(self, units: Iterable[Unit, ]) -> None:
        pass


class FocusedUnitHandler(UnitHandler, ABC):
    def _handle_units(self, units: Iterable[Unit, ]) -> None:
        for unit in units:
            self._handle_unit(unit)

    @abstractmethod
    def _handle_unit(self, unit: Unit) -> None:
        pass


class UnitUpdater(FocusedUnitHandler):
    def _handle_unit(self, unit: Unit) -> None:
        unit.update()


class UnitActionActivator(FocusedUnitHandler):
    def is_unit_suitable(self, unit: Unit) -> bool:
        return super().is_unit_suitable(unit) and unit.action

    def _handle_unit(self, unit: Unit) -> None:
        unit.action.update()


class UnitEffectsActivator(FocusedUnitHandler):
    def _handle_unit(self, unit: Unit) -> None:
        for effect in unit.effects:
            effect.update()


class RenderResourceParser(FocusedUnitHandler):
    def __init__(self):
        super().__init__()
        self._parsed_render_resources = list()

    @property
    def parsed_render_resources(self) -> tuple:
        return tuple(self._parsed_render_resources)

    def clear_parsed_render_resources(self) -> None:
        self._parsed_render_resources = list()

    def is_unit_suitable(self, unit: Unit) -> bool:
        return (
            super().is_unit_suitable(unit) and
            isinstance(unit, PositionalUnit) and
            unit.avatar is not None
        )

    def _handle_unit(self, unit: Unit) -> None:
        unit.avatar.update()
        self._parsed_render_resources.append(unit.avatar.render_resource)


class World(Unit, MixinDiscrete, ABC):
    _unit_handler_factories: Iterable[Callable[[], UnitHandler], ]

    def __init__(self, inhabitants: Iterable):
        self.__inhabitant = set()
        self._unit_handlers = tuple(
            unit_handler_factory()
            for unit_handler_factory in self._unit_handler_factories
        )

        for inhabitant in inhabitants:
            self.add_inhabitant(inhabitant)

    @property
    def parts(self) -> frozenset:
        return frozenset(self.__inhabitant)

    @property
    def unit_handlers(self) -> tuple[UnitHandler]:
        return self._unit_handlers

    def is_inhabited_for(self, inhabitant: object) -> bool:
        return isinstance(inhabitant, Unit)

    def add_inhabitant(self, inhabitant: object) -> None:
        if not self.is_inhabited_for(inhabitant):
            raise NotSupportPartError(f"World {self} does not support {inhabitant}")

        self.__inhabitant.add(inhabitant)

    def remove_inhabitant(self, inhabitant: object) -> None:
        self.__inhabitant.remove(inhabitant)

    def update(self) -> None:
        for unit_handler in self._unit_handlers:
            self.__use_unit_handler(unit_handler)

    def __use_unit_handler(self, handler: UnitHandler) -> None:
        unit_handler(
            filter(
                lambda unit: unit_handler.is_unit_suitable(unit),
                self.deep_parts
            )
        )
