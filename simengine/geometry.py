from abc import ABC, abstractmethod
from dataclasses import dataclass
from math import sqrt
from typing import Iterable, Callable

from pyoverload import overload

from errors.geometry_errors import (
    UnableToDivideVectorIntoPointsError,
    FigureIsNotCorrect,
    FigureIsNotClosedError,
    FigureCrossesItselfError
)
from tools import (
    NumberRounder,
    ShiftNumberRounder,
    AccurateNumberRounder,
    Report,
    Divider,
    StrictToStateMixin,
    ReportAnalyzer,
    BadReportHandler,
    Report
)


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

    def get_rounded_by(self, rounder: NumberRounder) -> 'Vector':
        return self.__class__(tuple(
            rounder(coordinate)
            for coordinate in self.coordinates
        ))


@dataclass
class VirtualVector:
    start_point: Vector
    end_point: Vector

    @property
    def value(self) -> Vector:
        return self.end_point - self.start_point

    def get_rounded_by(self, rounder: NumberRounder) -> 'VirtualVector':
        return self.__class__(
            self.start_point.get_rounded_by(rounder),
            self.end_point.get_rounded_by(rounder)
        )


class IPointChanger(ABC):
    @abstractmethod
    def __call__(self, point: Vector) -> Vector:
        pass


class VectorDivider(Divider):
    def __init__(self, distance_between_points: int | float, rounder: NumberRounder):
        self.distance_between_points = distance_between_points
        self.rounder = rounder

    def is_possible_to_divide(self, data: Vector) -> Report:
        return Report.create_error_report(
            UnableToDivideVectorIntoPointsError(
                f"Can't divide vector {data} into points with length 0"
            )
        ) if data.value.length == 0 else super().is_possible_to_divide(data)

    def _divide(self, vector: VirtualVector) -> frozenset[Vector, ]:
        distance_factor = self.distance_between_points / vector.value.length

        vector_to_next_point = Vector(tuple(
            coordinate * distance_factor for coordinate in vector.value.coordinates
        ))

        return self.__create_points(
            vector.start_point,
            vector.value.length / vector_to_next_point.length,
            vector_to_next_point
        )

    def __create_points(
        self,
        start_point: Vector,
        number_of_points_to_create: int,
        vector_to_next_point: Vector
    ) -> frozenset[Vector, ]:
        created_points = [start_point]

        for created_point_index in range(1, int(number_of_points_to_create) + 1):
            created_points.append(
                created_points[created_point_index - 1] + vector_to_next_point
            )

        return frozenset(
            point.get_rounded_by(self.rounder) for point in created_points
        )


class Zone(ABC):
    @overload
    def __contains__(self, point: Vector) -> bool:
        return self.is_point_inside(point)

    @overload
    def __contains__(self, vector: VirtualVector) -> bool:
        return self.is_vector_passes(vector)

    @abstractmethod
    def move_by(self, point_changer: IPointChanger) -> None:
        pass

    @abstractmethod
    def is_vector_passes(self, vector: VirtualVector) -> bool:
        pass

    @abstractmethod
    def is_vector_entered(self, vector: VirtualVector) -> bool:
        pass

    @abstractmethod
    def is_point_inside(self, point: Vector) -> bool:
        pass


class Line(Zone):
    _vector_divider_factory: Callable[['Line'], VectorDivider] = (
        lambda _: VectorDivider(0.1, ShiftNumberRounder(AccurateNumberRounder(), 1))
    )

    def __init__(self, first_point: Vector, second_point: Vector):
        self._vector_divider = self._vector_divider_factory()
        self._rounder = self._vector_divider.rounder

        self.__first_point = first_point
        self.__second_point = second_point

        self._update_points()

    def __repr__(self) -> str:
        return f"{self.__class__.__name__} between {self.first_point} and {self.second_point}"

    @property
    def first_point(self) -> Vector:
        return self.__first_point

    @first_point.setter
    def first_point(self, new_point: Vector) -> None:
        self.__first_point = new_point
        self._update_points()

    @property
    def second_point(self) -> Vector:
        return self.__second_point

    @second_point.setter
    def second_point(self, new_point: Vector) -> None:
        self.__second_point = new_point
        self._update_points()

    @property
    def all_available_points(self) -> tuple[Vector, ]:
        return self.__all_available_points

    def move_by(self, point_changer: IPointChanger) -> None:
        self.__first_point, self.__second_point = map(
            point_changer, (self.first_point, self.second_point)
        )

        self._update_points()

    def is_vector_passes(self, vector: VirtualVector) -> bool:
        rounded_vector = vector.get_rounded_by(self._rounder)

        return any(
            self.is_point_inside(point)
            for point in self._vector_divider(rounded_vector)
        )

    def is_vector_entered(self, vector: VirtualVector) -> bool:
        return self.is_point_inside(
            vector.get_rounded_by(self._rounder).end_point
        )

    def is_point_inside(self, point: Vector) -> bool:
        return point.get_rounded_by(self._rounder) in self.__all_available_points

    def _update_points(self) -> None:
        self.__first_point, self.__second_point = map(
            lambda vector: vector.get_rounded_by(self._rounder),
            (self.__first_point, self.__second_point)
        )

        self.__all_available_points = self._vector_divider(
            VirtualVector(self.first_point, self.second_point)
        )


class Figure(Zone, StrictToStateMixin):
    _line_factory: Callable[[Vector, Vector], Line] = Line
    _report_analyzer = ReportAnalyzer(
        (BadReportHandler(FigureIsNotCorrect, "Figure not viable"), )
    )

    def __init__(self, points: Iterable[Vector, ]):
        self._update_lines_by(points)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({len(self.summits)} summit{'s' if len(self.summits) > 0 else ''})"

    @property
    def summits(self) -> tuple[Vector, ]:
        return self.__summits

    def move_by(self, point_changer: IPointChanger) -> None:
        self._update_lines_by(
            tuple(map(point_changer, self.summits))
        )
        self._check_errors()

    def is_vector_passes(self, vector: VirtualVector) -> bool:
        return self._get_number_of_lines_passed_by(vector) % 2 == 0

    def is_vector_entered(self, vector: VirtualVector) -> bool:
        return self._get_number_of_lines_passed_by(vector) % 2 != 0

    def is_point_inside(self, point: Vector) -> bool:
        return any(line.is_point_inside(point) for line in self._lines)

    def _get_number_of_lines_passed_by(self, vector: VirtualVector) -> int:
        return sum(int(line.is_vector_passes(vector)) for line in self._lines)

    def _is_correct(self) -> Report:
        number_of_measurements = max(
            map(lambda point: len(point.coordinates), self.summits)
        )

        if len(self.summits) <= number_of_measurements:
            return Report.create_error_report(FigureIsNotClosedError(
                f"{number_of_measurements}D figure must contain more than {number_of_measurements} links for closure"
            ))
        elif any(
            3 < self._get_number_of_lines_passed_by(VirtualVector(line.first_point, line.second_point))
            for line in self._lines
        ):
            return Report.create_error_report(
                FigureCrossesItselfError("Figure lines intersect")
            )
        else:
            return Report(True)

    def _update_lines_by(self, points: Iterable[Vector, ]) -> tuple[Line, ]:
        self._lines = tuple(
            self._line_factory(
                points[point_index - 1],
                points[point_index]
            )
            for point_index in range(len(points))
        )

        self.__summits = tuple(line.first_point for line in self._lines)
        self._check_errors()
