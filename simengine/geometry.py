from math import modf

from pyoverload import overload

from physics import Vector, VirtualVector
from errors.geometry_errors import UnableToDivideVectorIntoPointsError


class Line:
    _DISTANCE_BETWEEN_POINTS: int | float = 1

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
        self.__first_point = new_point
        self._update_all_available_points()

    @property
    def second_point(self) -> Vector:
        return self.__second_point

    @second_point.setter
    def second_point(self, new_point: Vector) -> None:
        self.__second_point = new_point
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
        
