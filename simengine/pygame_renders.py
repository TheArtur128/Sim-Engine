from typing import Iterable, NewType

from pygame import *

from core import *
from interfaces import IUpdatable, ILoopFactory
from renders import Render, SurfaceKeeper, TypedResourceHandler, ResourcePack
from geometry import Vector
from pygame_resources import *
from tools import StoppingLoopUpdater, RGBAColor, LoopUpdater, CustomLoopFactory


class PygameSurfaceRender(SurfaceKeeper, Render):
    _resource_handler_wrapper_factory = TypedResourceHandler

    def __init__(self, surfaces: Iterable[Surface, ], background_color: RGBAColor = RGBAColor()):
        super().__init__(surfaces)
        self.background_color = background_color

    def _clear_surface(self, surface: any) -> None:
        surface.fill(tuple(self.background_color))

    @Render.resource_handler(supported_resource_type=Surface)
    def _handle_pygame_surface(resource_pack: ResourcePack, surface: Surface, render: 'PygameSurfaceRender') -> None:
        surface.blit(resource_pack.resource, resource_pack.point.coordinates)

    @Render.resource_handler(supported_resource_type=Polygon)
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

    @Render.resource_handler(supported_resource_type=Line)
    def _handle_pygame_line(resource_pack: ResourcePack, surface: Surface, render: 'PygameSurfaceRender') -> None:
        (draw.line if not resource_pack.resource.is_smooth else draw.aaline)(
            surface,
            tuple(resource_pack.resource.color),
            (resource_pack.resource.start_point + resource_pack.point).coordinates,
            (resource_pack.resource.end_point + resource_pack.point).coordinates,
            resource_pack.resource.border_width
        )

    @Render.resource_handler(supported_resource_type=Lines)
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

    @Render.resource_handler(supported_resource_type=Circle)
    def _handle_pygame_circle(resource_pack: ResourcePack, surface: Surface, render: 'PygameSurfaceRender') -> None:
        draw.circle(
            surface,
            tuple(resource_pack.resource.color),
            resource_pack.point.coordinates,
            resource_pack.resource.radius,
            resource_pack.resource.border_width
        )

    @Render.resource_handler(supported_resource_type=Rectangle)
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

    @Render.resource_handler(supported_resource_type=Ellipse)
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

    @Render.resource_handler(supported_resource_type=Arc)
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
    def __call__(self, event: PygameEvent, loop: 'PygameLoopUpdater') -> None:
        pass

    @abstractmethod
    def is_support_handling_for(self, event: PygameEvent, loop: 'PygameLoopUpdater') -> bool:
        pass


class PygameEventHandler(IPygameEventHandler, ABC):
    def __call__(self, event: PygameEvent, loop: 'PygameLoopUpdater') -> None:
        if not self.is_support_handling_for(event, loop):
            raise PygameEventHandlerError(
                f"Event handler {self} doesn't support handling event {event} in loop {loop}"
            )

        self._handle(event, loop)

    @abstractmethod
    def _handle(self, event: PygameEvent, loop: 'PygameLoopUpdater') -> None:
        pass


class PygameEventHandlerWrapper(PygameEventHandler):
    def __init__(self, handlers: Iterable[IPygameEventHandler, ]):
        self.handlers = tuple(handlers)

    def _handle(self, event: PygameEvent, loop: 'PygameLoopUpdater') -> None:
        for handler in self.handlers:
            if handler.is_support_handling_for(event, loop):
                handler(event, loop)


class EventSupportStackHandler(IPygameEventHandler, ABC):
    _support_event_types: Iterable
    _support_keys: Optional[Iterable] = None
    _support_buttons: Optional[Iterable] = None
    _is_strict: bool = True

    def is_support_handling_for(self, event: PygameEvent, loop: 'PygameLoopUpdater') -> bool:
        return (all if self._is_strict else any)((
            (event.key in self._support_keys) if hasattr(event, 'key') else self._support_keys is None,
            (event.button in self._support_buttons) if hasattr(event, 'button') else self._support_buttons is None
        )) if event.type in self._support_event_types else False


class ExitEventHandler(PygameEventHandler, EventSupportStackHandler):
    _support_event_types = (QUIT, )

    def _handle(self, event: PygameEvent, loop: 'PygameLoopUpdater') -> None:
        exit()


class PygameLoopUpdater(StoppingLoopUpdater):
    _clock_factory: Callable[['PygameLoopUpdater'], time.Clock] = CustomFactory(
        lambda pygame_loop: time.Clock()
    )

    def __init__(
        self,
        units: Iterable[IUpdatable, ],
        keyboard_controller: PygameKeyboardController,
        fps: int | float
    ):
        super().__init__(units)
        self.keyboard_controller = keyboard_controller
        self.fps = fps
        self._pygame_clock = self._clock_factory(self)

    def _handle(self) -> None:
        self.keyboard_controller(self)
        super()._handle()
        display.flip()

    def _stop(self) -> None:
        self._pygame_clock.tick(self.fps)


class PygameLoopFactory(ILoopFactory):
    _loop_factory: ILoopFactory = PygameLoopUpdater

    def __init__(self, keyboard_controller: PygameKeyboardController, fps: int | float):
        self.fps = fps
        self.keyboard_controller = keyboard_controller

    def __call__(self, units: Iterable[IUpdatable, ]) -> LoopUpdater:
        return self._loop_factory(units, self.keyboard_controller, self.fps)


if __name__ == '__main__':
    class TestUnit(PositionalUnit):
        _avatar_factory = lambda unit: PrimitiveAvatar(unit, None)

        def update(self) -> None:
            pass


    unit = TestUnit(Vector((320, 240)))
    unit.avatar.render_resource = Circle(RGBAColor(), 20)

    CustomAppFactory(PygameLoopFactory(PygameKeyboardController(), 30))(
        CustomWorld(
            [unit],
            [UnitUpdater, RenderResourceParser]
        ),
        (
            PygameSurfaceRender(
                (display.set_mode((640, 480)), ),
                RGBAColor(232, 232, 232)
            ),
        )
    ).run()
