from abc import ABC, abstractmethod, ABCMeta
from dataclasses import dataclass
from typing import Callable, Iterable, Optional, Generator, Self
from os import get_terminal_size

from beautiful_repr import StylizedMixin, Field
from colorama import Style

from simengine.geometry import Vector
from simengine.interfaces import IUpdatable, IRenderRersourceKeeper, IAvatar, IRenderActivatorFactory
from simengine.errors.render_errors import UnsupportedResourceError
from simengine.tools import ReportAnalyzer, BadReportHandler, Report, Arguments, CustomArgumentFactory, get_collection_with_reduced_nesting_level_by


@dataclass
class ResourcePack:
    """
    Dataclass for transport representation of atomic data for rendering in
    positional form.

    Has two attributes: resource - data to render and point - position to render
    the resource.
    """

    resource: any
    point: any


@dataclass
class StylishResourcePack(ResourcePack):
    """ResourcePack dataclass with style annotation."""

    style: any


class IRenderResourceHandler(ABC):
    """Resource pack handler interface in conjunction with surface and render."""

    @abstractmethod
    def __call__(self, resource_pack: ResourcePack, surface: any, render: 'BaseRender') -> None:
        """Resource pack handling method with an environment."""


class RenderResourceHandler(IRenderResourceHandler, ABC):
    """
    Base class that template implements the RenderResourceHandler interface.

    Templates the main handling method by analyzing the processing support of
    a pack and its environment.
    """

    _report_analyzer = ReportAnalyzer(
        (BadReportHandler(UnsupportedResourceError, "Resource Handler can't handle resource"), )
    )

    def __call__(self, resource_pack: ResourcePack, surface: any, render: 'BaseRender') -> None:
        self._report_analyzer(self.is_support_to_handle(resource_pack, surface, render))
        self._handle(resource_pack, surface, render)

    def is_support_to_handle(self, resource_pack: ResourcePack, surface: any, render: 'BaseRender') -> Report:
        """Method for obtaining analysis of handling conditions."""

        return Report(True)

    @abstractmethod
    def _handle(self, resource_pack: ResourcePack, surface: any, render: 'BaseRender') -> None:
        """Unconditional Packet handling method."""


class ResourceHandlerWrapper(RenderResourceHandler, StylizedMixin):
    """RenderResourceHandler delegating handling to another RenderResourceHandler."""

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
    def create_decorator_by(cls, *args, **kwargs) -> Callable[[IRenderResourceHandler], Self]:
        """Decorator creation method to create ResourceHandlerWrapper via @."""

        def decorator(resource_handler: IRenderResourceHandler):
            return cls(resource_handler, *args, **kwargs)

        return decorator


class TypedResourceHandler(ResourceHandlerWrapper):
    """Resource Handler Wrapper using types as handling conditions."""

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
    """Render interface for rendering data from resource packs."""

    @abstractmethod
    def __call__(self, resource_pack: ResourcePack) -> None:
        """Native method of rendering a single render pack."""

    @abstractmethod
    def draw_resource_pack(self, resource_pack: ResourcePack) -> None:
        """Render pack drawing method."""

    @abstractmethod
    def draw_scene(self, resource_packs: Iterable[ResourcePack]) -> None:
        """Method for rendering an entire scene from resource packs."""

    @abstractmethod
    def clear_surfaces(self) -> None:
        """Method that allows you to clear surfaces from rendered entities."""


class BaseRender(IRender, ABC):
    """Class that abstractly implements the Render interface."""

    @property
    @abstractmethod
    def surfaces(self) -> tuple:
        """Property of surfaces used by the render."""

    def __call__(self, resource_pack: ResourcePack) -> None:
        self.draw_resource_pack(resource_pack)

    def draw_scene(self, resource_packs: Iterable[ResourcePack]) -> None:
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
        """Atomic rendering method resource packs on the surface."""

    @abstractmethod
    def _clear_surface(self, surface: any) -> None:
        """Atomic single surface cleaning method."""


class ResourceHandlingChainMeta(ABCMeta):
    """
    Metaclass for collecting resource handlers from a class at the time of
    creation of this very class.

    Gathers handlers in _resource_handlers attribute.
    """

    _resource_handlers: Optional[tuple]

    def __new__(cls, class_name: str, super_classes: tuple, attributes: dict):
        render_type = super().__new__(cls, class_name, super_classes, attributes)

        render_type._resource_handlers = (
            tuple(render_type.__get_resource_handlers_from(attributes))
            + render_type._get_resource_handlers_of_parents()
        )

        return render_type

    @staticmethod
    def resource_handler(
        *args_for_factory,
        wrapper_factory: Optional[ResourceHandlerWrapper] = None,
        **kwargs_for_factory,
    ) -> Callable[[IRenderResourceHandler], ResourceHandlerWrapper]:
        """Decorator for system adding a resource handler to a class."""

        def decorator(resource_handler: IRenderResourceHandler) -> ResourceHandlerWrapper | Arguments:
            # Arguments here to initialize handler by metaclass
            return (wrapper_factory if wrapper_factory else Arguments.create_via_call)(
                resource_handler,
                *args_for_factory,
                **kwargs_for_factory
            )

        return decorator

    def _get_resource_handlers_of_parents(cls) -> tuple[IRenderResourceHandler]:
        """Method for collecting all available handlers in the inheritance tree."""

        return sum(
            tuple(
                parent_type._resource_handlers for parent_type in cls.__bases__
                if hasattr(parent_type, '_resource_handlers')
            ),
            tuple()
        )

    def __get_resource_handlers_from(cls, attributes: dict) -> Generator[IRenderResourceHandler, any, None]:
        """Method for collecting handlers from attribute space."""

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


resource_handler = ResourceHandlingChainMeta.resource_handler


class Render(BaseRender, ABC, metaclass=ResourceHandlingChainMeta):
    """BaseRender child class that delegates rendering of packs to pack handlers."""

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


class ConsoleCell:
    """Console cell view class. Stores the immediate content and its style."""

    def __init__(self, sign: str, style: Iterable[str] = tuple()):
        self.sign = sign
        self.style = style

    def __str__(self) -> str:
        return str().join((self.style, self.sign, Style.RESET_ALL if self.style else ''))

    @property
    def sign(self) -> str:
        """Cell content property."""

        return self.__sign

    @sign.setter
    def sign(self, sign: str) -> None:
        self.__sign = sign[:1]

    @property
    def style(self) -> str:
        """
        Cell style property.
        By definition, be an ANSI code or something based on it.
        """

        return self.__style

    @style.setter
    def style(self, style: Iterable[str]) -> None:
        self.__style = str().join(style)


class ConsoleScene:
    """
    Content class of the active console \"frame\".
    Stores data as a two-dimensional missive.
    """

    def __init__(self, size: Iterable[int], default_empty_cell: ConsoleCell):
        self.reset(size, default_empty_cell)

    def __str__(self) -> str:
        return str().join(map(str, get_collection_with_reduced_nesting_level_by(3, self.__cell_table)))

    @property
    def default_empty_cell(self) -> ConsoleCell:
        """Cell property defining all unoccupied."""

        return self.__default_empty_cell

    @default_empty_cell.setter
    def default_empty_cell(self, default_empty_cell: ConsoleCell) -> None:
        for y in range(size[1]):
            for x in range(size[0]):
                if self[(x, y)] is self.__default_empty_cell:
                    self[(x, y)] = default_empty_cell

        self.__default_empty_cell = default_empty_cell

    @property
    def size(self) -> tuple[int, int]:
        """Scene size as 2D array size."""

        return self.__size

    @size.setter
    def size(self, size: Iterable[int]) -> None:
        if size[1] < self.__size[1]:
            self.__cell_table[size[1] - 1:] = tuple()

        if size[0] > self.__size[0]:
            for column in self.__cell_table:
                column.extend((self.default_empty_cell, ) * (size[0] - self.__size[0]))
        elif size[0] < self.__size[0]:
            for column in self.__cell_table:
                column[size[0] - 1:] = tuple()

        if size[1] > self.__size[1]:
            self.__cell_table.extend((self.default_empty_cell, ) * size[0])

        self.__size = tuple(size)

    def __getitem__(self, key: Iterable[int]) -> ConsoleCell:
        return self.__cell_table[key[1]][key[0]]

    def __setitem__(self, key: Iterable[int], value: ConsoleCell) -> None:
        if key[0] < self.size[0] and key[1] < self.size[1]:
            self.__cell_table[key[1]][key[0]] = value

    def reset(self, size: Optional[Iterable[int]] = None, default_empty_cell: Optional[ConsoleCell] = None) -> None:
        """Scene data reset and override method."""

        self.__size = tuple(size) if size is not None else self.__size

        self.__default_empty_cell = (
            default_empty_cell if default_empty_cell is not None
            else self.__default_empty_cell
        )

        self.__cell_table = [
            [self.__default_empty_cell] * self.__size[0]
            for _ in range(self.__size[1])
        ]


class ConsoleRender(IRender):
    """
    Console rendering class.

    In the absence of access to the console by the system or due to some other
    reason, it can still be active, but without any results. Not designed for
    high fps rendering since the console may flash in the first and last line
    due to slow output (relative to the difference in time between two \"frames\")
    to this very console.

    Accepts strings and a ConsoleCell as atomic render data.
    """

    def __init__(
        self,
        empty_cell: ConsoleCell,
        default_filled_cell: ConsoleCell = ConsoleCell('#')
    ):
        self.default_filled_cell = default_filled_cell
        self.__scene = ConsoleScene(self._console_size, empty_cell)

    @property
    def empty_cell(self) -> ConsoleCell:
        """Cell property that defines unoccupied other cells."""

        return self.__scene.default_empty_cell

    @empty_cell.setter
    def empty_cell(self, empty_cell: ConsoleCell) -> None:
        self.__scene.default_empty_cell = empty_cell

    def __call__(self, resource_pack: ResourcePack) -> None:
        self.draw_resource_pack(resource_pack)

    def draw_resource_pack(self, resource_pack: ResourcePack) -> None:
        self._insert_resource_pack_into_scene(resource_pack)
        self._draw_current_scene()

    def draw_scene(self, resource_packs: Iterable[ResourcePack]) -> None:
        self._clear_scene()

        for resource_pack in resource_packs:
            self._insert_resource_pack_into_scene(resource_pack)

        self._draw_current_scene()

    def clear_surfaces(self) -> None:
        self._clear_scene()

    @property
    def _scene(self) -> ConsoleScene:
        """Active render scene property."""

        return self.__scene

    @property
    def _console_size(self) -> tuple[int, int]:
        """Real size property of the console."""

        try:
            terminal_size = get_terminal_size()
            return (terminal_size.columns, terminal_size.lines - 1)
        except OSError:
            return (0, 0)

    def _draw_current_scene(self) -> None:
        """Method for outputting a saved frame to the console."""

        if all(self.__scene.size):
            print('\n' + str(self.__scene))

    def _clear_scene(self) -> None:
        """Method for clearing the active frame from all elements lying on it."""

        self.__scene.reset(self._console_size)

    def _insert_resource_pack_into_scene(self, resource_pack: ResourcePack) -> None:
        """Method for inserting data from the resource pack into the active frame."""

        resource_pack = self._get_usable_resource_pack(resource_pack)

        self.__scene[resource_pack.point] = str(resource_pack.resource)

    def _get_usable_resource_pack(self, resource_pack: ResourcePack) -> ResourcePack:
        """Method for getting the given resource pack into the correct form for rendering."""

        return ResourcePack(
            resource=self._get_usable_cell_from(resource_pack),
            point=tuple(map(
                int,
                (
                    resource_pack.point.coordinates[:2]
                    if isinstance(resource_pack.point, Vector) else resource_pack.point
                )
            ))
        )

    def _get_usable_cell_from(self, resource_pack: ResourcePack) -> ConsoleCell:
        """
        Atomic method for converting data from a resource pack into the correct
        form of ConsoleCell.
        """

        sign = None
        style = None

        if isinstance(resource_pack.resource, ConsoleCell):
            sign = resource_pack.resource.sign
            if resource_pack.resource.style:
                style = resource_pack.resource.style
        else:
            if hasattr(resource_pack, 'style') and isinstance(resource_pack.style, str) and resource_pack.style:
                style = resource_pack.style

            sign = (
                resource_pack.resource
                if isinstance(resource_pack.resource, str) and resource_pack.resource
                else self.default_filled_cell.sign
            )

        if not style:
            style = self.default_filled_cell.style

        return ConsoleCell(sign, style)


class RenderActivator(IUpdatable):
    """
    Unit class that activates the rendering of scenes from resource packs.

    Gets packages from input render_resource_keepers and delegates rendering to
    input renders.
    """

    def __init__(self, render_resource_keepers: Iterable[IRenderRersourceKeeper], renders: Iterable[Render]):
        self.render_resource_keepers = render_resource_keepers
        self.renders = tuple(renders)

    def update(self) -> None:
        for render in self.renders:
            render.draw_scene(self._get_render_resource_packs())

    def _get_render_resource_packs(self) -> Generator[ResourcePack, any, None]:
        """Method to get all resource packs from stored render resource keepers."""

        for keeper in self.render_resource_keepers:
            yield from keeper.render_resource_packs


class CustomRenderActivatorFactory(CustomArgumentFactory, IRenderActivatorFactory):
    """Class of factory render activators."""

    def __call__(
        self,
        render_resource_keepers: Iterable[IRenderRersourceKeeper],
        redners: Iterable[Render],
        *args,
        **kwargs
    ) -> RenderActivator:
        return super().__call__(render_resource_keepers, redners, *args, **kwargs)
