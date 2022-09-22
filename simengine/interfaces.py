from abc import ABC, abstractmethod


class IUpdatable(ABC):
    @abstractmethod
    def update(self) -> None:
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
