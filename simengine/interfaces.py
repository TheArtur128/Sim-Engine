from abc import ABC, abstractmethod


class IUpdatable(ABC):
    @abstractmethod
    def update(self) -> None:
        pass


class IAvatar(IUpdatable, ABC):
    @property
    @abstractmethod
    def render_resources(self) -> tuple:
        pass


class ILoop(ABC):
    @abstractmethod
    def run(self) -> None:
        pass
