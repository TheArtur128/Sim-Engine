from math import copysign

from pyoverload import overload

from physics import Vector, VirtualVector


class Line:
    _MINIMUM_DISTANCE_BETWEEN_POINTS: int | float = 1

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
        points = [vector.start_point]
        current_point_index = 1
        vector_to_end_point = vector.value

        while any(vector_to_end_point.coordinates):
            vector_coordinates_to_created_point = list()
            new_point_coordinates = list()

            for end_point_vector_coordinate_index, end_point_vector_coordinate in enumerate(vector_to_end_point.coordinates):
                step = (
                    copysign(self._MINIMUM_DISTANCE_BETWEEN_POINTS, end_point_vector_coordinate)
                    if end_point_vector_coordinate != 0 else 0
                )

                new_point_coordinates.append(
                    points[current_point_index - 1].coordinates[end_point_vector_coordinate_index] + step
                )

                vector_coordinates_to_created_point.append(step)

            points.append(Vector(tuple(new_point_coordinates)))
            current_point_index += 1
            vector_to_end_point -= Vector(vector_coordinates_to_created_point)

        return tuple(points)
