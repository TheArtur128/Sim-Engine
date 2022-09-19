from abc import ABC, abstractmethod
from typing import NamedTuple, Callable, Iterable

from geometry import Vector
from interfaces import IUpdatable
from errors.render_errors import UnsupportedResourceError


class PositionalRenderResource(NamedTuple):
    resource: any
    point: Vector


class IRenderRersourceKeeper(ABC):
    @property
    @abstractmethod
    def render_resources(self) -> tuple[PositionalRenderResource, ]:
        pass


class IResourceHandler(ABC):
    @abstractmethod
    def __call__(
        self,
        resource: any,
        point: tuple[int | float, ],
        surface: object
    ) -> None:
        pass


class Render(ABC):
    _resource_handler_by_resource_type: dict[type, IResourceHandler] | None = None

    @property
    @abstractmethod
    def surfaces(self) -> tuple:
        pass

    def __call__(self, positional_resource: PositionalRenderResource) -> None:
        if not self.is_supported_resource(positional_resource.resource):
            raise UnsupportedResourceError(
                f"Render {self} cannot display resource {positional_resource.resource} at {positional_resource.point}"
            )

        resource_handler = self._get_resource_handler_by(positional_resource)

        for surface in self.surfaces:
            resource_handler(
                positional_resource.resource,
                positional_resource.point.coordinates,
                surface
            )

    def is_supported_resource(self, resource: any) -> bool:
        return type(resource) in self._resource_handler_by_resource_type.keys()

    def _get_resource_handler_by(self, positional_resource: PositionalRenderResource) -> IResourceHandler:
        return self._resource_handler_by_resource_type[type(positional_resource.resource)]

    @classmethod
    def resource_handler_for(cls, resource_type: type) -> Callable[[IResourceHandler], IResourceHandler]:
        def decorator(handler: IResourceHandler):
            if cls._resource_handler_by_resource_type is None:
                cls._resource_handler_by_resource_type = dict()

            cls._resource_handler_by_resource_type[resource_type] = handler
            return handler

        return decorator


class RenderActivator(IUpdatable):
    def __init__(self, render_resource_keeper: IRenderRersourceKeeper, renders: Iterable[Render, ]):
        self.render_resource_keeper = render_resource_keeper
        self.renders = tuple(renders)

    def update(self) -> None:
        for render in self.renders:
            self.__apply_render(render)

    def __apply_render(self, render: Render) -> None:
        for positional_render_resource in self.render_resource_keeper.render_resources:
            render(positional_render_resource)
