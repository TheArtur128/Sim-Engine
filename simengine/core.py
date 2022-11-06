from abc import ABC, abstractmethod
from typing import Iterable, Callable, Optional, Self, NamedTuple

from beautiful_repr import StylizedMixin, Field

from simengine.interfaces import *
from simengine.renders import ResourcePack, RenderActivator, IRender
from simengine.errors.core_errors import *
from simengine.tools import *
from simengine.geometry import Vector, Figure, Site, DynamicTransporter, IPointChanger


class IProcessState(IUpdatable, ABC):
    """Interface for public process behavior."""

    @property
    def process(self) -> 'Process':
        """Property for process that has this state."""

    @abstractmethod
    def get_next_state(self) -> Optional[Self]:
        """Property of the next state of the process."""

    @abstractmethod
    def is_compelling_to_handle(self) -> bool:
        """Flag property defining the internal behavior of the process."""

    @abstractmethod
    def is_valid(self) -> Report:
        """
        Property denoting the validity of the state of the process for further
        exploitation.
        """


class ProcessState(StrictToStateMixin, IProcessState, ABC):
    """
    Basic implementation of the ProcessState interface.

    Raises an error when attempting to call with an invalid state.
    """

    _state_report_analyzer = ReportAnalyzer((BadReportHandler(
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
        self._check_state_errors()
        self._handle()

    @abstractmethod
    def _handle(self) -> None:
        """Method for handling the public state of the process."""

    def _is_correct(self) -> Report:
        return self.is_valid()


class CompletedProcessState(ProcessState):
    """Completed process state class. Raises an error during updating."""

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
    """
    Standard process state class that allows an internal state to flow without
    the need for an public one.
    """

    is_compelling_to_handle = True

    def get_next_state(self) -> None:
        return None

    def is_valid(self) -> Report:
        return Report(True)

    def _handle(self) -> None:
        pass


class NewStateByValidationProcessStateMixin(IProcessState, ABC):
    """
    Process state mixin that defines a new state when the current one is invalid.

    Provides for the creation of the next process using the _new_state_factory
    attribute.
    """

    _new_state_factory: Callable[['Process'], ProcessState | None] = CustomFactory(ActiveProcessState)

    def get_next_state(self) -> ProcessState | None:
        return self._new_state_factory(self.process) if self.is_valid() else None


class SleepProcessState(ProcessState, NewStateByValidationProcessStateMixin):
    """
    Process state class the freezing action of the internal state of the process
    for the specified number of runs of the update method.
    """

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
    """
    Process state class that doesn't handle anything but annotates handling to
    something else.
    """

    is_compelling_to_handle = True
    _is_standing: bool = False

    def is_valid(self) -> Report:
        return Report(self._is_standing)

    def update(self) -> None:
        pass

    @classmethod
    def create_flag_state(
        cls,
        name: str,
        is_standing: bool = False,
        bases: Iterable[type] = tuple(),
        attributes: dict = dict()
    ) -> Self:
        """Process state flag class dynamic creation method."""

        return type(
            name,
            bases + (cls, ),
            {'is_standing': is_standing} | attributes
        )


class IProcess(IUpdatable, ABC):
    """
    Process class, which is the removal of the processing logic of something
    into an object to systematize work with this logic.

    It has two states: internal - which is the logic rendered into the object
    and public - the state imposed from outside to control this process. Public
    state is expressed by an object and lies in the state attribute.
    """

    state: IProcessState | None

    @property
    @abstractmethod
    def original_process(self) -> Self:
        """
        Crutch property that ensures the availability of the original process
        behind a layer of proxy processes.
        """

    @property
    @abstractmethod
    def participants(self) -> tuple:
        """Property of objects involved in the process."""

    @abstractmethod
    def start(self) -> None:
        """Process start method."""


class Process(StrictToStateMixin, IProcess, ABC):
    _state_report_analyzer = ReportAnalyzer((BadReportHandler(
        ProcessError,
        "Process is not valid"
    ), ))

    state = None

    def __init__(self):
        self._check_state_errors()

    @property
    def original_process(self) -> IProcess:
        return self

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

    @abstractmethod
    def _handle(self) -> None:
        """Process internal state method."""

    def _get_next_state(self) -> ProcessState | None:
        return None

    def _is_correct(self) -> Report:
        return Report(True)

    def __reset_state(self) -> None:
        """Method for updating its public state."""

        next_state = self.state.get_next_state()

        if next_state is None:
            next_state = self._get_next_state()

        if next_state:
            self.state = next_state


class ProxyProcess(IProcess, ABC):
    """Process class that changes the logic of another process."""

    def __init__(self, process: IProcess):
        self._process = process

    @property
    def process(self) -> IProcess:
        return self._process

    @property
    def original_process(self) -> IProcess:
        current_process = self._process

        while isinstance(current_process, ProxyProcess):
            current_process = current_process.process

        return current_process

    @property
    def state(self) -> IProcessState | None:
        return self.process.state

    @state.setter
    def state(self, new_state: IProcessState | None) -> None:
        self.process.state = new_state

    @property
    def participants(self) -> tuple:
        return self._process.participants

    def start(self) -> None:
        self.process.start()


class StrictToParticipantsProcess(Process, ABC):
    """Process class that has strict restrictions on the states of its participants."""

    def _is_correct(self) -> Report:
        self.is_support_participants(self.participants)

    @classmethod
    @abstractmethod
    def is_support_participants(cls, participants: Iterable) -> Report:
        """
        Method for validating the state of participants without taking into
        account the state of the process itself.
        """


class ManyPassProcess(Process, ABC):
    """
    Process class that natively ends after a certain number of updates.

    Сertain number of updates is specified by the _passes attribute.
    """

    _passes: int

    def update(self) -> None:
        self._passes -= 1
        super().update()

    def _get_next_state(self) -> ProcessState | None:
        return CompletedProcessState(self) if self._passes <= 0 else None


class WorldProcess(Process, ABC):
    """
    Process world handling class.
    Before starting, the world attribute must be filled with the defined world.
    """

    world: Optional['World'] = None

    def start(self) -> None:
        if not self.world:
            raise WorldProcessError(f"World process {self} has no world")

        super().start()


class Event(Process, ABC):
    """Process class with homogeneous unrestricted participants."""

    def __init__(self, participants: Iterable[IUpdatable]):
        self.__participants = tuple(participants)
        super().__init__()

    @property
    def participants(self) -> tuple:
        return self.__participants


class FocusedEvent(Event, ABC):
    """Event class that handles each of its participants in the same way."""

    def _handle(self) -> None:
        for participant in self.participants:
            self._handle_participant(participant)

    @abstractmethod
    def _handle_participant(self, participant: IUpdatable) -> None:
        """Participant handling method applied to each participant."""


class UnitSpawnProcess(FocusedEvent, WorldProcess, ManyPassProcess):
    """Process class that adds its participants to the existing world, after it ends."""

    _passes = 1

    def _handle_participant(self, participant: IUpdatable) -> None:
        self.world.add_inhabitant(participant)


class UnitKillProcess(FocusedEvent, WorldProcess, ManyPassProcess):
    """
    Process class that removes its participants from the existing world, after
    it ends.
    """

    _passes = 1

    def _handle_participant(self, participant: IUpdatable) -> None:
        self.world.remove_inhabitant(participant)


class DelayedProcess(Process, ABC):
    """
    Process class that delays the execution of its logic for a certain number of
    updates.

    Number of updates is set by the _ticks_of_inactivity attribute.
    """

    _ticks_of_inactivity: int

    def start(self) -> None:
        self.activate_delay()

    def activate_delay(self) -> None:
        """Logic execution delay resume method."""

        self.state = SleepProcessState(self, self._ticks_of_inactivity)


class CustomBilateralProcessFactory(IBilateralProcessFactory, ABC):
    """BilateralProcessFactory interface implementation class."""

    def __init__(self, process_type: type):
        self._process_type = process_type

    @property
    def process_type(self) -> type:
        return self._process_type

    def __call__(self, active_unit: IUpdatable, passive_unit: IUpdatable) -> Process:
        return self.process_type(active_unit, passive_unit)


class IProcessKeeper(ABC):
    """Class interface that implements logic as input processes and manages them."""

    @property
    @abstractmethod
    def processes(self) -> frozenset[IProcess]:
        """Active processes property."""

    @property
    @abstractmethod
    def completed_processes(self) -> frozenset[IProcess]:
        """Property of processes that have completed their work."""

    @abstractmethod
    def add_process(self, process: IProcess) -> None:
        """Method for adding a new process."""

    @abstractmethod
    def remove_process(self, process: IProcess) -> None:
        """Method for forcibly removing an existing process."""

    def is_support_process(self, process: IProcess) -> Report:
        """Method for determining input process support as internal."""

    @abstractmethod
    def activate_processes(self) -> None:
        """Process management method."""

    @abstractmethod
    def clear_completed_processes(self) -> None:
        """Method for cleaning up completed processes."""


class ProcessKeeper(IProcessKeeper, ABC):
    """ProcessKeeper interface implementation class."""

    _process_adding_report_analyzer = ReportAnalyzer((BadReportHandler(
        UnsupportedProcessError,
        "Process keeper unsupported process"
    ), ))

    def __init__(self):
        self._processes = set()
        self.__completed_processes = list()

    @property
    def processes(self) -> frozenset[IProcess]:
        return frozenset(self._processes)

    @property
    def completed_processes(self) -> frozenset[IProcess]:
        return frozenset(self.__completed_processes)

    def is_support_process(self, process: IProcess) -> Report:
        return Report(isinstance(process, IProcess))

    def add_process(self, process: IProcess) -> None:
        self._process_adding_report_analyzer(self.is_support_process(process))
        self._processes.add(process)

    def remove_process(self, process: IProcess) -> None:
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
    """Unit class implementing process support."""


class InteractiveUnit(IUpdatable, ABC):
    """Unit class that can interact with other units."""

    _interaction_report_analyzer = ReportAnalyzer((BadReportHandler(
        UnitRelationError,
        "Unit can't interact"
    ), ))

    def interact_with(self, unit: IUpdatable) -> None:
        """Method for starting interaction with the input unit."""

        self._interaction_report_analyzer(self.is_support_interaction_with(unit))
        self._handle_interaction_with(unit)

    @abstractmethod
    def is_support_interaction_with(self, unit: IUpdatable) -> Report:
        """Method describing unit support for interacting with it."""

    @abstractmethod
    def _handle_interaction_with(self, unit: IUpdatable) -> None:
        """Method that implements the logic of interaction with a particular unit."""


class _ObjectFactoriesCash(NamedTuple):
    """Factory cache storage structure for a unit."""

    object_: object
    factories: tuple[IBilateralProcessFactory | StrictToParticipantsProcess]


class ProcessInteractiveUnit(InteractiveUnit, MultitaskingUnit, ABC):
    """
    Unit class that implements interaction with units by creating two-way
    processes by unit type.

    The two-way process factories for interaction are stored in the
    _bilateral_process_factories attribute. The content of the attribute can
    represent the factories of the corresponding processes, or process types
    strictly related to the state of the participants.
    """

    _bilateral_process_factories: Iterable[IBilateralProcessFactory | type]

    def is_support_interaction_with(self, unit: IUpdatable) -> Report:
        return (
            Report(
                bool(self._get_suported_process_factories_for(unit)),
                error=IncorrectUnitInteractionError("No possible processes to occur")
            )
        )

    def _handle_interaction_with(self, unit: IUpdatable) -> None:
        for factory in self._get_suported_process_factories_for(unit):
            process = factory(self, unit)
            process.start()

            self.add_process(process)

    def _get_suported_process_factories_for(self, unit: IUpdatable) -> tuple[IBilateralProcessFactory]:
        """Method for getting corresponding factories by unit."""

        return self.__get_cachedly_suported_process_factories_for(unit)

    def __get_cachedly_suported_process_factories_for(self, unit: IUpdatable) -> tuple[IBilateralProcessFactory]:
        """Method for getting matching factories by unit using cache."""

        if unit is self.__cashed_factories_for_object.object_:
            return self.__cashed_factories_for_object.factories

        factories = tuple(
            (
                factory.process_type if hasattr(factory, 'process_type') else factory
            ).is_support_participants((self, unit))
            for factory in self._bilateral_process_factories
        )
        self.__cashed_factories_for_object = _ObjectFactoriesCash(unit, factories)

        return factories

    __cashed_factories_for_object: _ObjectFactoriesCash = _ObjectFactoriesCash(object(), tuple())


class DependentUnit(IUpdatable, ABC):
    """Unit class that has a reference to another unit."""

    master: IUpdatable | None = None


class PartUnit(DependentUnit, StrictToStateMixin, StylizedMixin, ABC):
    """Unit class that is part of another unit. Cannot be computed without a principal."""

    _repr_fields = (Field("master"), )
    _state_report_analyzer = ReportAnalyzer((BadReportHandler(UnitPartError), ))

    def _is_correct(self) -> Report:
        return Report(
            self.master is not None,
            error=UnitPartError(f"Part unit {self} must have a master")
        )


class StructuredPartDiscreteMixin(IDiscretable, ABC, metaclass=AttributesTransmitterMeta):
    """
    Class that allows you to structure attributes that have parts of an object.

    The names of the attributes that store the parts of an object are in the
    _part_attribute_names attribute.
    """

    _attribute_names_to_parse = '_part_attribute_names',
    _part_attribute_names: tuple[str]

    @property
    def parts(self) -> frozenset[DependentUnit]:
        parts = self._get_parts()

        for part in parts:
            part.master = self

        return parts

    def _get_parts(self) -> frozenset[DependentUnit]:
        parts = list()

        for part_attribute_name in self._part_attribute_names:
            if not hasattr(self, part_attribute_name):
                continue

            attribute_value = getattr(self, part_attribute)

            append_method = getattr(
                parts,
                'extend' if isinstance(attribute_value, Iterable) else 'append'
            )

            append_method(attribute_value)

        return frozenset(parts)


class DeepPartDiscreteMixin(IDiscretable, ABC):
    """Mixin with the implementation of getting all parts for the Discrete interface."""

    @property
    def deep_parts(self) -> frozenset[IUpdatable]:
        found_parts = set()

        for part in self.parts:
            found_parts.add(part)

            if hasattr(part, "deep_parts"):
                found_parts.update(part.deep_parts)

        return found_parts


class DiscreteUnit(IUpdatable, StructuredPartDiscreteMixin, DeepPartDiscreteMixin, ABC):
    """Discrete unit class containing other units."""

    @abstractmethod
    def init_parts(self, *args, **kwargs) -> None:
        pass


class AnyPartMixin:
    """Mixin for illegible addition of parts."""

    def __create_parts__(self, *parts) -> Iterable[IUpdatable]:
        return parts


class TactileUnit(IUpdatable, ABC):
    """Unit class having a specific body."""

    _zone_factory: IZoneFactory

    def __init__(self):
        self._zone = self._zone_factory(self)

    @property
    def zone(self) -> Figure:
        return self._zone


class PositionalUnit(TactileUnit, StylizedMixin, ABC):
    """Unit class having position and visual representation."""

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
    """Unit class providing dynamic position."""

    def __init__(self, position: Vector):
        super().__init__(position)
        self.__previous_position = self.position

    @property
    def previous_position(self) -> Vector:
        """Property of the position the unit had before the start of the last move."""

        return self.__previous_position

    @property
    @abstractmethod
    def next_position(self) -> Vector:
        """Property that defines the next position when moving."""

    def move(self) -> None:
        self.__previous_position = self._position
        self._position = self.next_position

        self._update_zone_position()

    def _update_zone_position(self) -> None:
        """
        Method of movement of a unit's zone according to the vector of the last
        movement of the unit itself.
        """

        self._zone.move_by(DynamicTransporter(self.position - self.previous_position))


class ProcessMovableUnit(MovableUnit, ABC):
    """
    Movable unit class delegating calculation of next position to a special process.

    Creates a moving process by the corresponding _moving_process_factory attribute.
    """

    _moving_process_factory: Callable[[Self], 'IMovingProcess']

    def __init__(self, position: Vector):
        super().__init__(position)
        self._moving_process = self._moving_process_factory(self)

    @property
    def moving_process(self) -> 'IMovingProcess':
        return self._moving_process

    @property
    def next_position(self) -> Vector:
        return self._moving_process.next_unit_position

    def move(self) -> None:
        super().move()
        self._moving_process.state = UnitMovingProcessState(self._moving_process)


class IMovingProcess(IProcess, ABC):
    """Process interface that calculates the next position of the unit."""

    @property
    @abstractmethod
    def movable_unit(self) -> ProcessMovableUnit:
        """Unit property for which the next position is calculated."""

    @property
    @abstractmethod
    def next_unit_position(self) -> Vector:
        """Unit's computed next position property."""


class MovingProcess(Process, IMovingProcess, ABC):
    """MovingProcess Interface Implementation."""

    is_support_participants = CallableProxyReporter((TypeReporter((ProcessMovableUnit, )), ))

    def __init__(self, movable_unit: ProcessMovableUnit):
        self._movable_unit = movable_unit

    @property
    def participants(self) -> tuple[ProcessMovableUnit]:
        return self._movable_unit

    @property
    def movable_unit(self) -> ProcessMovableUnit:
        return self._movable_unit


class ProxyMovingProcess(ProxyProcess, IMovingProcess, ABC):
    """Process proxy class for a mobile process."""

    @property
    def movable_unit(self) -> ProcessMovableUnit:
        return self.process.movable_unit

    @property
    def next_unit_position(self) -> Vector:
        return self.process.next_unit_position


class SpeedLimitedProxyMovingProcess(ProxyMovingProcess):
    """Proxy moving process that limits the length of the motion vector."""

    def __init__(self, process: MovingProcess, speed_limit: int | float):
        super().__init__(process)
        self._speed_limit = speed_limit

    @property
    def speed_limit(self) -> int | float:
        """Motion vector length constraint property."""

        return self._speed_limit

    @property
    def next_unit_position(self) -> Vector:
        vector_to_next_position = (
            self.process.next_unit_position
            - self.process.movable_unit.previous_position
        )

        return self.process.movable_unit.position + (
            vector_to_next_position
            if vector_to_next_position.length <= self.speed_limit
            else vector_to_next_position.get_reduced_to_length(self.speed_limit)
        )

    def update(self) -> None:
        pass


class UnitMovingProcessState(FlagProcessState):
    """Flag of the moving process indicating the movement of the unit."""


class DirectedMovingProcess(MovingProcess):
    """Moving process class using a public vector."""

    def __init__(self, movable_unit: ProcessMovableUnit):
        super().__init__(movable_unit)
        self.vector_to_next_unit_position = Vector()

    @property
    def next_unit_position(self) -> Vector:
        return self.movable_unit.position + self.vector_to_next_unit_position

    def _handle(self):
        pass


class ImpulseMovingProcess(DirectedMovingProcess, ABC):
    """
    Directed Moving Process class that changes the motion vector after the
    movement has been made.
    """

    _impulse_changer: IPointChanger

    def _handle(self):
        if isinstance(self.state, UnitMovingProcessState):
            self.vector_to_next_point = self._impulse_changer(self.vector_to_next_point)


class AbruptImpulseProcess(ImpulseMovingProcess):
    """ImpulseMovingProcess class that resets the motion vector."""

    _impulse_changer = CustomFactory(lambda original_vector: Vector())


class SpeedLimitedUnit(ProcessMovableUnit, ABC):
    """Unit class with motion preconfiguration."""

    _speed_limit: int | float
    _moving_process_factory = CustomDecoratorFactory(
        CustomFactory(SpeedLimitedProxyMovingProcess, speed_limit=None),
        AbruptImpulseProcess
    )

    def __init__(self, position: Vector):
        self._moving_process_factory.decorator_factory.arguments_for_factory.kwargs['speed_limit'] = self._speed_limit
        super().__init__(position)


class CustomSpeedLimitedUnit(SpeedLimitedUnit):
    """SpeedLimitedUnit class for runtime creation."""

    def __init__(self, position: Vector, speed_limit: int | float):
        self._speed_limit = speed_limit
        super().__init__(position)

    @property
    def speed_limit(self) -> int | float:
        return self._speed_limit


class UnitHandler(ABC):
    """Class that handles units in the world."""

    _unit_suitabing_report_analyzer = ReportAnalyzer((BadReportHandler(UnsupportedUnitForHandlerError), ))

    def __init__(self, world: 'World'):
        self.world = world

    def __call__(self, units: Iterable[IUpdatable]) -> None:
        for unit in units:
            self._unit_suitabing_report_analyzer(self.is_unit_suitable(unit))

        self._handle_units(units)

    def is_unit_suitable(self, unit: IUpdatable) -> Report:
        return Report(isinstance(unit, IUpdatable))

    @abstractmethod
    def _handle_units(self, units: Iterable[IUpdatable]) -> None:
        """Handling method of world's units."""


class TypeSuportingUnitHandler(UnitHandler, ABC, metaclass=TypeReporterKeeperMeta):
    """UnitHandler class implementing unit support by delegating a type reporter."""

    def is_unit_suitable(self, unit: IUpdatable) -> Report:
        return self._type_reporter.create_report_of((unit, ))


class FocusedUnitHandler(UnitHandler, ABC):
    """UnitHandler class uniformly handles units."""

    def _handle_units(self, units: Iterable[IUpdatable]) -> None:
        for unit in units:
            self._handle_unit(unit)

    @abstractmethod
    def _handle_unit(self, unit: IUpdatable) -> None:
        """Single unit handling method."""


class UnitUpdater(FocusedUnitHandler):
    """UnitHandler updating units."""

    def _handle_unit(self, unit: IUpdatable) -> None:
        unit.update()


class ProcessKeeperHandler(UnitHandler, ABC):
    """UnitHandler handling the process keepers."""

    def is_unit_suitable(self, unit: IUpdatable) -> Report:
        return super().is_unit_suitable(unit) and Report(isinstance(unit, ProcessKeeper))


class UnitProcessesActivator(FocusedUnitHandler, ProcessKeeperHandler):
    """UnitHandler activating processes inside process keepers."""

    def _handle_unit(self, unit: IUpdatable) -> None:
        unit.clear_completed_processes()
        unit.activate_processes()


class WorldProcessesActivator(ProcessKeeper, ProcessKeeperHandler):
    """UnitHandler connecting world processes with the world."""

    def __init__(self, world: 'World'):
        super().__init__()
        super(ProcessKeeperHandler, self).__init__(world)

    def is_support_process(self, process: Process) -> Report:
        return Report(isinstance(process, WorldProcess))

    def add_process(self, process: Process) -> None:
        process.world = self.world
        super().add_process(process)

    def _handle_units(self, units: Iterable[MultitaskingUnit]) -> None:
        self.clear_completed_processes()
        self.__parse_world_processes_from(units)
        self.activate_processes()

    def __parse_world_processes_from(self, units: Iterable[MultitaskingUnit]) -> None:
        for unit in units:
            self.__handle_unit_processes(unit)

    def __handle_unit_processes(self, unit: MultitaskingUnit) -> None:
        for process in unit.processes:
            if isinstance(process, WorldProcess):
                unit.remove_process(process)
                self.add_process(process)


class RenderResourceParser(FocusedUnitHandler, IRenderRersourceKeeper, ABC):
    """
    RenderRersourceKeeper class that takes its render resource packs thanks to
    handling the inhabitants of the world.
    """

    def __init__(self, world: 'World'):
        super().__init__(world)
        self._parsed_resource_packs = list()

    @property
    def render_resource_packs(self) -> tuple[ResourcePack]:
        return tuple(self._parsed_resource_packs)

    def clear_parsed_resource_packs(self) -> None:
        self._parsed_resource_packs = list()

    def _handle_units(self, units: Iterable[IUpdatable]) -> None:
        self.clear_parsed_resource_packs()
        super()._handle_units(units)


class UnitAvatarRenderResourceParser(RenderResourceParser, TypeSuportingUnitHandler):
    """RenderResourceParser taking packs from positional unit avatars."""

    _suported_types = PositionalUnit,

    def _handle_unit(self, unit: IUpdatable) -> None:
        unit.avatar.update()
        self._parsed_resource_packs.extend(unit.avatar.render_resource_packs)


class AvatarRenderResourceParser(RenderResourceParser, TypeSuportingUnitHandler):
    """RenderResourceParser taking packs from avatars inhabited in the world."""

    _suported_types = IAvatar,

    def _handle_unit(self, unit: IAvatar) -> None:
        self._parsed_resource_packs.extend(unit.render_resource_packs)


class UnitRelationsActivator(UnitHandler):
    """UnitHandler activating the relations of the units inhabited in the world."""

    def _handle_units(self, units: Iterable[IUpdatable]) -> None:
        for active_unit in units:
            if not isinstance(active_unit, InteractiveUnit):
                continue

            passive_units = set(units)
            passive_units.remove(active_unit)

            for passive_unit in passive_units:
                active_unit.interact_with(passive_unit)


class UnitMover(FocusedUnitHandler):
    """UnitHandler activating movement of moving units."""

    def is_unit_suitable(self, unit: IMovable) -> Report:
        return super().is_unit_suitable(unit) and Report(isinstance(unit, IMovable))

    def _handle_unit(self, unit: IMovable) -> None:
        unit.move()


class World(IUpdatable, DeepPartDiscreteMixin, ABC):
    """
    The domain object habitat class.

    Delegates processing of domain entities to special handlers.
    Creates handlers using factories stored in _unit_handler_factories attribute.
    """

    _unit_handler_factories: Iterable[Callable[[Self], UnitHandler]]

    def __init__(self, inhabitants: Iterable = tuple()):
        self.__inhabitant = set()
        self._unit_handlers = tuple(
            unit_handler_factory(self)
            for unit_handler_factory in self._unit_handler_factories
        )

        for inhabitant in inhabitants:
            self.add_inhabitant(inhabitant)

    @property
    def parts(self) -> frozenset[IUpdatable]:
        return frozenset(self.__inhabitant)

    @property
    def unit_handlers(self) -> tuple[UnitHandler]:
        """Property of handlers for world objects."""

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
    """World class using input handler factories."""

    def __init__(
        self,
        inhabitants: Iterable = tuple(),
        unit_handler_factories: Iterable[Callable[[World], UnitHandler]] = tuple()
    ):
        self._unit_handler_factories = tuple(unit_handler_factories)
        super().__init__(inhabitants)


class AppFactory(IAppFactory, metaclass=AttributesTransmitterMeta):
    """Class that implements the application factory interface."""

    _attribute_names_to_parse = ('_loop_handler_factories', )

    _loop_handler_factories: Iterable[LoopHandler] = tuple()
    _updater_loop_handler_factory: LoopHandler = UpdaterLoopHandler

    _loop_factory: Callable[[Iterable[UpdaterLoopHandler]], ILoop] = CustomHandlerLoop
    _render_activator_factory: IRenderActivatorFactory = RenderActivator

    def __call__(
        self,
        world: World,
        renders: Iterable[IRender]
    ) -> ILoop:
        render_activator = self._render_activator_factory(
            self._get_resource_parsers_from(world),
            renders
        )

        return self._loop_factory((
            CustomFactory(self._updater_loop_handler_factory, (world, render_activator)),
            *self._loop_handler_factories
        ))

    def _get_resource_parsers_from(self, world: World) -> tuple[RenderResourceParser]:
        resource_parsers = tuple(filter(
            lambda handler: isinstance(unit_handler, RenderResourceParser),
            world.unit_handlers
        ))

        if resource_parsers:
            return resource_parsers

        raise InvalidWorldError(f"World {world} does not have resource parsers for render")


class CustomAppFactory(AppFactory):
    """AppFactory class with input factories."""

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
