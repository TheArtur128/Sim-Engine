from dataclasses import dataclass
from typing import Iterable, NoReturn

from physics import Vector


@dataclass
class LineSegment:
    first_point: Vector
    second_point: Vector

    @property
    def points(self) -> tuple[Vector, Vector]:
        return (self.first_point, self.second_point)


class PolygonalFigure:
    def __init__(self, points: Iterable[Iterable[int | float,],]):
        self._line_segments = set(line_segments)
        self._is_correct()

    def _is_correct(self) -> NoReturn:
        pass
