from abc import ABC, abstractmethod
from dataclass import dataclasses
from typing import Iterable


@dataclass(frozen=True)
class RenderResourcePack:
    data: any
    position: tuple[int | float, ]


class IResourceRender(ABC):
    @abstractmethod
    def __call__(self, resource: any, surface: any, point: Vector | None = None) -> None:
        pass

    @abstractmethod
    def is_resource_renderable(self, resource: any) -> bool:
        pass


class TypedResourceRender(IResourceRender, ABC):
    supported_resource_types: tuple[type, ] | None

    def is_resource_renderable(self, resource: any) -> bool:
        return all(map(
            lambda supported_type: isinstance(resource, supported_type),
            self.supported_resource_types
        )) if self.supported_resource_types else True


class IUnitRender(ABC):
    @abstractmethod
    def __call__(self, unit: Unit) -> None:
        pass

    @abstractmethod
    def _get_resource_from_unit(self, unit: Unit) -> any:
        pass


class UnitRender(IUnitRender, ABC):
    def __init__(self, resource_renders: Iterable[IResourceRender, ], surfaces: Iterable):
        self._resource_renders = frozenset(resource_renders)
        self._surfaces = frozenset(surfaces)

    def __call__(self, unit: Unit) -> None:
        resource = self._get_resource_from_unit(unit)
        resource_position = (
            unit.position if isinstance(unit, PositionalUnit)
            else None
        )

        for resource_render in filter(
            lambda resource_render: resource_render.is_resource_renderable(resource),
            self._resource_renders
        ):
            for surface in self._surfaces:
                resource_render(resource, surface, resource_position)

    def _get_resource_from_unit(self, unit: Unit) -> any:
        return unit.avatar.render_resource
