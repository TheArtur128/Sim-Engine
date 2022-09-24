from abc import ABC, abstractmethod
from typing import Iterable


class IUpdatable(ABC):
    @abstractmethod
    def update(self) -> None:
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


class IZone(ABC):
    @abstractmethod
    def is_point_inside(self, point: 'Vector') -> bool:
        pass


class ILoopFactory(ABC):
    @abstractmethod
    def __call__(self, units: Iterable[IUpdatable, ]) -> 'LoopUpdater':
        pass


class IRenderActivatorFactory(ABC):
    @abstractmethod
    def __call__(
        self,
        rersource_keeper: 'IRenderRersourceKeeper',
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


class IHitboxFactory(ABC):
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
