from pygame import *

from core import *
from pygame_renders import *


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
