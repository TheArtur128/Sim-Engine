from dataclasses import dataclass
from typing import Iterable

from sim32.geometry import Vector
from sim32.tools import RGBAColor


@dataclass
class ColorRenderResource:
    """Dataclass of render resources with color."""

    color: RGBAColor


@dataclass
class Polygon(ColorRenderResource):
    """Dataclass containing data for drawing polygon."""

    points: Iterable[Vector]


@dataclass
class Line(ColorRenderResource):
    """Dataclass containing data for drawing line."""

    start_point: Vector
    end_point: Vector


@dataclass
class Circle(ColorRenderResource):
    """Dataclass containing data for drawing circle."""

    radius: int | float


@dataclass
class Rectangle(ColorRenderResource):
    """Dataclass containing data for drawing rectangle."""

    width: int | float
    height: int | float
