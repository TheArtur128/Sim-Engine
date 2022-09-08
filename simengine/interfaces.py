from abc import ABC, abstractmethod


class IUpdatable(ABC):
    @abstractmethod
    def update(self) -> None:
        pass


class IInteractive(ABC):
    @abstractmethod
    def react_to(self, object_: object) -> None:
        pass


class IAvatar(IUpdatable, ABC):
    @property
    @abstractmethod
    def render_resource(self) -> any:
        pass
