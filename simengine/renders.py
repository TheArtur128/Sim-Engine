from abc import ABC, abstractmethod
from typing import NamedTuple, Callable, Iterable
from dataclasses import dataclass

from beautiful_repr import StylizedMixin, Field

from geometry import Vector
from interfaces import IUpdatable
from errors.render_errors import UnsupportedResourceError
from tools import ReportAnalyzer, BadReportHandler, Report


@dataclass
class RenderResourcePack:
    resource: any
    point: any


class IAvatar(IUpdatable, ABC):
    @property
    @abstractmethod
    def render_resources(self) -> tuple[RenderResourcePack, ]:
        pass


class IRenderRersourceKeeper(ABC):
    @property
    @abstractmethod
    def render_resources(self) -> tuple[PositionalRenderResource, ]:
        pass


class IResourceHandler(ABC):
    @abstractmethod
    def __call__(self, resource: any, point: any, surface: any) -> None:
        pass


class ResourceHandler(IResourceHandler, ABC):
    _report_analyzer = ReportAnalyzer(
        (BadReportHandler(UnsupportedResourceError, "Resource Handler can't handle resource"), )
    )

    def __call__(self, resource: any, point: any, surface: any) -> None:
        self._report_analyzer(self.is_support_to_handle(resource, point, surface))
        self._handle(resource, point, surface)

    def is_support_to_handle(self, resource: any, point: any, surface: any) -> Report:
        return Report(True)

    @abstractmethod
    def _handle(self, resource: any, point: any, surface: any) -> None:
        pass


class ResourceHandlerWrapper(ResourceHandler, StylizedMixin):
    _repr_fields = (Field('resource_handler'), )

    def __init__(self, resource_handler: IResourceHandler):
        self.resource_handler = resource_handler

    def is_support_to_handle(self, resource: any, point: any, surface: any) -> Report:
        return (
            self.resource_handler.is_support_to_handle(resource, point, surface)
            if hasattr(self.resource_handler, 'is_support_to_handle') else Report(True)
        )

    def _handle(self, resource: any, point: any, surface: any) -> None:
        self.resource_handler(resource, point, surface)


class TypedResourceHandler(ResourceHandlerWrapper):
    _repr_fields = (Field(
        'supported_resource_type',
        value_getter=lambda handler, _: handler.supported_resource_type.__name__
    ), )

    def __init__(self, resource_handler: IResourceHandler, supported_resource_type: type):
        super().__init__(resource_handler)
        self.supported_resource_type = supported_resource_type

    def is_support_to_handle(self, resource: any, point: any, surface: any) -> Report:
        return (
            Report(isinstance(resource, self.supported_resource_type)) and
            super().is_support_to_handle(resource, point, surface)
        )
        pass


class Render(ABC):
    _resource_handler_by_resource_type: dict[type, IResourceHandler] | None = None

    @property
    @abstractmethod
    def surfaces(self) -> tuple:
        pass

    def __call__(self, positional_resource: PositionalRenderResource) -> None:
        self.draw_resource(positional_resource)

    def draw_scene(self, positional_resources: Iterable[PositionalRenderResource, ]) -> None:
        for surface in self.surfaces:
            self._prepare_surface(surface)

        for positional_resource in positional_resources:
            self.draw_resource(positional_resource)

    def draw_resource(self, positional_resource: PositionalRenderResource) -> None:
        if not self.is_supported_resource(positional_resource.resource):
            raise UnsupportedResourceError(
                f"Render {self} cannot display resource {positional_resource.resource} at {positional_resource.point}"
            )

        resource_handler = self._get_resource_handler_by(positional_resource)

        for surface in self.surfaces:
            resource_handler(
                positional_resource.resource,
                positional_resource.point,
                surface
            )

    def is_supported_resource(self, resource: any) -> bool:
        return type(resource) in self._resource_handler_by_resource_type.keys()

    def _get_resource_handler_by(self, positional_resource: PositionalRenderResource) -> IResourceHandler:
        return self._resource_handler_by_resource_type[type(positional_resource.resource)]

    @abstractmethod
    def _prepare_surface(self, surface: any) -> None:
        pass

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
