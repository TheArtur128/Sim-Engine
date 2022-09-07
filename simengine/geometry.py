from typing import Iterable, NoReturn

from physics import Vector
from errors.geometry_errors import FigureIsNotConvexError


class LineSegment:
    def __init__(self, points: Iterable[Vector, ]) -> None:
        self._points = tuple(points)
        self._is_correnct()

    @property
    def points(self) -> tuple[Vector, ]:
        return self._points

    def _is_correnct(self) -> NoReturn:
        pass


class Figure(LineSegment):
    def is_point_inside(self, point: Vector) -> bool:
        сomparisons_by_coordinates_from_reference_point = tuple(map(
            list, ((False, False),) * len(point.coordinates)
        ))

        for active_point in self.points:
            for coordinate_index, reference_point_coordinate, active_point_coordinate in map(
                lambda item: (item[0], *item[1:][0]),
                enumerate(zip(point.coordinates, active_point.coordinates))
            ):
                if reference_point_coordinate > active_point_coordinate:
                    сomparisons_by_coordinates_from_reference_point[coordinate_index][0] = True

                if reference_point_coordinate < active_point_coordinate:
                    сomparisons_by_coordinates_from_reference_point[coordinate_index][1] = True

        return all(map(all, сomparisons_by_coordinates_from_reference_point))

    def _is_correnct(self) -> NoReturn:
        for point in self.points:
            self.__check_point(point)

    def __check_point(self, point: Vector) -> NoReturn:
        if self.is_point_inside(point):
            raise FigureIsNotConvexError(f"Figure {self} has a point {point} in it bending it")
