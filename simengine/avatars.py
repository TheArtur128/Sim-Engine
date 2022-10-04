from abc import ABC
from typing import Callable

from beautiful_repr import StylizedMixin, Field

from simengine.core import PositionalUnit
from simengine.geometry import Vector
from simengine.renders import ResourcePack
from simengine.interfaces import IAvatar


class Avatar(IAvatar, ABC):
    def __init__(self, unit: PositionalUnit):
        self._unit = unit

    @property
    def unit(self) -> PositionalUnit:
        return self._unit


class ResourceAvatar(Avatar, StylizedMixin, ABC):
    _repr_fields = (Field('resource'), )
    _resource_factory: Callable[['ResourceAvatar'], any]
    _resource_pack_factory: Callable[[any, Vector], ResourcePack] = ResourcePack

    def __init__(self, unit: PositionalUnit):
        super().__init__(unit)
        self._main_resource_pack = self._resource_pack_factory(
            self._resource_factory(self),
            self.unit.position
        )

    @property
    def render_resource_packs(self) -> tuple[ResourcePack, ]:
        return (self._main_resource_pack, )

    @property
    def render_resource(self) -> any:
        return self._main_resource_pack.resource

    def update(self) -> None:
        self._main_resource_pack.point = self.unit.position


class PrimitiveAvatar(ResourceAvatar, ABC):
    def __init__(self, unit: PositionalUnit, resource: any):
        self._resource_factory = lambda _: resource
        super().__init__(unit)

    @property
    def render_resource(self) -> any:
         return ResourceAvatar.render_resource.fget(self)

    @render_resource.setter
    def render_resource(self, render_resource: any) -> None:
        self._main_resource_pack.resource = render_resource
