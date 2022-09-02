from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Callable


@dataclass(frozen=True)
class SpawnContainer:
    """Postpones object creation."""

    factory: Callable
    args_for_factory: tuple = tuple()
    kwargs_for_factory: dict = field(default_factory=dict)
    meta_information: dict = field(default_factory=dict)

    def __call__(self) -> any:
        return self.factory(*self.args_for_factory, **self.kwargs_for_factory)
