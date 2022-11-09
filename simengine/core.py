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
        return self._new_state_factory(self.process) if not self.is_valid() else None


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

    def _handle(self) -> None:
        pass


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

        while True:
            if self.state.is_valid():
                self.state.update()

            old_state = self.state
            self.__reset_state()

            if hash(old_state) == hash(self.state):
                break

        if self.state.is_compelling_to_handle:
            self._handle()

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

    def update(self) -> None:
        self._process.update()


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


class InteractiveMixin(IInteractive, ABC):
    """Interactive base implementation class."""

    _interaction_report_analyzer = ReportAnalyzer((BadReportHandler(
        InteractionError,
        "Object can't interact"
    ), ))

    def interact_with(self, passive: object) -> None:
        self._interaction_report_analyzer(self.is_support_interaction_with(passive))
        self._handle_interaction_with(passive)

    @abstractmethod
    def _handle_interaction_with(self, passive: object) -> None:
        """Method that implements the logic of interaction with a particular unit."""


class _ObjectFactoriesCash(NamedTuple):
    """Factory cache storage structure for a unit."""

    object_: object
    factories: tuple[IBilateralProcessFactory | StrictToParticipantsProcess]


class ProcessInteractiveMixin(InteractiveMixin, ProcessKeeper, ABC):
    """
    Mixin that implements interaction by creating two-way processes by object
    type.

    The two-way process factories for interaction are stored in the
    _bilateral_process_factories attribute. The content of the attribute can
    represent the factories of the corresponding processes, or process types
    strictly related to the state of the participants.
    """

    _bilateral_process_factories: Iterable[IBilateralProcessFactory | type]

    def is_support_interaction_with(self, passive: object) -> Report:
        return (
            Report(
                bool(self._get_suported_process_factories_for(passive)),
                error=IncorrectUnitInteractionError("No possible processes to occur")
            )
        )

    def _handle_interaction_with(self, passive: object) -> None:
        for factory in self._get_suported_process_factories_for(passive):
            process = factory(self, passive)
            process.start()

            self.add_process(process)

    def _get_suported_process_factories_for(self, passive: object) -> tuple[IBilateralProcessFactory]:
        """Method for getting corresponding factories by object."""

        return self.__get_cachedly_suported_process_factories_for(passive)

    def __get_cachedly_suported_process_factories_for(self, passive: object) -> tuple[IBilateralProcessFactory]:
        """Method for getting matching factories by unit using cache."""

        if passive is self.__cashed_factories_for_object.object_:
            return self.__cashed_factories_for_object.factories

        factories = tuple(
            (
                factory.process_type if hasattr(factory, 'process_type') else factory
            ).is_support_participants((self, passive))
            for factory in self._bilateral_process_factories
        )
        self.__cashed_factories_for_object = _ObjectFactoriesCash(passive, factories)

        return factories

    __cashed_factories_for_object: _ObjectFactoriesCash = _ObjectFactoriesCash(object(), tuple())


class InteractiveUnit(InteractiveMixin, IUpdatable, ABC):
    """Unit class that can interact with other units."""


class Dependent:
    """Class annotating the need for a dependency on another object."""

    master: Optional[object] = None


class StrictDependent(Dependent, StrictToStateMixin, StylizedMixin):
    """Dependent child class that must have a master for the correct state."""

    _repr_fields = (Field("master"), )
    _state_report_analyzer = ReportAnalyzer((BadReportHandler(UnmetDependencyError), ))

    def _is_correct(self) -> Report:
        return Report(
            self.master is not None,
            error=UnmetDependencyError(f"{self} must have a master")
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
    def parts(self) -> frozenset[object]:
        parts = self._get_parts()

        for part in parts:
            if isinstance(part, Dependent):
                part.master = self

        return parts

    def _get_parts(self) -> frozenset[object]:
        parts = list()

        for part_attribute_name in self._part_attribute_names:
            if not hasattr(self, part_attribute_name):
                continue

            attribute_value = getattr(self, part_attribute_name)

            append_method = getattr(
                parts,
                'extend' if isinstance(attribute_value, Iterable) else 'append'
            )

            append_method(attribute_value)

        return frozenset(parts)


class DeepPartDiscreteMixin(IDiscretable, ABC):
    """Mixin with the implementation of getting all parts for the Discrete interface."""

    @property
    def deep_parts(self) -> frozenset[object]:
        found_parts = set()

        for part in self.parts:
            found_parts.add(part)

            if hasattr(part, "deep_parts"):
                found_parts.update(part.deep_parts)
            elif hasattr(part, "parts"):
                found_parts.update(part.parts)

        return found_parts


class DiscreteUnit(IUpdatable, StructuredPartDiscreteMixin, DeepPartDiscreteMixin, ABC):
    """Discrete unit class containing other units."""

    @abstractmethod
    def init_parts(self, *args, **kwargs) -> None:
        """Method for initializing parts of a unit."""


class DiscreteUnitFactory(ABC):
    """
    Factory class for simultaneous creation and initialization of parts of a
    discrete unit.

    Creates a unit from the input arguments and initializes the parts using the
    stored.

    Stores the unit's factory in the _unit_factory attribute and the arguments
    to initialize its parts in the _unit_part_initialization_arguments attribute.
    """

    _unit_factory: Callable[[], DiscreteUnit]
    _unit_part_initialization_arguments: Arguments

    def __call__(self, *args, **kwargs) -> DiscreteUnit:
        unit = self._unit_factory(*args, **kwargs)
        self._unit_part_initialization_arguments.call_for(unit.init_parts)

        return unit


class CustomDiscreteUnitFactory(DiscreteUnitFactory):
    """DiscreteUnitFactory with input attributes to create a unit and its parts."""

    def __init__(self, unit_factory: Callable[[], DiscreteUnit], unit_part_initialization_arguments: Arguments):
        self._unit_factory = unit_factory
        self._unit_part_initialization_arguments = unit_part_initialization_arguments


class AvatarKeeper(IAvatarKeeper, ABC):
    """
    Implementation of the avatar keeper interface that initializes the avatar
    through the factory located in the _avatar_factory attribute.
    """

    _avatar_factory: IAvatarFactory

    def __init__(self):
        self._avatar = self._avatar_factory(self)

    @property
    def avatar(self) -> IAvatar:
        return self._avatar


class ZoneKeeper(ABC):
    """Class having a specific body as a zone."""

    _zone_factory: IZoneFactory

    def __init__(self):
        self._zone = self._zone_factory(self)

    @property
    def zone(self) -> Figure:
        return self._zone


class PositionalKeeper(ZoneKeeper, IPositional, ABC):
    """Сlass that has a location point."""

    _zone_factory = CustomFactory(lambda unit: Site(unit.position))

    def __init__(self, position: Vector):
        self._position = position
        super().__init__()

    @property
    def position(self) -> Vector:
        return self._position


class StaticAvatarKeeper(PositionalKeeper, AvatarKeeper):
    """Avatar keeper child class having a statically assigned position."""

    def __init__(self, position: Vector):
        super().__init__(position)
        AvatarKeeper.__init__(self)


class MovablePositionalKeeper(PositionalKeeper, IMovable, ABC):
    """Сlass providing dynamic position."""

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
        Method of movement of a object's zone according to the vector of the last
        movement of the object itself.
        """

        self._zone.move_by(DynamicTransporter(self.position - self.previous_position))


class ProcessMovablePositionalKeeper(MovablePositionalKeeper, ABC):
    """
    Movable class delegating calculation of next position to a special process.

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
        return self._moving_process.next_subject_position

    def move(self) -> None:
        self._moving_process.update()
        super().move()

        self._moving_process.state = MovingProcessState(self._moving_process)


class IMovingProcess(IProcess, ABC):
    """Process interface that calculates the next position of an object."""

    @property
    @abstractmethod
    def subject(self) -> ProcessMovablePositionalKeeper:
        """Subject property for which the next position is calculated."""

    @property
    @abstractmethod
    def next_subject_position(self) -> Vector:
        """Subject's computed next position property."""


class MovingProcess(Process, IMovingProcess, ABC):
    """MovingProcess Interface Implementation."""

    is_support_participants = CallableProxyReporter((TypeReporter((ProcessMovablePositionalKeeper, )), ))

    def __init__(self, subject: ProcessMovablePositionalKeeper):
        self._subject = subject

    @property
    def participants(self) -> tuple[ProcessMovablePositionalKeeper]:
        return self._subject

    @property
    def subject(self) -> ProcessMovablePositionalKeeper:
        return self._subject


class ProxyMovingProcess(ProxyProcess, IMovingProcess, ABC):
    """Process proxy class for a mobile process."""

    @property
    def subject(self) -> ProcessMovablePositionalKeeper:
        return self.process.subject

    @property
    def next_subject_position(self) -> Vector:
        return self.process.next_subject_position


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
    def next_subject_position(self) -> Vector:
        vector_to_next_position = (
            self.process.next_subject_position
            - self.process.subject.previous_position
        )

        return self.process.subject.position + (
            vector_to_next_position
            if vector_to_next_position.length <= self.speed_limit
            else vector_to_next_position.get_reduced_to_length(self.speed_limit)
        )


class MovingProcessState(FlagProcessState):
    """Flag of the moving process indicating the movement of a movable object."""


class DirectedMovingProcess(MovingProcess):
    """Moving process class using a public vector."""

    def __init__(self, subject: ProcessMovablePositionalKeeper):
        super().__init__(subject)
        self.vector_to_next_subject_position = Vector()

    @property
    def next_subject_position(self) -> Vector:
        return self.subject.position + self.vector_to_next_subject_position

    def _handle(self):
        pass


class ImpulseMovingProcess(DirectedMovingProcess, ABC):
    """
    Directed Moving Process class that changes the motion vector after the
    movement has been made.
    """

    _impulse_changer: IPointChanger

    def _handle(self):
        if isinstance(self.state, MovingProcessState):
            self.vector_to_next_point = self._impulse_changer(self.vector_to_next_point)


class AbruptImpulseProcess(ImpulseMovingProcess):
    """ImpulseMovingProcess class that resets the motion vector."""

    _impulse_changer = CustomFactory(lambda original_vector: Vector())


class MultilayerProcessMovablePositionalKeeperMeta(AttributesTransmitterMeta):
    """
    Meta class for combining all factories of proxy moving processes into one.

    Merges factories from the _proxy_moving_process_factories attribute into the
    _multilayer_proxy_process_factory attribute.
    """

    _attribute_names_to_parse = ('_proxy_moving_process_factories', )

    _proxy_moving_process_factories: Iterable[Callable[[IProcess], IProcess]]
    _multilayer_proxy_process_factory: Optional[Callable[[Self], IMovingProcess]] = None

    def __new__(cls, class_name: str, super_classes: tuple, attributes: dict):
        isinstance_type = super().__new__(cls, class_name, super_classes, attributes)

        for proxy_moving_process_factory in isinstance_type._proxy_moving_process_factories:
            isinstance_type._multilayer_proxy_process_factory = CustomDecoratorFactory(
                proxy_moving_process_factory,
                (
                    isinstance_type._multilayer_proxy_process_factory
                    if isinstance_type._multilayer_proxy_process_factory is not None
                    else isinstance_type._proxy_moving_process_factories[0]
                )
            )

        return isinstance_type


class MultilayerProcessMovablePositionalKeeper(ProcessMovablePositionalKeeper, ABC, metaclass=MultilayerProcessMovablePositionalKeeperMeta):
    """
    Child class ProcessMovablePositionalKeeper with native implementation of
    building a motion process factory by the proxy process factories.
    """

    def __init__(self, position: Vector):
        self._moving_process_factory = CustomDecoratorFactory(
            self._multilayer_proxy_process_factory,
            self._moving_process_factory
        ) if self._multilayer_proxy_process_factory else self._moving_process_factory

        super().__init__(position)


class MultilayerProcessMovableAvatarKeeper(MultilayerProcessMovablePositionalKeeper, AvatarKeeper):
    """
    AvatarKeeper child class that implements positioning by inheriting from
    MultilayerProcessMovablePositionalKeeper.
    """

    def __init__(self, position: Vector):
        super().__init__(position)
        AvatarKeeper.__init__(self)


class WorldInhabitantsHandler(ABC):
    """Class that handles objects in a world."""

    _inhabitant_suitabing_report_analyzer = ReportAnalyzer(
        (BadReportHandler(UnsupportedInhabitantForHandlerError), )
    )

    def __init__(self, world: 'World'):
        self.world = world

    def __call__(self, inhabitants: Iterable) -> None:
        for inhabitant in inhabitants:
            self._inhabitant_suitabing_report_analyzer(self.is_inhabitant_suitable(inhabitant))

        self._handle_inhabitants(inhabitants)

    @abstractmethod
    def is_inhabitant_suitable(self, inhabitant: object) -> Report:
        """Method that returns a inhabitant support report for handling."""

    @abstractmethod
    def _handle_inhabitants(self, inhabitants: Iterable[IUpdatable]) -> None:
        """Handling method of world's inhabitants."""


class UnscrupulousWorldInhabitantsHandler(WorldInhabitantsHandler, ABC):
    """WorldInhabitantsHandler child class that handles each inhabitant."""

    def is_inhabitant_suitable(self, inhabitant: object) -> Report:
        return Report(True)


class TypeSuportingWorldInhabitantsHandler(WorldInhabitantsHandler, ABC, metaclass=TypeReporterKeeperMeta):
    """
    WorldInhabitantsHandler class implementing inhabitant support by delegating
    a type reporter.
    """

    def is_inhabitant_suitable(self, inhabitant: object) -> Report:
        return self._type_reporter.create_report_of((inhabitant, ))


class FocusedWorldInhabitantsHandler(WorldInhabitantsHandler, ABC):
    """WorldInhabitantsHandler child class uniformly handles inhabitants."""

    def _handle_inhabitants(self, inhabitants: Iterable) -> None:
        for inhabitant in inhabitants:
            self._handle_inhabitant(inhabitant)

    @abstractmethod
    def _handle_inhabitant(self, inhabitant: object) -> None:
        """Single inhabitant handling method."""


class InhabitantUpdater(FocusedWorldInhabitantsHandler, TypeSuportingWorldInhabitantsHandler):
    """WorldInhabitantsHandler child class updating inhabitants."""

    _suported_types = (IUpdatable, )

    def _handle_inhabitant(self, inhabitant: IUpdatable) -> None:
        inhabitant.update()


class InhabitantProcessesActivator(FocusedWorldInhabitantsHandler, TypeSuportingWorldInhabitantsHandler):
    """WorldInhabitantsHandler child class activating processes inside process keepers."""

    _suported_types = (IProcessKeeper, )

    def _handle_inhabitant(self, inhabitant: object) -> None:
        inhabitant.clear_completed_processes()
        inhabitant.activate_processes()


class WorldProcessesActivator(ProcessKeeper, FocusedWorldInhabitantsHandler, TypeSuportingWorldInhabitantsHandler):
    """
    WorldInhabitantsHandler child class connecting world processes from
    inhabitants with the world.
    """

    _suported_types = (IProcessKeeper, )

    def __init__(self, world: 'World'):
        super().__init__()
        super(TypeSuportingWorldInhabitantsHandler, self).__init__(world)

    def add_process(self, process: WorldProcess) -> None:
        process.world = self.world
        super().add_process(process)

    def _handle_inhabitants(self, inhabitants: Iterable[WorldProcess]) -> None:
        self.clear_completed_processes()
        super()._handle_inhabitants(inhabitants)
        self.activate_processes()

    def _handle_inhabitant(self, inhabitant: WorldProcess) -> None:
        for process in inhabitant.processes:
            if isinstance(process, WorldProcess):
                inhabitant.remove_process(process)
                self.add_process(process)


class RenderResourceParser(WorldInhabitantsHandler, IRenderRersourceKeeper, ABC):
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

    def _handle_inhabitants(self, inhabitants: Iterable) -> None:
        self.clear_parsed_resource_packs()
        super()._handle_inhabitants(inhabitants)


class InhabitantAvatarRenderResourceParser(RenderResourceParser, FocusedWorldInhabitantsHandler, TypeSuportingWorldInhabitantsHandler):
    """RenderResourceParser taking packs from avatars of avatar keeper inhabitants."""

    _suported_types = (AvatarKeeper, )

    def _handle_inhabitant(self, inhabitant: AvatarKeeper) -> None:
        inhabitant.avatar.update()
        self._parsed_resource_packs.extend(inhabitant.avatar.render_resource_packs)


class AvatarRenderResourceParser(RenderResourceParser, FocusedWorldInhabitantsHandler, TypeSuportingWorldInhabitantsHandler):
    """RenderResourceParser taking packs from avatars inhabited in the world."""

    _suported_types = (IAvatar, )

    def _handle_inhabitant(self, inhabitant: IAvatar) -> None:
        self._parsed_resource_packs.extend(inhabitant.render_resource_packs)


class RelationsActivator(WorldInhabitantsHandler):
    """
    WorldInhabitantsHandler activating the relations of the objects inhabited in
    the world.
    """

    def _handle_inhabitants(self, inhabitants: Iterable) -> None:
        for active_inhabitants in inhabitants:
            if not isinstance(active_inhabitants, IInteractive):
                continue

            passive_inhabitants = set(inhabitants)
            passive_inhabitants.remove(active_inhabitants)

            for passive_inhabitant in passive_inhabitants:
                active_inhabitants.interact_with(passive_inhabitant)


class InhabitantMover(FocusedWorldInhabitantsHandler, TypeSuportingWorldInhabitantsHandler):
    """WorldInhabitantsHandler activating movement of moving inhabitants."""

    _suported_types = (IMovable, )

    def _handle_inhabitant(self, inhabitant: IMovable) -> None:
        inhabitant.move()


class World(IUpdatable, DeepPartDiscreteMixin, ABC):
    """
    The domain object habitat class.

    Delegates processing of domain entities to special handlers.
    Creates handlers using factories stored in _inhabitant_handler_factories
    attribute.
    """

    _inhabitant_handler_factories: Iterable[Callable[[Self], WorldInhabitantsHandler]]

    def __init__(self, inhabitants: Iterable = tuple()):
        self.__inhabitant = set()
        self._inhabitant_handlers = tuple(
            inhabitant_handler_factory(self)
            for inhabitant_handler_factory in self._inhabitant_handler_factories
        )

        for inhabitant in inhabitants:
            self.add_inhabitant(inhabitant)

    @property
    def parts(self) -> frozenset:
        return frozenset(self.__inhabitant)

    @property
    def inhabitant_handlers(self) -> tuple[WorldInhabitantsHandler]:
        """Property of handlers for world objects."""

        return self._inhabitant_handlers

    def is_inhabited_for(self, inhabitant: object) -> Report:
        return Report(not isinstance(inhabitant, World))

    def add_inhabitant(self, inhabitant: IUpdatable) -> None:
        if not self.is_inhabited_for(inhabitant):
            raise NotSupportPartError(f"World {self} does not support {inhabitant}")

        self.__inhabitant.add(inhabitant)

    def remove_inhabitant(self, inhabitant: IUpdatable) -> None:
        self.__inhabitant.remove(inhabitant)

    def update(self) -> None:
        for inhabitant_handler in self._inhabitant_handlers:
            inhabitant_handler(
                tuple(
                    inhabitant for inhabitant in self.deep_parts
                    if inhabitant_handler.is_inhabitant_suitable(inhabitant)
                )
            )


class CustomWorld(World):
    """World class using input handler factories."""

    def __init__(
        self,
        inhabitants: Iterable = tuple(),
        inhabitant_handler_factories: Iterable[Callable[[World], WorldInhabitantsHandler]] = tuple()
    ):
        self._inhabitant_handler_factories = tuple(inhabitant_handler_factories)
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
            lambda handler: isinstance(handler, IRenderRersourceKeeper),
            world.inhabitant_handlers
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
