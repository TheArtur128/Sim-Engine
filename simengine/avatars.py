from abc import ABC
from dataclasses import dataclass
from typing import Callable, Iterable, Self

from beautiful_repr import StylizedMixin, Field

from simengine.core import PositionalUnit, MultitaskingUnit
from simengine.geometry import Vector
from simengine.renders import ResourcePack
from simengine.interfaces import IAvatar
from simengine.errors.avatar_errors import AnimationAlreadyFinishedError


class Avatar(IAvatar, ABC):
    """Base avatar with unit acquisition implementation."""

    def __init__(self, unit: PositionalUnit):
        self._unit = unit

    @property
    def unit(self) -> PositionalUnit:
        return self._unit


class SingleResourcePackAvatar(Avatar, ABC):
    """Avatar class using only one resource pack."""

    _main_resource_pack: ResourcePack

    @property
    def render_resource_packs(self) -> tuple[ResourcePack]:
        return (self._main_resource_pack, )

    def update(self) -> None:
        self._main_resource_pack.point = self.unit.position


class ResourceAvatar(SingleResourcePackAvatar, StylizedMixin, ABC):
    """
    Avatar class operating on only one render resource.

    To create a resource and its pack uses the appropriate factories from
    _resource_factory and _resource_pack_factory attributes.
    """

    _repr_fields = (Field('resource'), )
    _resource_factory: Callable[[Self], any]
    _resource_pack_factory: Callable[[any, Vector], ResourcePack] = ResourcePack

    def __init__(self, unit: PositionalUnit):
        super().__init__(unit)
        self._main_resource_pack = self._resource_pack_factory(
            self._resource_factory(self),
            self.unit.position
        )

    @property
    def render_resource(self) -> any:
        """Property to get one available render resource."""

        return self._main_resource_pack.resource


class PrimitiveAvatar(ResourceAvatar):
    """Avatar class that wraps the position of a unit and an input render resource."""

    def __init__(self, unit: PositionalUnit, resource: any):
        self._resource_factory = lambda _: resource
        super().__init__(unit)

    @property
    def render_resource(self) -> any:
         return ResourceAvatar.render_resource.fget(self)

    @render_resource.setter
    def render_resource(self, render_resource: any) -> None:
        self._main_resource_pack.resource = render_resource


@dataclass
class Sprite:
    """Dataclass pack render resource processed as a sprite."""

    resource: any
    max_stay_ticks: int

    def __post_init__(self):
        self.real_stay_ticks = self.max_stay_ticks


class Animation(SingleResourcePackAvatar, ABC):
    """
    Avatar class implemented as an animation from sprites.

    Leaves the sprite storage implementation to childs. Throws an error when
    playing all sprites.
    """

    _sprites: tuple[Sprite]
    _current_sprite_index: int = 0

    def __init__(self, unit: PositionalUnit):
        super().__init__(unit)
        self._update_main_resource_pack()

    def update(self) -> None:
        super().update()

        if self.is_finished():
            self._handle_finish()

        self._update_main_resource_pack()

        self._active_sprite.real_stay_ticks -= 1

        if self._active_sprite.real_stay_ticks <= 0:
            self._current_sprite_index += 1

    def is_finished(self) -> bool:
        return (
            self._current_sprite_index >= len(self._sprites) - 1
            and self._active_sprite.real_stay_ticks <= 0
        )

    @property
    def _active_sprite(self) -> Sprite:
        """Property for the current animation sprite."""

        return self._sprites[self._current_sprite_index]

    def _update_main_resource_pack(self) -> None:
        """Method for updating the main resource pack."""

        self._main_resource_pack = ResourcePack(
            self._sprites[self.__current_sprite_index].resource,
            self.unit.position
        )

    def _handle_finish(self) -> None:
        """
        Method for handling the end of sprites for assignment to the main
        main_resource_pack.
        """

        raise AnimationAlreadyFinishedError(f"Animation {self} already finished")


class CustomAnimation(Animation):
    """Animation class with input sprites."""

    def __init__(self, unit: PositionalUnit, sprites: Iterable[Sprite]):
        super().__init__(unit)
        self._sprites = tuple(sprites)


class EndlessAnimation(Animation, ABC):
    """Animation class for looping sprites."""

    def _handle_finish(self) -> None:
        self._current_sprite_index = 0

        for sprite in self._sprites:
            sprite.real_stay_ticks = sprite.max_stay_ticks


class CustomEndlessAnimation(EndlessAnimation, CustomAnimation):
    """Endless Animation class with input sprites."""


class AnimationAvatar(Avatar, ABC):
    """Avatar class delegating responsibilities to animations."""

    _default_animation_factory: Callable[[PositionalUnit], EndlessAnimation]

    def __init__(self, unit: PositionalUnit):
        super().__init__(unit)
        self._current_animation = self._default_animation = self._default_animation_factory(unit)

    @property
    def render_resource_packs(self) -> tuple[ResourcePack]:
        return self._current_animation.render_resource_packs

    def update(self) -> None:
        self._current_animation.update()


class TopicAnimationAvatar(AnimationAvatar, ABC):
    """Animation Avatar class that implements selection of animations by topic."""

    _animation_factory_by_topic: dict[str, Callable[[PositionalUnit], EndlessAnimation]]

    def __init__(self, unit: PositionalUnit):
        super().__init__(unit)

        self._animation_by_topic = {
            topic: animation_factory(unit)
            for topic, animation_factory in self._animation_factory_by_topic.items()
        }

    def update(self) -> None:
        if (
            self._default_animation is not self._current_animation
            and self._current_animation.is_finished()
        ):
            self._current_animation = self._default_animation

        super().update()

    def activate_animation_by_topic(self, topic: str) -> None:
        """Animation selection method by topic."""

        self._current_animation = self._animation_by_topic[topic]


class CustomTopicAnimationAvatar(TopicAnimationAvatar):
    """Topic Animation Avatar class with input animation factories and topics."""

    def __init__(
        self,
        unit: PositionalUnit,
        animation_factory_by_topic: dict[str, Callable[[PositionalUnit], EndlessAnimation]]
    ):
        self._animation_factory_by_topic = animation_factory_by_topic
        super().__init__(unit)


class ProcessAnimationAvatar(AnimationAvatar):
    """
    Animation Avatar class that implements the choice of animations for the
    processes running in the unit.
    """
    
    _animation_factory_by_process_type: dict[type, Callable[[MultitaskingUnit], EndlessAnimation]]

    def __init__(self, unit: PositionalUnit):
        super().__init__(unit)

        self.__units_previous_processes = unit.processes
        self._animation_by_process_type = {
            process_type: animation_factory(unit)
            for process_type, animation_factory in self._animation_factory_by_process_type.items()
        }

    def update(self) -> None:
        for process in self.unit.processes - self.__units_previous_processes:
            if type(process) in self._animation_by_process_type:
                self._current_animation = self._animation_by_process_type[type(process)]
                break

        self.__units_previous_processes = self.unit.processes

        super().update()
