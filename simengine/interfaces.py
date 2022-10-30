from abc import ABC, abstractmethod
from typing import Iterable


class IUpdatable(ABC):
    @abstractmethod
    def update(self) -> None:
        pass


class IDiscretable(ABC):
    @property
    @abstractmethod
    def parts(self) -> frozenset[IUpdatable, ]:
        pass

    @property
    def deep_parts(self) -> frozenset[IUpdatable, ]:
        pass


class IMovable(ABC):
    @abstractmethod
    def move(self) -> None:
        pass


class IRenderRersourceKeeper(ABC):
    @property
    @abstractmethod
    def render_resource_packs(self) -> tuple['ResourcePack', ]:
        pass


class IAvatar(IUpdatable, IRenderRersourceKeeper, ABC):
    pass


class ILoop(ABC):
    @abstractmethod
    def run(self) -> None:
        pass

    @abstractmethod
    def finish(self) -> None:
        pass


class IZone(ABC):
    @abstractmethod
    def move_by(self, point_changer: 'IPointChanger') -> None:
        pass

    @abstractmethod
    def is_vector_passes(self, vector: 'VirtualVector') -> bool:
        pass

    @abstractmethod
    def is_vector_entered(self, vector: 'VirtualVector') -> bool:
        pass

    @abstractmethod
    def is_point_inside(self, point: 'Vector') -> bool:
        pass


class IRenderActivatorFactory(ABC):
    @abstractmethod
    def __call__(
        self,
        rersource_keepers: Iterable[IRenderRersourceKeeper],
        redners: Iterable['Render', ]
    ) -> 'RenderActivator':
        pass


class IAppFactory(ABC):
    def __call__(
        self,
        world: 'World',
        renders: Iterable['RenderResourceParser', ]
    ) -> 'LoopUpdater':
        pass


class IZoneFactory(ABC):
    @abstractmethod
    def __call__(self, unit: IUpdatable) -> 'Figure':
        pass


class IBilateralProcessFactory(ABC):
    @property
    @abstractmethod
    def process_type(self) -> type:
        pass

    @abstractmethod
    def __call__(self, active_unit: IUpdatable, passive_unit: IUpdatable) -> 'Process':
        pass


class IAvatarFactory(ABC):
    @abstractmethod
    def __call__(self, unit: 'PositionalUnit') -> IAvatar:
        pass
