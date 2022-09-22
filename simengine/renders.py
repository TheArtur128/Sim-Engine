from abc import ABC, abstractmethod, ABCMeta
from dataclasses import dataclass
from typing import Callable, Iterable, Optional, Generator

from beautiful_repr import StylizedMixin, Field

from geometry import Vector
from interfaces import IUpdatable
from errors.render_errors import UnsupportedResourceError
from tools import ReportAnalyzer, BadReportHandler, Report, Arguments


@dataclass
class ResourcePack:
    resource: any
    point: any


class IRenderRersourceKeeper(ABC):
    @property
    @abstractmethod
    def render_resource_packs(self) -> tuple[ResourcePack, ]:
        pass


class IAvatar(IUpdatable, IRenderRersourceKeeper, ABC):
    pass


class IRenderResourceHandler(ABC):
    @abstractmethod
    def __call__(self, resource_pack: ResourcePack, surface: any, render: 'BaseRender') -> None:
        pass


class RenderResourceHandler(IRenderResourceHandler, ABC):
    _report_analyzer = ReportAnalyzer(
        (BadReportHandler(UnsupportedResourceError, "Resource Handler can't handle resource"), )
    )

    def __call__(self, resource_pack: ResourcePack, surface: any, render: 'BaseRender') -> None:
        self._report_analyzer(self.is_support_to_handle(resource_pack, surface, render))
        self._handle(resource_pack, surface, render)

    def is_support_to_handle(self, resource_pack: ResourcePack, surface: any, render: 'BaseRender') -> Report:
        return Report(True)

    @abstractmethod
    def _handle(self, resource_pack: ResourcePack, surface: any, render: 'BaseRender') -> None:
        pass


class ResourceHandlerWrapper(RenderResourceHandler, StylizedMixin):
    _repr_fields = (Field('resource_handler'), )

    def __init__(self, resource_handler: IRenderResourceHandler):
        self.resource_handler = resource_handler

    def is_support_to_handle(self, resource_pack: ResourcePack, surface: any, render: 'BaseRender') -> Report:
        return (
            self.resource_handler.is_support_to_handle(resource_pack, surface, render)
            if hasattr(self.resource_handler, 'is_support_to_handle') else Report(True)
        )

    def _handle(self, resource_pack: ResourcePack, surface: any, render: 'BaseRender') -> None:
        self.resource_handler(resource_pack, surface, render)

    @classmethod
    def create_decorator_by(cls, *args, **kwargs) -> Callable[[], 'ResourceHandlerWrapper']:
        def decorator(resource_handler: IRenderResourceHandler):
            return cls(resource_handler, *args, **kwargs)

        return decorator


class TypedResourceHandler(ResourceHandlerWrapper):
    _repr_fields = (Field(
        'supported_resource_type',
        value_getter=lambda handler, _: handler.supported_resource_type.__name__
    ), )

    def __init__(self, resource_handler: IRenderResourceHandler, supported_resource_type: type):
        super().__init__(resource_handler)
        self.supported_resource_type = supported_resource_type

    def is_support_to_handle(self, resource_pack: ResourcePack, surface: any, render: 'BaseRender') -> Report:
        return (
            Report(isinstance(resource_pack.resource, self.supported_resource_type)) and
            super().is_support_to_handle(resource_pack, surface, render)
        )


class IRender(ABC):
    @abstractmethod
    def __call__(self, resource_pack: ResourcePack) -> None:
        pass

    @abstractmethod
    def draw_resource_pack(self, resource_pack: ResourcePack) -> None:
        pass

    @abstractmethod
    def draw_scene(self, resource_packs: Iterable[ResourcePack, ]) -> None:
        pass

    @abstractmethod
    def clear_surfaces(self) -> None:
        pass


class BaseRender(IRender, ABC):
    @property
    @abstractmethod
    def surfaces(self) -> tuple:
        pass

    def __call__(self, resource_pack: ResourcePack) -> None:
        self.draw_resource_pack(resource_pack)

    def draw_scene(self, resource_packs: Iterable[ResourcePack, ]) -> None:
        for surface in self.surfaces:
            self._clear_surface(surface)

            for resource_pack in resource_packs:
                self._draw_resource_pack_on(surface, resource_pack)

    def draw_resource_pack(self, resource_pack: ResourcePack) -> None:
        for surface in self.surfaces:
            self._draw_resource_pack_on(surface, resource_pack)

    def clear_surfaces(self) -> None:
        for surface in self.surfaces:
            self._clear_surface(surface)

    @abstractmethod
    def _draw_resource_pack_on(self, surface: any, resource_pack: ResourcePack) -> None:
        pass

    @abstractmethod
    def _clear_surface(self, surface: any) -> None:
        pass


class ResourceHandlingChainMeta(ABCMeta):
    def __new__(cls, class_name: str, super_classes: tuple, attributes: dict):
        render_type = super().__new__(cls, class_name, super_classes, attributes)

        render_type._resource_handlers = (
            tuple(render_type.__get_resource_handlers_from(attributes)) +
            render_type._get_resource_handlers_of_parents()
        )

        return render_type

    @staticmethod
    def resource_handler(
        wrapper_factory: Optional[ResourceHandlerWrapper] = None,
        *args_for_factory,
        **kwargs_for_factory,
    ) -> Callable[[IRenderResourceHandler], ResourceHandlerWrapper]:
        def decorator(resource_handler: IRenderResourceHandler) -> ResourceHandlerWrapper | Arguments:
            # Arguments here to initialize handler by metaclass
            return (wrapper_factory if wrapper_factory else Arguments.create_via_call)(
                resource_handler,
                *args_for_factory,
                **kwargs_for_factory
            )

        return decorator

    def _get_resource_handlers_of_parents(cls) -> tuple[IRenderResourceHandler, ]:
        return sum(
            tuple(
                parent_type._resource_handlers for parent_type in cls.__bases__
                if hasattr(parent_type, '_resource_handlers')
            ),
            tuple()
        )

    def __get_resource_handlers_from(cls, attributes: dict) -> Generator[IRenderResourceHandler, any, None]:
        for attribute_name, attribute_value in attributes.items():
            if isinstance(attribute_value, RenderResourceHandler):
                yield attribute_value
            elif isinstance(attribute_value, Arguments):
                resource_handler = cls._resource_handler_wrapper_factory(
                    *attribute_value.args,
                    **attribute_value.kwargs
                )
                setattr(cls, attribute_name, resource_handler)
                yield resource_handler


class Render(BaseRender, ABC, metaclass=ResourceHandlingChainMeta):
    _resource_handler_wrapper_factory = ResourceHandlerWrapper

    def _draw_resource_pack_on(self, surface: any, resource_pack: ResourcePack) -> None:
        for resource_handler in self._resource_handlers:
            if resource_handler.is_support_to_handle(resource_pack, surface, self):
                resource_handler(resource_pack, surface, self)


class SurfaceKeeper:
    """Stub class for classes inheriting from Render."""

    def __init__(self, surfaces: Iterable):
        self._surfaces = tuple(surfaces)

    @property
    def surfaces(self) -> tuple:
        return self._surfaces


class RenderActivator(IUpdatable):
    def __init__(self, render_resource_keeper: IRenderRersourceKeeper, renders: Iterable[Render, ]):
        self.render_resource_keeper = render_resource_keeper
        self.renders = tuple(renders)

    def update(self) -> None:
        for render in self.renders:
            render.draw_scene(self.render_resource_keeper.render_resource_packs)
