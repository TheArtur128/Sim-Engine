from dataclasses import dataclass
from typing import Iterable

from simengine.geometry import Vector
from simengine.tools import RGBAColor


@dataclass
class GraphicPrimitive:
    color: RGBAColor


@dataclass
class Polygon(GraphicPrimitive):
    points: Iterable[Vector, ]
    border_width: int | float = 0


@dataclass
class Line(GraphicPrimitive):
    start_point: Vector
    end_point: Vector
    border_width: int | float = 1
    is_smooth: bool = False


@dataclass
class Lines(GraphicPrimitive):
    is_closed: bool
    points: Iterable[Vector, ]
    border_width: int | float = 1
    is_smooth: bool = False


@dataclass
class Circle(GraphicPrimitive):
    radius: int | float
    border_width: int | float = 0


@dataclass
class CornerZone(GraphicPrimitive):
    width: int | float
    height: int | float


@dataclass
class Rectangle(CornerZone):
    border_width: int | float = 0


@dataclass
class Ellipse(CornerZone):
    border_width: int | float = 0


@dataclass
class Arc(CornerZone):
    start_angle: int | float
    stop_angle: int | float
    border_width: int | float = 1
