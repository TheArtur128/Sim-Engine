from abc import ABC, abstractmethod
from typing import Iterable, NewType, Optional, Callable

from pygame import *

from pygame_renders.errors import PygameEventHandlerError
from pygame_renders.resources import *
from simengine.interfaces import IUpdatable
from simengine.renders import Render, SurfaceKeeper, TypedResourceHandler, ResourcePack, resource_handler
from simengine.geometry import Vector
from simengine.tools import *


class PygameSurfaceRender(SurfaceKeeper, Render):
    _resource_handler_wrapper_factory = TypedResourceHandler

    def __init__(self, surfaces: Iterable[Surface, ], background_color: RGBAColor = RGBAColor()):
        super().__init__(surfaces)
        self.background_color = background_color

    def _clear_surface(self, surface: any) -> None:
        surface.fill(tuple(self.background_color))

    @resource_handler(Surface)
    def _handle_pygame_surface(resource_pack: ResourcePack, surface: Surface, render: 'PygameSurfaceRender') -> None:
        surface.blit(resource_pack.resource, resource_pack.point.coordinates)

    @resource_handler(Polygon)
    def _handle_pygame_polygon(resource_pack: ResourcePack, surface: Surface, render: 'PygameSurfaceRender') -> None:
        draw.polygon(
            surface,
            tuple(resource_pack.resource.color),
            tuple(
                (resource_pack.point + vector_to_point).coordinates
                for vector_to_point in resource_pack.resource.points
            ),
            resource_pack.resource.border_width
        )

    @resource_handler(Line)
    def _handle_pygame_line(resource_pack: ResourcePack, surface: Surface, render: 'PygameSurfaceRender') -> None:
        (draw.line if not resource_pack.resource.is_smooth else draw.aaline)(
            surface,
            tuple(resource_pack.resource.color),
            (resource_pack.resource.start_point + resource_pack.point).coordinates,
            (resource_pack.resource.end_point + resource_pack.point).coordinates,
            resource_pack.resource.border_width
        )

    @resource_handler(Lines)
    def _handle_pygame_lines(resource_pack: ResourcePack, surface: Surface, render: 'PygameSurfaceRender') -> None:
        (draw.lines if not resource_pack.resource.is_smooth else draw.aalines)(
            surface,
            tuple(resource_pack.resource.color),
            resource_pack.resource.is_closed,
            tuple(
                (line_point + resource_pack.point).coordinates
                for line_point in resource_pack.resource.points
            ),
            resource_pack.resource.border_width
        )

    @resource_handler(Circle)
    def _handle_pygame_circle(resource_pack: ResourcePack, surface: Surface, render: 'PygameSurfaceRender') -> None:
        draw.circle(
            surface,
            tuple(resource_pack.resource.color),
            resource_pack.point.coordinates,
            resource_pack.resource.radius,
            resource_pack.resource.border_width
        )

    @resource_handler(Rectangle)
    def _handle_pygame_rect(resource_pack: ResourcePack, surface: Surface, render: 'PygameSurfaceRender') -> None:
        draw.rect(
            surface,
            tuple(resource_pack.resource.color),
            (
                *resource_pack.point.coordinates,
                resource_pack.resource.width,
                resource_pack.resource.height
            ),
            resource_pack.resource.border_width
        )

    @resource_handler(Ellipse)
    def _handle_pygame_ellipse(resource_pack: ResourcePack, surface: Surface, render: 'PygameSurfaceRender') -> None:
        draw.ellipse(
            surface,
            tuple(resource_pack.resource.color),
            (
                *resource_pack.point.coordinates,
                resource_pack.resource.width,
                resource_pack.resource.height
            ),
            resource_pack.resource.border_width
        )

    @resource_handler(Arc)
    def _handle_pygame_arc(resource_pack: ResourcePack, surface: Surface, render: 'PygameSurfaceRender') -> None:
        draw.arc(
            surface,
            tuple(resource_pack.resource.color),
            (
                *resource_pack.point.coordinates,
                resource_pack.resource.width,
                resource_pack.resource.height
            ),
            resource_pack.resource.start_angle,
            resource_pack.resource.stop_angle,
            resource_pack.resource.border_width
        )


PygameEvent: NewType = object


class IPygameEventHandler(ABC):
    @abstractmethod
    def __call__(self, event: PygameEvent, controller: 'PygameEventController') -> None:
        pass

    @abstractmethod
    def is_support_handling_for(self, event: PygameEvent, controller: 'PygameEventController') -> bool:
        pass


class PygameEventHandler(IPygameEventHandler, ABC):
    def __call__(self, event: PygameEvent, controller: 'PygameEventController') -> None:
        if not self.is_support_handling_for(event, controller):
            raise PygameEventHandlerError(
                f"Event handler {self} doesn't support handling event {event} in controller {controller}"
            )

        self._handle(event, controller)

    @abstractmethod
    def _handle(self, event: PygameEvent, controller: 'PygameEventController') -> None:
        pass


class PygameEventHandlerWrapper(PygameEventHandler):
    def __init__(self, handlers: Iterable[IPygameEventHandler, ]):
        self.handlers = tuple(handlers)

    def _handle(self, event: PygameEvent, controller: 'PygameEventController') -> None:
        for handler in self.handlers:
            if handler.is_support_handling_for(event, controller):
                handler(event, controller)


class EventSupportStackHandler(IPygameEventHandler, ABC):
    _support_event_types: Iterable
    _support_keys: Optional[Iterable] = None
    _support_buttons: Optional[Iterable] = None
    _is_strict: bool = True

    def is_support_handling_for(self, event: PygameEvent, controller: 'PygameEventController') -> bool:
        return (all if self._is_strict else any)((
            (event.key in self._support_keys) if hasattr(event, 'key') else self._support_keys is None,
            (event.button in self._support_buttons) if hasattr(event, 'button') else self._support_buttons is None
        )) if event.type in self._support_event_types else False


class ExitEventHandler(PygameEventHandler, EventSupportStackHandler):
    _support_event_types = (QUIT, )

    def _handle(self, event: PygameEvent, controller: 'PygameEventController') -> None:
        exit()


class IPygameEventGetter(ABC):
    @abstractmethod
    def get(self) -> Iterable[PygameEvent]:
        pass


class PygameEventController(LoopHandler):
    _event_getter: IPygameEventGetter

    def __init__(self, loop: HandlerLoop, handlers: Iterable[PygameEventHandler]):
        super().__init__(loop)
        self.handlers = tuple(handlers)

    def update(self) -> None:
        for event_ in self._event_getter.get():
            self._handle_event(event_)

    def _handle_event(self, event: PygameEvent) -> None:
        for event_handler in self.handlers:
            if event_handler.is_support_handling_for(event, self):
                event_handler(event, self)


class SyncPygameEventController(PygameEventController):
    _event_getter = event


class PygameDisplayUpdater(LoopHandler):
    def update(self) -> None:
        display.flip()


class PygameClockSleepLoopHandler(TicksSleepLoopHandler, AlwaysReadyForSleepLoopHandler):
    _clock_factory: Callable[['PygameClockSleepLoopHandler'], time.Clock] = CustomFactory(
        lambda pygame_sleep_handler: time.Clock()
    )

    def __init__(self, loop: HandlerLoop, ticks_to_sleep: int | float):
        super().__init__(loop, ticks_to_sleep)
        self._pygame_clock = self._clock_factory(self)

    def _sleep_function(self, ticks_to_sleep: int | float) -> None:
        self._pygame_clock.tick(self.ticks_to_sleep)
