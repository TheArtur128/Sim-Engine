from dataclasses import dataclass
from typing import Iterable
from math import sqrt, modf

from pyoverload import overload

from tools import round_number_with_comma_shift
from errors.geometry_errors import UnableToDivideVectorIntoPointsError


@dataclass(frozen=True)
class Vector:
    coordinates: tuple[float | int] = tuple()

    @property
    def length(self) -> float:
        return sqrt(sum(coordinate**2 for coordinate in self.coordinates))

    def __add__(self, other: 'Vector') -> 'Vector':
        maximum_number_of_measurements = max((len(self.coordinates), len(other.coordinates)))

        return self.__class__(
            tuple(map(
                lambda first, second: first + second,
                self.get_normalized_to_measurements(maximum_number_of_measurements).coordinates,
                other.get_normalized_to_measurements(maximum_number_of_measurements).coordinates
            ))
        )

    def __sub__(self, other: 'Vector') -> 'Vector':
        return self + other.get_reflected_by_coordinates()

    def __len__(self) -> int:
        return len(self.coordinates)

    def get_normalized_to_measurements(
        self,
        number_of_measurements: int,
        default_measurement_point: int | float = 0
    ) -> 'Vector':
        measurement_difference = number_of_measurements - len(self.coordinates)

        return self.__class__(
            self.coordinates + (default_measurement_point,)*measurement_difference if measurement_difference > 0
            else self.coordinates[:number_of_measurements if number_of_measurements >= 0 else 0]
        )

    def get_reflected_by_coordinates(
        self,
        coordinate_indexes: Iterable[int, ] | None = None
    ) -> 'Vector':
        if coordinate_indexes is None:
            coordinate_indexes = range(len(self.coordinates))

        return self.__class__(tuple(
            coordinate * (-1 if coordinate_index in coordinate_indexes else 1)
            for coordinate_index, coordinate in enumerate(self.coordinates)
        ))

    def get_rounded_with_comma_shift(self, comma_shift: int) -> 'Vector':
        return self.__class__(tuple(
            round_number_with_comma_shift(coordinate, comma_shift)
            for coordinate in self.coordinates
        ))


@dataclass
class VirtualVector:
    start_point: Vector
    end_point: Vector

    @property
    def value(self) -> Vector:
        return self.end_point - self.start_point

    def get_rounded_with_comma_shift(self, comma_shift: int) -> None:
        return self.__class__(
            self.start_point.get_rounded_with_comma_shift(comma_shift),
            self.end_point.get_rounded_with_comma_shift(comma_shift)
        )


class Line:
    _DISTANCE_BETWEEN_POINTS: int | float = 1
    _SHIFT_BY_POINT_ROUNDING_FROM_COMMA: int = 0

    def __init__(self, first_point: Vector, second_point: Vector):
        self.__first_point = first_point
        self.__second_point = second_point

        self._update_all_available_points()

    def __repr__(self) -> str:
        return f"{self.__class__.__name__} between {self.first_point} and {self.second_point}"

    @property
    def first_point(self) -> Vector:
        return self.__first_point

    @first_point.setter
    def first_point(self, new_point: Vector) -> None:
        self.__first_point = new_point.get_rounded_with_comma_shift(
            self._SHIFT_BY_POINT_ROUNDING_FROM_COMMA
        )
        self._update_all_available_points()

    @property
    def second_point(self) -> Vector:
        return self.__second_point

    @second_point.setter
    def second_point(self, new_point: Vector) -> None:
        self.__second_point = new_point.get_rounded_with_comma_shift(
            self._SHIFT_BY_POINT_ROUNDING_FROM_COMMA
        )
        self._update_all_available_points()

    @property
    def all_available_points(self) -> tuple[Vector, ]:
        return self.__all_available_points

    @overload
    def __contains__(self, point: Vector) -> bool:
        return self.is_point_inside(point)

    @overload
    def __contains__(self, vector: VirtualVector) -> bool:
        return self.is_vector_passes(vector)

    def is_vector_passes(self, vector: VirtualVector) -> bool:
        vector = vector.get_rounded_with_comma_shift(self)

        for point in self.__create_points_from(vector):
            if self.is_point_inside(point):
                return True

        return False

    def is_point_inside(self, point: Vector) -> bool: # Will be redone
        return point in self.__all_available_points

    def _update_all_available_points(self) -> None:
        self.__all_available_points = self.__create_points_from(
            VirtualVector(self.first_point, self.second_point)
        )

    def __create_points_from(self, vector: VirtualVector) -> tuple[Vector, ]:
        factor = vector.value.length / self._DISTANCE_BETWEEN_POINTS

        vector_to_next_point = Vector(tuple(
            coordinate / factor for coordinate in vector.value.coordinates
        ))

        number_of_points_to_create = vector.value.length / vector_to_next_point.length

        if number_of_points_to_create <= 0 or modf(number_of_points_to_create)[0]:
            raise UnableToDivideVectorIntoPointsError(
                "Can't divide vector {vector} into {point_number} points with distance {distance}".format(
                    vector=vector,
                    point_number=number_of_points_to_create,
                    distance=self._DISTANCE_BETWEEN_POINTS
                )
            )

        created_points = [vector.start_point]

        for created_point_index in range(1, int(number_of_points_to_create)):
            created_points.append(
                created_points[created_point_index - 1] + vector_to_next_point
            )

        return tuple(created_points)
