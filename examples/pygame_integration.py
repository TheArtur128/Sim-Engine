from pygame import *
from random import randint, choice

from sim32.avatars import ResourceAvatar, PrimitiveAvatar
from sim32.core import *
from sim32.tools import Timer
from sim32.pygame_integration import *


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

    def _handle(self, event: PygameEvent, loop: HandlerLoop) -> None:
        impulse = Vector((0, 0))

        if event.key in self._right_movement_keys:
            impulse += Vector((self.main_hero._speed_limit, 0))
        if event.key in self._left_movement_keys:
            impulse -= Vector((self.main_hero._speed_limit, 0))

        if event.key in self._up_movement_keys:
            impulse -= Vector((0, self.main_hero._speed_limit))
        if event.key in self._down_movement_keys:
            impulse += Vector((0, self.main_hero._speed_limit))

        self.main_hero.moving_process.original_process.vector_to_next_subject_position = impulse


class TestObject(MultilayerProcessMovableAvatarKeeper):
    _moving_process_factory = AbruptImpulseProcess
    _proxy_moving_process_factories = (CustomFactory(SpeedLimitedProxyMovingProcess, 2), )

    _avatar_factory = CustomFactory(
        lambda unit: PrimitiveAvatar(
            unit,
            Circle(
                RGBAColor(choice(range(255)), choice(range(255)), choice(range(255))),
                choice(range(3, 50))
            )
        )
    )


class ObserveAvatar(ResourceAvatar):
    _resource_factory = CustomFactory(lambda _: Circle(RGBAColor(255, 0, 50), 0))

    def update(self) -> None:
        super().update()
        vector_to_observed = self.domain.position - self.domain.observed.position
        self.render_resource.radius = vector_to_observed.length


class ObserveUnit(MultilayerProcessMovableAvatarKeeper, IUpdatable):
    _avatar_factory = ObserveAvatar

    _moving_process_factory = AbruptImpulseProcess
    _proxy_moving_process_factories = (CustomFactory(SpeedLimitedProxyMovingProcess, 1), )

    def __init__(self, position: Vector, observed: IPositional):
        super().__init__(position)
        self.observed = observed

    def update(self) -> None:
        self._moving_process.original_process.vector_to_next_subject_position = (
            self.observed.position
            - self.position
        )


class SpawnerUnit(StaticAvatarKeeper, MultitaskingUnit):
    _avatar_factory = CustomFactory(lambda unit: PrimitiveAvatar(unit, None))

    def __init__(
        self,
        position: Vector,
        factory: Callable[[Vector], IPositional],
        spawn_zone: Iterable[Diapason],
        timer: Timer
    ):
        super().__init__(position)
        super(MultitaskingUnit, self).__init__()

        self.factory = factory
        self.spawn_zone = tuple(spawn_zone)
        self.timer = timer

    def update(self) -> None:
        if self.timer.is_time_over():
            generate_point = Vector(tuple(
                randint(coordinate_diapason.start, coordinate_diapason.end)
                for coordinate_diapason in self.spawn_zone
            ))

            self.add_process(
                UnitSpawnProcess((self.factory(generate_point), ))
            )
            self.timer.start()


black_unit = TestObject(Vector((200, 240)))
black_unit.avatar.render_resource = Circle(RGBAColor(), 20)

red_unit = ObserveUnit(Vector((100, 240)), black_unit)

unit_spawner = SpawnerUnit(
    Vector((320, 240)),
    CustomFactory(TestObject),
    (Diapason(640), Diapason(480)),
    Timer(3)
)

unit_spawner.avatar.render_resource = Circle(RGBAColor(red=255, green=243), 30)


CustomAppFactory((
    CustomFactory(
        SyncPygameEventController, (
            ExitEventHandler(),
            MainHeroManagement(black_unit)
        )
    ),
    PygameDisplayUpdater,
    CustomFactory(PygameClockSleepLoopHandler, 60)
))(
    CustomWorld(
        [black_unit, red_unit, unit_spawner],
        [InhabitantUpdater, WorldProcessesActivator, InhabitantMover, InhabitantAvatarRenderResourceParser]
    ),
    (
        PygameSurfaceRender(
            (display.set_mode((640, 480)), ),
            RGBAColor(232, 232, 232)
        ),
    )
).run()
