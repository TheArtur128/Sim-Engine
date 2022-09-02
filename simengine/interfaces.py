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


class IUnit(IUpdatable, ABC):
    @abstractmethod
    def clear_previous_actions(self) -> None:
        pass

    @property
    @abstractmethod
    def previous_actions(self) -> tuple:
        pass

    @property
    @abstractmethod
    def action(self) -> Action | None:
        pass

    @action.setter
    @abstractmethod
    def action(self, action: Action) -> None:
        pass


class IPositionalUnit(IUnit, ABC):
    @property
    @abstractmethod
    def position(self) -> Vector:
        pass

    @abstractmethod
    def move(self) -> None:
        pass
