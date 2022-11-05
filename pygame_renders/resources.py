from dataclasses import dataclass
from typing import Iterable

from simengine.geometry import Vector
from simengine.tools import RGBAColor


@dataclass
class GraphicPrimitive:
    """Dataclass of pygame render resources with color."""

    color: RGBAColor


@dataclass
class Polygon(GraphicPrimitive):
    """Dataclass containing data for pygame polygon drawing function."""

    points: Iterable[Vector, ]
    border_width: int | float = 0


@dataclass
class Line(GraphicPrimitive):
    """
    Dataclass containing data for pygame line and aaline drawing functions.

    The value of is_smooth attribute defines the annotation on the using function:
    True - aaline, False - line.
    """

    start_point: Vector
    end_point: Vector
    border_width: int | float = 1
    is_smooth: bool = False


@dataclass
class Lines(GraphicPrimitive):
    """
    Dataclass containing data for pygame lines and aalines drawing functions.

    The value of is_smooth attribute defines the annotation on the using function:
    True - aalines, False - lines.
    """

    is_closed: bool
    points: Iterable[Vector, ]
    border_width: int | float = 1
    is_smooth: bool = False


@dataclass
class Circle(GraphicPrimitive):
    """Dataclass containing data for pygame circle drawing function."""

    radius: int | float
    border_width: int | float = 0


@dataclass
class CornerZone(GraphicPrimitive):
    """GraphicPrimitive dataclass containing the size of the area of the drawn figure."""

    width: int | float
    height: int | float


@dataclass
class Rectangle(CornerZone):
    """Dataclass containing data for pygame rect drawing function."""

    border_width: int | float = 0


@dataclass
class Ellipse(CornerZone):
    """Dataclass containing data for pygame ellipse drawing function."""

    border_width: int | float = 0


@dataclass
class Arc(CornerZone):
    """Dataclass containing data for pygame arc drawing function."""

    start_angle: int | float
    stop_angle: int | float
    border_width: int | float = 1
