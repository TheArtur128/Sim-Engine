from abc import ABC, abstractmethod
from typing import Iterable, Callable, Optional, Self

from beautiful_repr import StylizedMixin, Field

from simengine.interfaces import *
from simengine.renders import ResourcePack, RenderActivator, IRender
from simengine.errors.core_errors import *
from simengine.tools import *
from simengine.geometry import Vector, Figure, Site, DynamicTransporter


class IProcessState(IUpdatable, ABC):
    @property
    def process(self) -> 'Process':
        pass

    @abstractmethod
    def get_next_state(self) -> Optional[Self]:
        pass

    @abstractmethod
    def is_compelling_to_handle(self) -> bool:
        pass

    @abstractmethod
    def is_valid(self) -> Report:
        pass

    @abstractmethod
    def update(self) -> None:
        pass


class ProcessState(IProcessState, ABC):
    _report_analyzer = ReportAnalyzer((BadReportHandler(
        ProcessStateIsNotValidError,
        "Process state is not valid to update"
    ), ))

    def __init__(self, process: 'Process'):
        self.__process = process

    def __hash__(self) -> int:
        return id(self.__class__)

    @property
    def process(self) -> 'Process':
        return self.__process

    def update(self) -> None:
        self._report_analyzer(self.is_valid())
        self._handle()

    @abstractmethod
    def _handle(self) -> None:
        pass


class CompletedProcessState(ProcessState):
    is_compelling_to_handle = False

    def get_next_state(self) -> None:
        return None

    def is_valid(self) -> Report:
        return Report(True)

    def _handle(self) -> None:
        raise ProcessAlreadyCompletedError(
            f"Process {self.process} has completed its life cycle"
        )


class ActiveProcessState(ProcessState):
    is_compelling_to_handle = True

    def get_next_state(self) -> None:
        return None

    def is_valid(self) -> Report:
        return Report(True)

    def _handle(self) -> None:
        pass


class NewStateByValidationProcessStateMixin(IProcessState, ABC):
    _new_state_factory: Callable[['Process'], ProcessState | None] = CustomFactory(ActiveProcessState)

    def get_next_state(self) -> ProcessState | None:
        return self._new_state_factory(self.process) if self.is_valid() else None


class SleepProcessState(ProcessState, NewStateByValidationProcessStateMixin):
    is_compelling_to_handle = False

    def __init__(
        self,
        process: 'Process',
        ticks_to_activate: int | float,
        tick_factor: int | float = 1
    ):
        super().__init__(process)
        self.ticks_to_activate = ticks_to_activate
        self.tick = 1 * tick_factor

    def __hash__(self) -> int:
        return id(self)

    def is_valid(self) -> Report:
        return Report.create_error_report(
            ProcessIsNoLongerSleepingError(f"Process {self.process} no longer sleeps")
        ) if self.ticks_to_activate <= 0 else Report(True)

    def _handle(self) -> None:
        self.ticks_to_activate -= self.tick


class FlagProcessState(ProcessState, NewStateByValidationProcessStateMixin):
    is_compelling_to_handle = True
    _is_standing: bool = False

    def is_valid(self) -> Report:
        return Report(self._is_standing)

    def update(self) -> None:
        pass


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
            self.start()

        self.state.update()

        if self.state.is_compelling_to_handle:
            self._handle()

        while True:
            old_state = self.state
            self.__reset_state()

            if hash(old_state) == hash(self.state):
                break

    @classmethod
    def is_support_participants(cls, participants: Iterable) -> Report:
        return Report(True)

    @abstractmethod
    def _handle(self) -> None:
        pass

    @abstractmethod
    def _get_next_state(self) -> ProcessState | None:
        pass

    def _is_correct(self) -> Report:
        return self.is_support_participants(self.participants)

    def __reset_state(self) -> None:
        next_state = self.state.get_next_state()

        if next_state is None:
            next_state = self._get_next_state()

        if next_state:
            self.state = next_state


class ManyPassProcess(Process, ABC):
    _passes: int

    def update(self) -> None:
        self._passes -= 1
        super().update()

    def _get_next_state(self) -> ProcessState | None:
        return CompletedProcessState(self) if self._passes <= 0 else None


class WorldProcess(Process, ABC):
    world: Optional['World'] = None

    def start(self) -> None:
        if not self.world:
            raise WorldProcessError(f"World process {self} has no world")

        super().start()


class Event(Process, ABC):
    def __init__(self, participants: Iterable[IUpdatable, ]):
        self.__participants = tuple(participants)
        super().__init__()

    @property
    def participants(self) -> tuple:
        return self.__participants


class FocusedEvent(Event, ABC):
    def _handle(self) -> None:
        for participant in self.participants:
            self._handle_participant(participant)

    @abstractmethod
    def _handle_participant(self, participant: IUpdatable) -> None:
        pass


class UnitSpawnProcess(FocusedEvent, WorldProcess, ManyPassProcess):
    _passes = 1

    def _handle_participant(self, participant: IUpdatable) -> None:
        self.world.add_inhabitant(participant)


class UnitKillProcess(FocusedEvent, WorldProcess, ManyPassProcess):
    _passes = 1

    def _handle_participant(self, participant: IUpdatable) -> None:
        self.world.remove_inhabitant(participant)


class DelayedProcess(Process, ABC):
    _ticks_of_inactivity: int

    def start(self) -> None:
        self.activate_delay()

    def activate_delay(self) -> None:
        self.state = SleepProcessState(self, self._ticks_of_inactivity)


class CustomBilateralProcessFactory(IBilateralProcessFactory, ABC):
    def __init__(self, process_type: type):
        self._process_type = process_type

    @property
    def process_type(self) -> type:
        return self._process_type

    def __call__(self, active_unit: IUpdatable, passive_unit: IUpdatable) -> Process:
        return self.process_type(active_unit, passive_unit)


class IProcessKeeper(ABC):
    @property
    @abstractmethod
    def processes(self) -> frozenset[Process, ]:
        pass

    @property
    @abstractmethod
    def completed_processes(self) -> frozenset[Process, ]:
        pass

    @abstractmethod
    def add_process(self, process: Process) -> None:
        pass

    @abstractmethod
    def remove_process(self, process: Process) -> None:
        pass

    @abstractmethod
    def activate_processes(self) -> None:
        pass

    @abstractmethod
    def clear_completed_processes(self) -> None:
        pass


class ProcessKeeper(IProcessKeeper, ABC):
    _process_adding_report_analyzer = ReportAnalyzer((BadReportHandler(
        UnsupportedProcessError,
        "Process keeper unsupported process"
    ), ))

    def __init__(self):
        self._processes = set()
        self.__completed_processes = list()

    @property
    def processes(self) -> frozenset[Process, ]:
        return frozenset(self._processes)

    @property
    def completed_processes(self) -> frozenset[Process, ]:
        return frozenset(self.__completed_processes)

    def is_support_process(self, process: Process) -> Report:
        return Report(isinstance(process, Process))

    def add_process(self, process: Process) -> None:
        self._process_adding_report_analyzer(self.is_support_process(process))
        self._processes.add(process)

    def remove_process(self, process: Process) -> None:
        self._processes.remove(process)

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


class MultitaskingUnit(ProcessKeeper, IUpdatable, ABC):
    pass


class InteractiveUnit(IUpdatable, ABC):
    _interaction_report_analyzer = ReportAnalyzer((BadReportHandler(
        UnitRelationError,
        "Unit can't interact"
    ), ))

    def interact_with(self, unit: IUpdatable) -> None:
        self._interaction_report_analyzer(self.is_support_interaction_with(unit))
        self._handle_interaction_with(unit)

    @abstractmethod
    def is_support_interaction_with(self, unit: IUpdatable) -> Report:
        pass

    @abstractmethod
    def _handle_interaction_with(self, unit: IUpdatable) -> None:
        pass


class ProcessInteractiveUnit(InteractiveUnit, MultitaskingUnit, ABC):
    _bilateral_process_factories: Iterable[IBilateralProcessFactory | type, ]
    __cash_factories_for_object: tuple[object, tuple[IBilateralProcessFactory, ]] = (object(), tuple())

    def is_support_interaction_with(self, unit: IUpdatable) -> Report:
        return (
            Report(True) if self.__get_cachedly_suported_process_factories_for(unit)
            else Report.create_error_report(
                IncorrectUnitInteractionError("No possible processes to occur")
            )
        )

    def _handle_interaction_with(self, unit: IUpdatable) -> None:
        for factory in self.__get_cachedly_suported_process_factories_for(unit):
            process = factory(self, unit)
            process.start()

            self.add_process(process)

    def __get_cachedly_suported_process_factories_for(self, unit: IUpdatable) -> tuple[IBilateralProcessFactory, ]:
        if unit is self.__cash_factories_for_object[0]:
            return self.__cash_factories_for_object[1]

        factories = tuple(
            (
                factory.process_type if hasattr(factory, 'process_type') else factory
            ).is_support_participants((self, unit))
            for factory in self._bilateral_process_factories
        )
        self.__cash_factories_for_object = (unit, factories)

        return factories


class DependentUnit(IUpdatable, ABC):
    master: IUpdatable | None = None


class PartUnit(DependentUnit, StrictToStateMixin, StylizedMixin, ABC):
    _repr_fields = (Field("master"), )

    def _is_correct(self) -> Report:
        return Report(True) if self.master is not None else Report.create_error_report(
            UnitPartError(f"Part unit {self} must have a master")
        )


class MixinDiscrete(IDiscretable, ABC):
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


class DiscreteUnit(MixinDiscrete, IUpdatable, ABC):
    @property
    def parts(self) -> frozenset[DependentUnit, ]:
        return frozenset(self._parts)

    @abstractmethod
    def __create_parts__(self) -> Iterable[DependentUnit, ]:
        pass

    def init_parts(self, *args, **kwargs) -> None:
        self._parts = set()

        for part in self.__create_parts__(*args, **kwargs):
            self._add_part(part)

    def _add_part(self, part: DependentUnit) -> None:
        part.master = self
        self._parts.add(part)

    def _remove_part(self, part: DependentUnit) -> None:
        part.master = None
        self._parts.remove(part)


class AnyPartMixin:
    def __create_parts__(self, *parts) -> Iterable[IUpdatable, ]:
        return parts


class TactileUnit(IUpdatable, ABC):
    _zone_factory: IZoneFactory

    def __init__(self):
        self._zone = self._zone_factory(self)

    @property
    def zone(self) -> Figure:
        return self._zone


class PositionalUnit(TactileUnit, StylizedMixin, ABC):
    _repr_fields = (Field('position'), )
    _zone_factory = CustomFactory(lambda unit: Site(unit.position))

    _avatar_factory: IAvatarFactory = CustomFactory(lambda unit: None)

    def __init__(self, position: Vector):
        self._position = position
        super().__init__()

        self._avatar = self._avatar_factory(self)

    @property
    def avatar(self) -> IAvatar | None:
        return self._avatar

    @property
    def position(self) -> Vector:
        return self._position


class MovableUnit(PositionalUnit, IMovable, ABC):
    def __init__(self, position: Vector):
        super().__init__(position)
        self.__previous_position = self.position

    @property
    def previous_position(self) -> Vector:
        return self.__previous_position

    @property
    @abstractmethod
    def next_position(self) -> Vector:
        pass

    def move(self) -> None:
        self.__previous_position = self._position
        self._position = self.next_position

        self._update_zone_position()

    def _update_zone_position(self) -> None:
        self._zone.move_by(DynamicTransporter(self.position - self.previous_position))


class MovingProcess(Process):
    def __init__(self, movable_unit: 'ProcessMovableUnit'):
        self._movable_unit = movable_unit

    @property
    def movable_unit(self) -> 'ProcessMovableUnit':
        return self._movable_unit

    @property
    @abstractmethod
    def next_unit_position(self) -> Vector:
        pass


class UnitMovingProcessState(FlagProcessState):
    pass


class ProcessMovableUnit(MovableUnit):
    _moving_process_factory: Callable[[Self], MovingProcess]

    def __init__(self, position: Vector):
        super().__init__(position)
        self._moving_process = self._moving_process_factory(self)

    @property
    def moving_process(self) -> MovingProcess:
        return self._moving_process

    @property
    def next_position(self) -> Vector:
        return self._moving_process.next_unit_position

class ImpulseUnit(InfinitelyImpulseUnit):
    def move(self) -> None:
        super().move()
        self._moving_process.state = UnitMovingProcessState(self._moving_process)


class DirectedMovingProcess(MovingProcess):
    def __init__(self, movable_unit: ProcessMovableUnit):
        super().__init__(movable_unit)
        self.vector_to_next_unit_position = Vector()

    @property
    def next_unit_position(self) -> Vector:
        return self.movable_unit.position + self.vector_to_next_unit_position




class UnitHandler(ABC):
    _report_analyzer = ReportAnalyzer((BadReportHandler(
        UnsupportedUnitForHandlerError,
        "Unit handler can't handle unit"
    ), ))

    def __init__(self, world: 'World'):
        self.world = world

    def __call__(self, units: Iterable[IUpdatable, ]) -> None:
        for unit in units:
            self._report_analyzer(self.is_unit_suitable(unit))

        self._handle_units(units)

    def is_unit_suitable(self, unit: IUpdatable) -> Report:
        return Report(isinstance(unit, IUpdatable))

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


class ProcessKeeperHandler(UnitHandler):
    def is_unit_suitable(self, unit: IUpdatable) -> Report:
        return super().is_unit_suitable(unit) and Report(isinstance(unit, ProcessKeeper))


class UnitProcessesActivator(FocusedUnitHandler, ProcessKeeperHandler):
    def _handle_unit(self, unit: IUpdatable) -> None:
        unit.clear_completed_processes()
        unit.activate_processes()


class WorldProcessesActivator(ProcessKeeper, ProcessKeeperHandler):
    def __init__(self, world: 'World'):
        super().__init__()
        super(ProcessKeeperHandler, self).__init__(world)

    def is_support_process(self, process: Process) -> Report:
        return Report(isinstance(process, WorldProcess))

    def add_process(self, process: Process) -> None:
        process.world = self.world
        super().add_process(process)

    def _handle_units(self, units: Iterable[MultitaskingUnit, ]) -> None:
        self.clear_completed_processes()
        self.__parse_world_processes_from(units)
        self.activate_processes()

    def __parse_world_processes_from(self, units: Iterable[MultitaskingUnit, ]) -> None:
        for unit in units:
            self.__handle_unit_processes(unit)

    def __handle_unit_processes(self, unit: MultitaskingUnit) -> None:
        for process in unit.processes:
            if isinstance(process, WorldProcess):
                unit.remove_process(process)
                self.add_process(process)


class RenderResourceParser(UnitHandler, IRenderRersourceKeeper):
    def __init__(self, world: 'World'):
        super().__init__(world)
        self._parsed_resource_packs = list()

    @property
    def render_resource_packs(self) -> tuple[ResourcePack, ]:
        return tuple(self._parsed_resource_packs)

    def clear_parsed_resource_packs(self) -> None:
        self._parsed_resource_packs = list()

    def is_unit_suitable(self, unit: IUpdatable) -> Report:
        return (
            super().is_unit_suitable(unit) and
            Report(
                isinstance(unit, PositionalUnit) and
                unit.avatar is not None
            )
        )

    def _handle_units(self, units: Iterable[IUpdatable, ]) -> None:
        self.clear_parsed_resource_packs()

        for unit in units:
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


class UnitMover(FocusedUnitHandler):
    def is_unit_suitable(self, unit: IMovable) -> Report:
        return super().is_unit_suitable(unit) and Report(isinstance(unit, IMovable))

    def _handle_unit(self, unit: IMovable) -> None:
        unit.move()


class World(IUpdatable, MixinDiscrete, ABC):
    _unit_handler_factories: Iterable[Callable[[Self], UnitHandler], ]

    def __init__(self, inhabitants: Iterable = tuple()):
        self.__inhabitant = set()
        self._unit_handlers = tuple(
            unit_handler_factory(self)
            for unit_handler_factory in self._unit_handler_factories
        )

        for inhabitant in inhabitants:
            self.add_inhabitant(inhabitant)

    @property
    def parts(self) -> frozenset[IUpdatable, ]:
        return frozenset(self.__inhabitant)

    @property
    def unit_handlers(self) -> tuple[UnitHandler, ]:
        return self._unit_handlers

    def is_inhabited_for(self, inhabitant: IUpdatable) -> bool:
        return isinstance(inhabitant, IUpdatable) and not isinstance(inhabitant, World)

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


class CustomWorld(World):
    def __init__(
        self,
        inhabitants: Iterable = tuple(),
        unit_handler_factories: Iterable[Callable[[World], UnitHandler], ] = tuple()
    ):
        self._unit_handler_factories = tuple(unit_handler_factories)
        super().__init__(inhabitants)


class AppFactory(IAppFactory, metaclass=AttributesTransmitterMeta):
    _attribute_names_to_parse = ('_loop_handler_factories', )

    _loop_handler_factories: Iterable[LoopHandler] = tuple()
    _updater_loop_handler_factory: LoopHandler = UpdaterLoopHandler

    _loop_factory: Callable[[Iterable[UpdaterLoopHandler]], ILoop] = CustomHandlerLoop
    _render_activator_factory: IRenderActivatorFactory = RenderActivator

    def __call__(
        self,
        world: World,
        renders: Iterable[IRender, ]
    ) -> ILoop:
        render_activator = self._render_activator_factory(
            self._get_resource_parser_from(world),
            renders
        )

        return self._loop_factory((
            CustomFactory(self._updater_loop_handler_factory, (world, render_activator)),
            *self._loop_handler_factories
        ))

    def _get_resource_parser_from(self, world: World) -> RenderResourceParser:
        for unit_handler in world.unit_handlers:
            if isinstance(unit_handler, RenderResourceParser):
                return unit_handler

        raise InvalidWorldError(f"World {world} does not have resource parsers for render")


class CustomAppFactory(AppFactory):
    def __init__(
        self,
        loop_handler_factories: Iterable[LoopHandler] = tuple(),
        loop_factory: Callable[[Iterable[UpdaterLoopHandler]], ILoop] = CustomHandlerLoop,
        updater_loop_handler_factory: LoopHandler = UpdaterLoopHandler,
        render_activator_factory: IRenderActivatorFactory = RenderActivator
    ):
        self._loop_factory = loop_factory
        self._render_activator_factory = render_activator_factory
        self._loop_handler_factories = loop_handler_factories
        self._updater_loop_handler_factory = updater_loop_handler_factory


default_app_factory = AppFactory()
