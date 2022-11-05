from dataclasses import dataclass
from typing import Iterable

from simengine.basic_render_resources import *
from simengine.geometry import Vector
from simengine.tools import RGBAColor


@dataclass
class PygamePolygon(Polygon):
    """Dataclass containing data for pygame polygon drawing function."""

    border_width: int | float = 0


@dataclass
class PygameLine(Line):
    """
    Dataclass containing data for pygame line and aaline drawing functions.

    The value of is_smooth attribute defines the annotation on the using function:
    True - aaline, False - line.
    """

    border_width: int | float = 1
    is_smooth: bool = False


@dataclass
class PygameLines(ColorRenderResource):
    """
    Dataclass containing data for pygame lines and aalines drawing functions.

    The value of is_smooth attribute defines the annotation on the using function:
    True - aalines, False - lines.
    """

    is_closed: bool
    points: Iterable[Vector]
    border_width: int | float = 1
    is_smooth: bool = False


@dataclass
class PygameCircle(Circle):
    """Dataclass containing data for pygame circle drawing function."""

    border_width: int | float = 0


@dataclass
class PygameRectangle(Rectangle):
    """Dataclass containing data for pygame rect drawing function."""

    border_width: int | float = 0


@dataclass
class PygameEllipse(Rectangle):
    """Dataclass containing data for pygame ellipse drawing function."""

    border_width: int | float = 0


@dataclass
class PygameArc(Rectangle):
    """Dataclass containing data for pygame arc drawing function."""

    start_angle: int | float
    stop_angle: int | float
    border_width: int | float = 1
