from abc import ABC, abstractmethod
from typing import NamedTuple, Callable, Iterable

from physics import Vector
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
        positional_render_resource: PositionalRenderResource,
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
            resource_handler(positional_resource, surface)

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


class RenderDelegator(ABC):
    def __init__(self, render_resource_keeper: IRenderRersourceKeeper, renders: Iterable[Render, ]):
        self.render_resource_keeper = render_resource_keeper
        self.renders = tuple(renders)

    def __call__(self) -> None:
        for render in self.renders:
            self.__apply_render(render)

    def __apply_render(self, render: Render) -> None:
        for positional_render_resource in self.render_resource_keeper.render_resources:
            render(positional_render_resource)


class Matrica:
    def __init__(self, size):
        self._values = [None for _ in range(size[0])] * size[1]
        self._size = tuple(size)

    @property
    def size(self):
        return self._size

    def __repr__(self) -> str:
        return f"{self._values[:self._size[0]]}\n{self._values[self._size[0]:]}"

    def __getitem__(self, point) -> any:
        return self.get_from(point)

    def __setitem__(self, point, value: any) -> None:
        self.set_to(point, value)

    def get_from(self, point) -> any:
        return self._values[self._convert_point_to_index(point)]

    def set_to(self, point, value: any) -> None:
        self._values[self._convert_point_to_index(point)] = value

    def _convert_point_to_index(self, point) -> int:
        return point[0] + point[1]*self._size[1]






