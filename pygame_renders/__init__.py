from abc import ABC, abstractmethod
from typing import Iterable, NewType, Optional, Callable, Self

from pygame import *

from pygame_renders.errors import PygameEventHandlerError
from pygame_renders.resources import *
from simengine.interfaces import IUpdatable
from simengine.renders import Render, SurfaceKeeper, TypedResourceHandler, ResourcePack, resource_handler
from simengine.geometry import Vector
from simengine.tools import *


class PygameSurfaceRender(SurfaceKeeper, Render):
    """
    Pygame surface render class.

    Uses pygame render function attribute representations as a function definer
    with appropriate attributes.
    """

    _resource_handler_wrapper_factory = TypedResourceHandler

    def __init__(self, surfaces: Iterable[Surface], background_color: RGBAColor = RGBAColor()):
        super().__init__(surfaces)
        self.background_color = background_color

    def _clear_surface(self, surface: any) -> None:
        surface.fill(tuple(self.background_color))

    @resource_handler(Surface)
    def _handle_pygame_surface(resource_pack: ResourcePack, surface: Surface, render: Self) -> None:
        surface.blit(resource_pack.resource, resource_pack.point.coordinates)

    @resource_handler(PygamePolygon)
    def _handle_pygame_polygon(resource_pack: ResourcePack, surface: Surface, render: Self) -> None:
        draw.polygon(
            surface,
            tuple(resource_pack.resource.color),
            tuple(
                (resource_pack.point + vector_to_point).coordinates
                for vector_to_point in resource_pack.resource.points
            ),
            resource_pack.resource.border_width
        )

    @resource_handler(PygameLine)
    def _handle_pygame_line(resource_pack: ResourcePack, surface: Surface, render: Self) -> None:
        (draw.line if not resource_pack.resource.is_smooth else draw.aaline)(
            surface,
            tuple(resource_pack.resource.color),
            (resource_pack.resource.start_point + resource_pack.point).coordinates,
            (resource_pack.resource.end_point + resource_pack.point).coordinates,
            resource_pack.resource.border_width
        )

    @resource_handler(PygameLines)
    def _handle_pygame_lines(resource_pack: ResourcePack, surface: Surface, render: Self) -> None:
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

    @resource_handler(PygameCircle)
    def _handle_pygame_circle(resource_pack: ResourcePack, surface: Surface, render: Self) -> None:
        draw.circle(
            surface,
            tuple(resource_pack.resource.color),
            resource_pack.point.coordinates,
            resource_pack.resource.radius,
            resource_pack.resource.border_width
        )

    @resource_handler(PygameRectangle)
    def _handle_pygame_rect(resource_pack: ResourcePack, surface: Surface, render: Self) -> None:
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

    @resource_handler(PygameEllipse)
    def _handle_pygame_ellipse(resource_pack: ResourcePack, surface: Surface, render: Self) -> None:
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

    @resource_handler(PygameArc)
    def _handle_pygame_arc(resource_pack: ResourcePack, surface: Surface, render: Self) -> None:
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
    """Pygame event handler interface."""

    @abstractmethod
    def __call__(self, event: PygameEvent, controller: 'PygameEventController') -> None:
        """Handling logic start method."""

    @abstractmethod
    def is_support_handling_for(self, event: PygameEvent, controller: 'PygameEventController') -> bool:
        """Method for reporting a possible handling call."""


class PygameEventHandler(IPygameEventHandler, ABC):
    """Implementing the PygameEventHandler Interface."""

    def __call__(self, event: PygameEvent, controller: 'PygameEventController') -> None:
        if not self.is_support_handling_for(event, controller):
            raise PygameEventHandlerError(
                f"Event handler {self} doesn't support handling event {event} in controller {controller}"
            )

        self._handle(event, controller)

    @abstractmethod
    def _handle(self, event: PygameEvent, controller: 'PygameEventController') -> None:
        """Event handling logic method."""


class PygameEventHandlerWrapper(PygameEventHandler):
    """
    Pygame Event Handler class allows you to operate multiple handlers as a
    single object.
    """

    def __init__(self, handlers: Iterable[IPygameEventHandler]):
        self.handlers = tuple(handlers)

    def _handle(self, event: PygameEvent, controller: 'PygameEventController') -> None:
        for handler in self.handlers:
            if handler.is_support_handling_for(event, controller):
                handler(event, controller)


class EventSupportStackHandler(IPygameEventHandler, ABC):
    """
    Implementation of the PygameEventHandler interface with automatic support for
    determining support for event handling by configured attributes.
    """

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
    """PygameEventHandler class that handles the exit event with appropriate logic."""

    _support_event_types = (QUIT, )

    def _handle(self, event: PygameEvent, controller: 'PygameEventController') -> None:
        exit()


class IPygameEventGetter(ABC):
    """Pygame keeper interface."""

    @abstractmethod
    def get(self) -> Iterable[PygameEvent]:
        """Method to get events."""


class PygameEventController(LoopHandler):
    """
    LoopHandler class delegating the handling of pygame events.

    Gets events using the event getter and delegates them to input event handlers.
    """

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
    """Pygame Event Controller class using the standard pygame event store."""

    _event_getter = event


class PygameDisplayUpdater(LoopHandler):
    """LoopHandler class that updates the main window created by pygame."""

    def update(self) -> None:
        display.flip()


class PygameClockSleepLoopHandler(TicksSleepLoopHandler, AlwaysReadyForSleepLoopHandler):
    """TicksSleepLoopHandler class that implements waiting through pygame clock."""

    _clock_factory: Callable[[Self], time.Clock] = CustomFactory(
        lambda pygame_sleep_handler: time.Clock()
    )

    def __init__(self, loop: HandlerLoop, ticks_to_sleep: int | float):
        super().__init__(loop, ticks_to_sleep)
        self._pygame_clock = self._clock_factory(self)

    def _sleep_function(self, ticks_to_sleep: int | float) -> None:
        self._pygame_clock.tick(self.ticks_to_sleep)
