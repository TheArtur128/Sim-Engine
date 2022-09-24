from abc import ABC, abstractmethod
from typing import Iterable, Callable, Optional

from beautiful_repr import StylizedMixin, Field

from interfaces import *
from renders import ResourcePack, RenderActivator, IRender
from errors.core_errors import *
from geometry import Vector, Figure
from tools import ReportAnalyzer, BadReportHandler, Report, StrictToStateMixin, LoopUpdater, CustomFactory


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


class CustomBilateralProcessFactory(IBilateralProcessFactory, ABC):
    def __init__(self, process_type: type):
        self._process_type = process_type

    @property
    def process_type(self) -> type:
        return self._process_type

    def __call__(self, active_unit: IUpdatable, passive_unit: IUpdatable) -> Process:
        return self.process_type(active_unit, passive_unit)


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


class InteractiveUnit(IUpdatable, ABC):
    _report_analyzer = ReportAnalyzer((BadReportHandler(
        UnitError,
        "Unit state is incorrect"
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


class ProcessInteractiveUnit(InteractiveUnit, DependentUnit, ABC):
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


class DiscreteUnit(MixinDiscrete, IUpdatable, ABC):
    @property
    def parts(self) -> frozenset[IUpdatable, ]:
        return frozenset(self._parts)

    @abstractmethod
    def __create_parts__(self) -> Iterable[IUpdatable, ]:
        pass

    def init_parts(self, *args, **kwargs) -> None:
        self._parts = set(self.__create_parts__(*args, **kwargs))


class PositionalUnit(StylizedMixin, IUpdatable, ABC):
    _repr_fields = (Field('position'), )
    _avatar_factory: IAvatarFactory = CustomFactory(lambda unit: None)

    def __init__(self, position: Vector):
        super().__init__()
        self._position = position
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


class InfinitelyImpulseUnit(MovableUnit, ABC):
    def __init__(self, position: Vector):
        super().__init__(position)
        self.impulse = Vector()

    @property
    @abstractmethod
    def speed(self) -> int | float:
        pass

    @property
    def next_position(self) -> Vector:
        return self.position + self.impulse


class ImpulseUnit(InfinitelyImpulseUnit):
    def move(self) -> None:
        super().move()
        self.impulse = Vector()


class SpeedKeeperMixin(ABC):
    _speed: int | float

    @property
    def speed(self) -> int | float:
        return self._speed


class HitboxUnit(IUpdatable, ABC):
    hitbox_factories: Iterable[IHitboxFactory, ]

    def __init__(self):
        self._hitboxes = tuple(
            hitbox_factory(self)
            for hitbox_factory in self.hitbox_factories
        )

    @property
    def hitboxes(self) -> tuple[Figure, ]:
        return self._hitboxes


class Avatar(IAvatar, ABC):
    def __init__(self, unit: PositionalUnit):
        self._unit = unit

    @property
    def unit(self) -> PositionalUnit:
        return self._unit


class ResourceAvatar(Avatar, StylizedMixin, ABC):
    _repr_fields = (Field('resource'), )
    _resource_factory: Callable[['ResourceAvatar'], any]
    _resource_pack_factory: Callable[[any, Vector], ResourcePack] = ResourcePack

    def __init__(self, unit: PositionalUnit):
        super().__init__(unit)
        self._main_resource_pack = self._resource_pack_factory(
            self._resource_factory(self),
            self.unit.position
        )

    @property
    def render_resource_packs(self) -> tuple[ResourcePack, ]:
        return (self._main_resource_pack, )

    @property
    def render_resource(self) -> any:
        return self._main_resource_pack.resource

    def update(self) -> None:
        self._main_resource_pack.point = self.unit.position


class PrimitiveAvatar(ResourceAvatar, ABC):
    def __init__(self, unit: PositionalUnit, resource: any):
        self._resource_factory = lambda _: resource
        super().__init__(unit)

    @property
    def render_resource(self) -> any:
         return ResourceAvatar.render_resource.fget(self)

    @render_resource.setter
    def render_resource(self, render_resource: any) -> None:
        self._main_resource_pack.resource = render_resource


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


class UnitProcessesActivator(FocusedUnitHandler):
    def is_unit_suitable(self, unit: IUpdatable) -> Report:
        return super().is_unit_suitable(unit) and Report(isinstance(unit, DependentUnit))

    def _handle_unit(self, unit: IUpdatable) -> None:
        unit.clear_completed_processes()
        unit.activate_processes()


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
    _unit_handler_factories: Iterable[Callable[['World'], UnitHandler], ]

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
    def unit_handlers(self) -> tuple[UnitHandler]:
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


class AppFactory(IAppFactory):
    _loop_factory: ILoopFactory = LoopUpdater
    _render_activator_factory: IRenderActivatorFactory = RenderActivator

    def __call__(
        self,
        world: World,
        renders: Iterable[IRender, ]
    ) -> LoopUpdater:
        return self._loop_factory((
            world,
            self._render_activator_factory(
                self._get_resource_parser_from(world),
                renders
            )
        ))

    def _get_resource_parser_from(self, world: World) -> RenderResourceParser:
        for unit_handler in world.unit_handlers:
            if isinstance(unit_handler, RenderResourceParser):
                return unit_handler

        raise InvalidWorldError(f"World {world} does not have resource parsers for render")


class CustomAppFactory(AppFactory):
    def __init__(
        self,
        loop_factory: ILoopFactory = LoopUpdater,
        render_activator_factory: IRenderActivatorFactory = RenderActivator
    ):
        self._loop_factory = loop_factory
        self._render_activator_factory = render_activator_factory


default_app_factory = AppFactory()
