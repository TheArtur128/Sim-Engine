from typing import Iterable, NewType

from pygame import *

from core import *
from interfaces import IUpdatable, ILoopFactory
from renders import Render, SurfaceKeeper, TypedResourceHandler, ResourcePack
from geometry import Vector
from pygame_resources import *
from errors.pygame_render_errors import PygameEventHandlerError
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
        event_handlers: Iterable[PygameEventHandler, ],
        fps: int | float
    ):
        super().__init__(units)
        self.fps = fps
        self.event_handlers = tuple(event_handlers)
        self._pygame_clock = self._clock_factory(self)

    def _handle(self) -> None:
        for event_ in event.get():
            self._handle_event(event_)

        super()._handle()
        display.flip()

    def _handle_event(self, event: PygameEvent) -> None:
        for event_handler in self.event_handlers:
            if event_handler.is_support_handling_for(event, self):
                event_handler(event, self)

    def _stop(self) -> None:
        self._pygame_clock.tick(self.fps)


class PygameLoopFactory(CustomLoopFactory):
    factory = PygameLoopUpdater


if __name__ == '__main__':
    class MainHeroManagement(PygameEventHandler, EventSupportStackHandler):
        _right_movement_keys = (K_RIGHT, K_d)
        _left_movement_keys = (K_LEFT, K_a)
        _up_movement_keys = (K_UP, K_w)
        _down_movement_keys = (K_DOWN, K_s)

        _support_keys = (
            *_right_movement_keys,
            *_left_movement_keys,
            *_up_movement_keys,
            *_down_movement_keys
        )
        _support_event_types = (KEYDOWN, )

        def __init__(self, main_hero: InfinitelyImpulseUnit):
            self.main_hero = main_hero

        def _handle(self, event: PygameEvent, loop: PygameLoopUpdater) -> None:
            impulse = Vector((0, 0))

            if event.key in self._right_movement_keys:
                impulse += Vector((self.main_hero.speed, 0))
            if event.key in self._left_movement_keys:
                impulse -= Vector((self.main_hero.speed, 0))

            if event.key in self._up_movement_keys:
                impulse -= Vector((0, self.main_hero.speed))
            if event.key in self._down_movement_keys:
                impulse += Vector((0, self.main_hero.speed))

            self.main_hero.impulse = impulse


    class TestUnit(SpeedKeeperMixin, InfinitelyImpulseUnit):
        _avatar_factory = CustomFactory(lambda unit: PrimitiveAvatar(unit, None))
        _speed = 2

        def update(self) -> None:
            pass


    class ObserveUnitAvatar(ResourceAvatar):
        _resource_factory = CustomFactory(lambda _: Circle(RGBAColor(255, 0, 50), 0))

        def update(self) -> None:
            super().update()
            vector_to_observed_unit = self.unit.position - self.unit.observed_unit.position
            self.render_resource.radius = vector_to_observed_unit.length


    class ObserveUnit(SpeedKeeperMixin, ImpulseUnit):
        _avatar_factory = ObserveUnitAvatar
        _speed = 1

        def __init__(self, position: Vector, observed_unit: PositionalUnit):
            super().__init__(position)
            self.observed_unit = observed_unit

        def update(self) -> None:
            vector_to_observed_unit = Vector(
                (self.observed_unit.position - self.position).coordinates
            )
            self.impulse = vector_to_observed_unit / (
                (vector_to_observed_unit.length / self.speed)
                if vector_to_observed_unit.length else 1
            )


    black_unit = TestUnit(Vector((200, 240)))
    black_unit.avatar.render_resource = Circle(RGBAColor(), 20)

    red_unit = ObserveUnit(Vector((100, 240)), black_unit)

    CustomAppFactory(PygameLoopFactory([ExitEventHandler(), MainHeroManagement(black_unit)], 30))(
        CustomWorld(
            [black_unit, red_unit],
            [UnitUpdater, UnitMover, RenderResourceParser]
        ),
        (
            PygameSurfaceRender(
                (display.set_mode((640, 480)), ),
                RGBAColor(232, 232, 232)
            ),
        )
    ).run()
