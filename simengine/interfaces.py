from abc import ABC, abstractmethod
from typing import Iterable


class IUpdatable(ABC):
    """
    The interface of anything that can handle its state.

    Objects that are upcast to this interface and implementer classes that are
    implemented with a focus on self-calculation are called units.
    """

    @abstractmethod
    def update(self) -> None:
        """Main method for resuming | continuing computations."""


class IDiscretable(ABC):
    """Interface for objects delegating or processing any other objects."""

    @property
    @abstractmethod
    def parts(self) -> frozenset[IUpdatable]:
        """The property of getting objects directly lying in this object."""

    @property
    def deep_parts(self) -> frozenset[IUpdatable]:
        """Property to get all parts including parts of the parts themselves."""


class IMovable(ABC):
    """Interface for objects capable of moving."""

    @abstractmethod
    def move(self) -> None:
        """Direct Method of object motion."""


class IRenderRersourceKeeper(ABC):
    """Interface for objects containing data to be drawn."""

    @property
    @abstractmethod
    def render_resource_packs(self) -> tuple['ResourcePack']:
        """Property for packs of directly render resources."""


class IAvatar(IUpdatable, IRenderRersourceKeeper, ABC):
    """Interface for processing and directly storing processed render resources."""


class ILoop(ABC):
    """
    Loop class representation interface for abstracting dependencies on how an
    loop starts.
    """

    @abstractmethod
    def run(self) -> None:
        """Loop Start Method to respectively start a loop."""

    @abstractmethod
    def finish(self) -> None:
        """Method for forcibly ending a loop."""


class IZone(ABC):
    """
    Interface for representing an object that occupies some space and the
    possibility of checking about the presence of other objects in this space.
    """

    @abstractmethod
    def move_by(self, point_changer: 'IPointChanger') -> None:
        """
        A method for structured zone modification by abstracting from the direct
        implementation of the modification.

        Uses a point changer as an atomic implementation of changes, which is
        the argument of this method.
        """

    @abstractmethod
    def is_vector_passes(self, vector: 'VirtualVector') -> bool:
        """Method for finding an input vector in a zone."""

    @abstractmethod
    def is_vector_entered(self, vector: 'VirtualVector') -> bool:
        """Method for finding an end point of an input vector in a zone."""

    @abstractmethod
    def is_point_inside(self, point: 'Vector') -> bool:
        """Method for finding an input in a zone."""


class IRenderActivatorFactory(ABC):
    """Factory interface for implementation of RenderActivatorFactory interface."""

    @abstractmethod
    def __call__(
        self,
        rersource_keepers: Iterable[IRenderRersourceKeeper],
        redners: Iterable['IRender']
    ) -> 'RenderActivator':
        """Method creating an object."""


class IAppFactory(ABC):
    """
    Factory interface for creating a loop that implements the connection between
    the domain and its rendering.

    Due to the specific form of such loops, they are further called applications,
    since they implement its launch.
    """

    def __call__(
        self,
        world: 'World',
        renders: Iterable['IRenderResourceParser']
    ) -> 'ILoop':
        """
        Method for creating a loop, where the domain is an input world instance
        and the rendering implementations are input renders.
        """


class IZoneFactory(ABC):
    """Zone factory interface for an input object."""

    @abstractmethod
    def __call__(self, unit: IUpdatable) -> 'IZone':
        """Method creating an object."""


class IBilateralProcessFactory(ABC):
    """
    Interface for creating a separate process that implements the relationship
    of two units.
    """

    @property
    @abstractmethod
    def process_type(self) -> type:
        """Property holding the type of the subsequently created process."""

    @abstractmethod
    def __call__(self, active_unit: IUpdatable, passive_unit: IUpdatable) -> 'IProcess':
        """
        Process creation method that has two arguments: a process's exciter and
        its acceptor.
        """


class IAvatarFactory(ABC):
    """Factory interface for creating an avatar for an unit."""

    @abstractmethod
    def __call__(self, unit: 'PositionalUnit') -> IAvatar:
        """Method creating an object."""
