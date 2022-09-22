from abc import ABC, abstractmethod
from typing import Iterable, Callable, Optional

from interfaces import IUpdatable
from renders import IAvatar
from errors.core_errors import *
from geometry import Vector
from tools import ReportAnalyzer, BadReportHandler, Report, StrictToStateMixin


class ProcessState(IUpdatable, ABC):
    _report_analyzer = ReportAnalyzer((BadReportHandler(
        ProcessStateIsNotValidError,
        "Process state is not valid to update"
    ), ))

    def __init__(self, process: 'Process'):
        self.__process = process

    @property
    def process(self) -> 'Process':
        return self.__process

    @abstractmethod
    def get_next_state(self) -> Optional['ProcessState']:
        pass

    @abstractmethod
    def is_valid(self) -> Report:
        pass

    def update(self) -> None:
        self._report_analyzer(self.is_valid())
        self._handle()

    @abstractmethod
    def _handle(self) -> None:
        pass


class CompletedProcessState(ProcessState):
    def get_next_state(self) -> None:
        return None

    def is_valid(self) -> Report:
        return Report(True)

    def _handle(self) -> None:
        raise ProcessAlreadyCompletedError(
            f"Process {self.process} has completed its life cycle"
        )


class ActiveProcessState(ProcessState):
    def get_next_state(self) -> None:
        return None

    def is_valid(self) -> Report:
        return Report(True)

    def _handle(self) -> None:
        self.process._handle()


class SleepProcessState(ProcessState):
    def __init__(
        self,
        process: 'Process',
        ticks_to_activate: int | float,
        tick_factor: int | float = 1
    ):
        super().__init__(process)
        self.ticks_to_activate = ticks_to_activate
        self.tick = 1 * tick_factor

    def get_next_state(self) -> ProcessState:
        return ActiveProcessState(self.process)

    def is_valid(self) -> Report:
        return Report.create_error_report(
            ProcessIsNoLongerSleepingError(f"Process {self.process} no longer sleeps")
        ) if self.ticks_to_activate <= 0 else Report(True)

    def _handle(self) -> None:
        self.ticks_to_activate -= self.tick


class Process(StrictToStateMixin, IUpdatable, ABC):
    _report_analyzer = ReportAnalyzer((BadReportHandler(
        ProcessError,
        "Process is not valid"
    ), ))

    state = None

    def __init__(self):
        self._check_state_errors()

    @property
    @abstractmethod
    def participants(self) -> tuple:
        pass

    def start(self) -> None:
        self.state = ActiveProcessState(self)

    def update(self) -> None:
        if not self.state:
            self._start()

        while True:
            old_state = self.state
            self.__reset_state()

            if old_state is self.state:
                self._check_state_errors()
                self.state.update()
                break

    @classmethod
    def is_support_participants(cls, participants: Iterable) -> Report:
        return Report(True)

    @abstractmethod
    def _handle(self) -> None:
        pass

    def _is_correct(self) -> Report:
        return self.is_support_participants(self.participants)

    def __reset_state(self) -> None:
        next_state = self.state.get_next_state()

        if not self.state.is_valid() and next_state:
            self.state = next_state


class DelayedProcess(Process, ABC):
    _ticks_of_inactivity: int

    def activate_delay(self) -> None:
        self.state = SleepProcessState(self, self._ticks_of_inactivity)

    def _start(self) -> None:
        self.activate_delay()


class DependentUnit(IUpdatable, ABC):
    def __init__(self):
        self._processes = set()
        self.__completed_processes = list()

    @property
    def processes(self) -> frozenset[Process, ]:
        return frozenset(self._processes)

    @property
    def completed_processes(self) -> frozenset[Process, ]:
        return frozenset(self.__completed_processes)

    def add_process(self, process: Process) -> None:
        self._processes.add(process)

    def activate_processes(self) -> None:
        processes_to_update, self._processes = self._processes, set()

        for process in processes_to_update:
            if type(process.state) is CompletedProcessState:
                self.__completed_processes.append(process)
            else:
                self._processes.add(process)
                process.update()

    def clear_completed_processes(self) -> None:
        self.__completed_processes = list()


class InteractiveUnit(ABC):
    _report_analyzer = ReportAnalyzer((BadReportHandler(
        IncorrectUnitStateError,
        "Interactive unit state is incorrect"
    ), ))

    def interact_with(self, unit: IUpdatable) -> None:
        self._report_analyzer(self.is_support_interaction_with(unit))
        self._handle_interaction_with(unit)

    @abstractmethod
    def is_support_interaction_with(self, unit: IUpdatable) -> Report:
        pass

    @abstractmethod
    def _handle_interaction_with(self, unit: IUpdatable) -> None:
        pass


class MixinDiscrete(ABC):
    @property
    @abstractmethod
    def parts(self) -> frozenset[IUpdatable, ]:
        pass

    @property
    def deep_parts(self) -> frozenset[IUpdatable, ]:
        found_parts = set()

        for part in self.parts:
            found_parts.add(part)

            if hasattr(part, "deep_parts"):
                found_parts.update(part.deep_parts)

        return found_parts


class DiscreteUnit(MixinDiscrete, ABC):
    @property
    def parts(self) -> frozenset[IUpdatable, ]:
        return frozenset(self._parts)

    @abstractmethod
    def __create_parts__(self) -> Iterable[IUpdatable, ]:
        pass

    def init_parts(self, *args, **kwargs) -> None:
        self._parts = set(self.__create_parts__(*args, **kwargs))


class PositionalUnit(ABC):
    avatar_factory: Callable[['PositionalUnit'], IAvatar] = lambda unit: None

    def __init__(self, position: Vector):
        super().__init__()
        self.__position = self.__previous_position = position
        self._avatar = self.avatar_factory()

    @property
    def avatar(self) -> IAvatar:
        return self._avatar

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
    def __call__(self, units: Iterable[IUpdatable, ]) -> None:
        for unit in units:
            if self.is_unit_suitable(unit):
                raise UnsupportedUnitForHandlerError(f"Unit handler {self} unsupported unit {unit}")

        self._handle_units(units)

    def is_unit_suitable(self, unit: IUpdatable) -> bool:
        return isinstance(unit, IUpdatable)

    @abstractmethod
    def _handle_units(self, units: Iterable[IUpdatable, ]) -> None:
        pass


class FocusedUnitHandler(UnitHandler, ABC):
    def _handle_units(self, units: Iterable[IUpdatable, ]) -> None:
        for unit in units:
            self._handle_unit(unit)

    @abstractmethod
    def _handle_unit(self, unit: IUpdatable) -> None:
        pass


class UnitUpdater(FocusedUnitHandler):
    def _handle_unit(self, unit: IUpdatable) -> None:
        unit.update()


class UnitProcessesActivator(FocusedUnitHandler):
    def is_unit_suitable(self, unit: IUpdatable) -> bool:
        return super().is_unit_suitable(unit) and isinstance(unit, DependentUnit)

    def _handle_unit(self, unit: IUpdatable) -> None:
        unit.clear_completed_processes()
        unit.activate_processes()


class RenderResourceParser(FocusedUnitHandler):
    def __init__(self):
        super().__init__()
        self._parsed_resource_packs = list()

    @property
    def parsed_resource_packs(self) -> tuple:
        return tuple(self._parsed_resource_packs)

    def clear_parsed_resource_packs(self) -> None:
        self._parsed_resource_packs = list()

    def is_unit_suitable(self, unit: IUpdatable) -> bool:
        return (
            super().is_unit_suitable(unit) and
            isinstance(unit, PositionalUnit) and
            unit.avatar is not None
        )

    def _handle_unit(self, unit: IUpdatable) -> None:
        unit.avatar.update()
        self._parsed_resource_packs.extend(unit.avatar.render_resource_packs)


class UnitRelationsActivator(UnitHandler):
    def _handle_units(self, units: Iterable[IUpdatable, ]) -> None:
        for active_unit in units:
            if not isinstance(active_unit, InteractiveUnit):
                continue

            passive_units = set(units)
            passive_units.remove(active_unit)

            for passive_unit in passive_units:
                active_unit.interact_with(passive_unit)


class World(IUpdatable, MixinDiscrete, ABC):
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
    def parts(self) -> frozenset[IUpdatable, ]:
        return frozenset(self.__inhabitant)

    @property
    def unit_handlers(self) -> tuple[UnitHandler]:
        return self._unit_handlers

    def is_inhabited_for(self, inhabitant: IUpdatable) -> bool:
        return isinstance(inhabitant, IUpdatable)

    def add_inhabitant(self, inhabitant: IUpdatable) -> None:
        if not self.is_inhabited_for(inhabitant):
            raise NotSupportPartError(f"World {self} does not support {inhabitant}")

        self.__inhabitant.add(inhabitant)

    def remove_inhabitant(self, inhabitant: IUpdatable) -> None:
        self.__inhabitant.remove(inhabitant)

    def update(self) -> None:
        for unit_handler in self._unit_handlers:
            unit_handler(
                tuple(
                    unit for unit in self.deep_parts
                    if unit_handler.is_unit_suitable(unit)
                )
            )
