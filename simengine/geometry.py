from abc import ABC, abstractmethod
from dataclasses import dataclass
from math import sqrt, fabs, degrees, acos, cos, asin, sin, radians
from functools import lru_cache, wraps, cached_property, reduce
from typing import Iterable, Callable, Union, Generator

from beautiful_repr import StylizedMixin, Field, TemplateFormatter, parse_length
from pyoverload import overload

from simengine.interfaces import IUpdatable, IZone, IZoneFactory
from simengine.errors.geometry_errors import *
from simengine.tools import (
    NumberRounder,
    ShiftNumberRounder,
    AccurateNumberRounder,
    Report,
    Divider,
    StrictToStateMixin,
    ReportAnalyzer,
    BadReportHandler,
    Report,
    compare,
    Diapason,
    get_collection_with_reduced_nesting_level_by,
)


class DegreeMeasure:
    __slots__ = ('__degrees')

    def __init__(self, degrees: int | float):
        self.__degrees = self._bring_number_into_degrees(degrees)

    @property
    def degrees(self) -> int | float:
        return self.__degrees

    def __int__(self) -> int:
        return int(self.degrees)

    def __float__(self) -> float:
        return float(self.degrees)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.degrees})"

    def __hash__(self) -> int:
        return self.degrees

    def __eq__(self, other: int | float) -> bool:
        return self.degrees == self.__get_degrees_from(other)

    def _degree_measure_creation_from_degrees(
        method: Callable[['DegreeMeasure', any, ], int | float]
    ) -> Callable[[any, ], 'DegreeMeasure']:
        @wraps(method)
        def wrapper(self: 'DegreeMeasure', *args, **kwargs) -> 'DegreeMeasure':
            return self._create_from_degrees(method(self, *args, **kwargs))

        return wrapper

    def _interpret_input_measure_in_degrees(
        method: Callable[[int | float], any]
    ) -> Callable[[Union[int, float, 'DegreeMeasure']], any]:
        @wraps(method)
        def wrapper(
            self: 'DegreeMeasure',
            other: Union[int, float, 'DegreeMeasure'],
            *args,
            **kwargs
        ) -> any:
            return method(
                self,
                self._get_number_from_degrees_or_number(other),
                *args,
                **kwargs
            )

        return wrapper

    @_degree_measure_creation_from_degrees
    @_interpret_input_measure_in_degrees
    def __add__(self, number: int | float) -> int | float:
        return self.degrees + number

    def __radd__(self, number: int | float) -> 'DegreeMeasure':
        return self + number

    @_degree_measure_creation_from_degrees
    @_interpret_input_measure_in_degrees
    def __sub__(self, number: int | float) -> int | float:
        return self.degrees - number

    def __rsub__(self, number: int | float) -> 'DegreeMeasure':
        return -(self) + number

    @_degree_measure_creation_from_degrees
    @_interpret_input_measure_in_degrees
    def __mul__(self, number: int | float) -> int | float:
        return self.degrees * number

    def __rmul__(self, number: int | float) -> 'DegreeMeasure':
        return self * number

    @_degree_measure_creation_from_degrees
    @_interpret_input_measure_in_degrees
    def __truediv__(self, number: int | float) -> int | float:
        return self.degrees / number

    @_degree_measure_creation_from_degrees
    @_interpret_input_measure_in_degrees
    def __floordiv__(self, number: int | float) -> int | float:
        return (self.degrees / number) // 1

    @_degree_measure_creation_from_degrees
    def __neg__(self) -> 'DegreeMeasure':
        return self.degrees * -1

    def _get_number_from_degrees_or_number(
        cls,
        number_or_degrees: Union[int, float, 'DegreeMeasure']
    ) -> 'DegreeMeasure':
        return (
            number_or_degrees.degrees if isinstance(number_or_degrees, DegreeMeasure)
            else number_or_degrees
        )

    @classmethod
    def _create_from_degrees(cls, number):
        return cls(cls._bring_number_into_degrees(number))

    @staticmethod
    def _bring_number_into_degrees(number: int | float) -> int | float:
        return number - (number // 360)*360


@dataclass(repr=False)
class DegreesOnAxes:
    first_axis: int
    second_axis: int
    degrees: DegreeMeasure

    def __post_init__(self) -> None:
        if self.first_axis == self.second_axis:
            raise AxisDegreesError(f"{self.__class__.__name__} must be on two axes, not one ({self.first_axis})")

    @property
    def axes(self) -> tuple[int, int]:
        return (self.first_axis, self.second_axis)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({str(self.axes)[1:-1]}, degrees={self.degrees.degrees})"


@dataclass(repr=False)
class DegreeArea(DegreesOnAxes):
    shift_degrees: DegreeMeasure

    @property
    def diapason(self) -> Diapason:
        return Diapason(
            self.shift_degrees.degrees,
            (self.degrees + self.shift_degrees).degrees,
            is_end_inclusive=True
        )


class Vector:
    def __init__(self, coordinates: Iterable[float | int] = tuple()):
        self.__coordinates = tuple(coordinates)

    @property
    def coordinates(self) -> tuple[int | float, ]:
        return self.__coordinates

    @cached_property
    def length(self) -> float:
        return sqrt(sum(coordinate**2 for coordinate in self.coordinates))

    @cached_property
    def degrees(self) -> tuple[DegreesOnAxes, ]:
        perpendicular_vector = Vector((1, ))

        return tuple(
            DegreesOnAxes(
                first_axis,
                second_axis,
                self.__class__((
                    self.coordinates[first_axis],
                    self.coordinates[second_axis]
                )).get_degrees_between(
                    perpendicular_vector,
                    0 > self.coordinates[second_axis]
                ) if any(map(
                    lambda coordinate: coordinate != 0,
                    (self.coordinates[first_axis], self.coordinates[second_axis])
                )) else DegreeMeasure(0)
            )
            for first_axis in range(len(self.coordinates))
            for second_axis in range(first_axis + 1, len(self.coordinates))
        )

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({str(tuple(self.coordinates))[1:-1]})"

    def __hash__(self) -> int:
        return hash(self.coordinates)

    def __eq__(self, other: 'Vector') -> 'Vector':
        return self.coordinates == other.coordinates

    @lru_cache(maxsize=8192)
    def __add__(self, other: 'Vector') -> 'Vector':
        return self.__class__(
            tuple(map(
                lambda first, second: first + second,
                *(
                    vector.coordinates
                    for vector in self.get_mutually_normalized(self, other)
                )
            ))
        )

    def __sub__(self, other: 'Vector') -> 'Vector':
        return self + (-other)

    @lru_cache(maxsize=4096)
    def __mul__(self, other: Union[int, float, 'Vector']) -> 'Vector':
        return (
            self.get_scalar_by(other) if isinstance(other, Vector)
            else self.get_multiplied_by_number(other)
        )

    def __rmul__(self, number: int | float) -> 'Vector':
        return self * number

    def __truediv__(self, number: int | float) -> 'Vector':
        return self*(1 / number)

    def __floordiv__(self, number: int | float) -> 'Vector':
        return self.__class__(
            tuple(int(coordinate) for coordinate in (self / number).coordinates)
        )

    def __neg__(self) -> 'Vector':
        return self.get_reflected_by_axes()

    def __len__(self) -> int:
        return len(self.coordinates)

    @lru_cache(maxsize=1024)
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

    @lru_cache(maxsize=128)
    def get_reflected_by_axes(
        self,
        axis_indexes: Iterable[int, ] | None = None
    ) -> 'Vector':
        if axis_indexes is None:
            axis_indexes = range(len(self.coordinates))

        return self.__class__(tuple(
            coordinate * (-1 if coordinate_index in axis_indexes else 1)
            for coordinate_index, coordinate in enumerate(self.coordinates)
        ))

    @lru_cache(maxsize=128)
    def get_reduced_to_length(self, length: int | float) -> 'Vector':
        if self.length == 0:
            raise VectorError("Vector with length == 0 can't be lengthened")

        return (self / self.length) * length

    def get_rotated_many_times_by(self, axis_degree_measures: Iterable[DegreesOnAxes]) -> 'Vector':
        result_vector = self

        for axis_degree_measure in axis_degree_measures:
            result_vector = result_vector.get_rotated_by(axis_degree_measure)

        return result_vector

    def get_rotated_by(self, axes_degrees: DegreesOnAxes) -> 'Vector':
        number_of_measurements = max(axes_degrees.axes) + 1
        reduced_vector = (
            self.get_normalized_to_measurements(number_of_measurements)
            if len(self.coordinates) < number_of_measurements else self
        )

        axes_section_vector = self.__class__((
            reduced_vector.coordinates[axes_degrees.first_axis],
            reduced_vector.coordinates[axes_degrees.second_axis]
        ))

        if all(coordinate == 0 for coordinate in axes_section_vector.coordinates):
            return self

        coordinates = list(reduced_vector.coordinates)

        reduced_axes_section_vector = axes_section_vector.get_reduced_to_length(1)

        coordinates[axes_degrees.first_axis] = axes_section_vector.length * cos(radians(
            degrees(acos(reduced_axes_section_vector.coordinates[0]))
            + axes_degrees.degrees
        ))
        coordinates[axes_degrees.second_axis] = axes_section_vector.length * sin(radians(
            degrees(asin(reduced_axes_section_vector.coordinates[1]))
            + axes_degrees.degrees
        ))

        return self.__class__(coordinates)

    def get_rounded_by(self, rounder: NumberRounder) -> 'Vector':
        return self.__class__(tuple(
            rounder(coordinate)
            for coordinate in self.coordinates
        ))

    def get_multiplied_by_number(self, number: int | float) -> 'Vector':
        return self.__class__(
            tuple(number * coordinate for coordinate in self.coordinates)
        )

    def get_scalar_by(self, vector: 'Vector') -> int | float:
        return sum(tuple(map(
            lambda first, second: first * second,
            *(
                normalized_vector.coordinates
                for normalized_vector in self.get_mutually_normalized(self, vector)
            )
        )))

    def get_degrees_between(self, vector: 'Vector', is_external: bool = False) -> DegreeMeasure:
        return DegreeMeasure(degrees(acos(
            (self * vector) / (self.length * vector.length)
        ))) * (-1 if is_external else 1)

    @classmethod
    def get_mutually_normalized(cls, *vectors: tuple['Vector', ]) -> tuple['Vector', ]:
        maximum_number_of_measurements = max((len(vector.coordinates) for vector in vectors))

        return tuple(
            vector.get_normalized_to_measurements(maximum_number_of_measurements)
            for vector in vectors
        )

    @classmethod
    def create_by_degrees(cls, length: int | float, axis_degree_measures: Iterable[DegreesOnAxes]) -> 'Vector':
        fill_axis = axis_degree_measures[0].first_axis if len(axis_degree_measures) else 0

        return cls(
            (0, )*fill_axis + (length, )
        ).get_rotated_many_times_by(axis_degree_measures)


@dataclass(repr=False)
class PositionVector:
    start_point: Vector
    end_point: Vector

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(from {self.start_point} to {self.end_point})"

    @property
    def virtual_vector(self) -> Vector:
        return self.end_point - self.start_point

    def get_rounded_by(self, rounder: NumberRounder) -> 'PositionVector':
        return self.__class__(
            self.start_point.get_rounded_by(rounder),
            self.end_point.get_rounded_by(rounder)
        )


class IPointChanger(ABC):
    @abstractmethod
    def __call__(self, point: Vector) -> Vector:
        pass


class DynamicTransporter(IPointChanger):
    def __init__(self, shift: Vector):
        self.shift = shift

    def __call__(self, point: Vector) -> Vector:
        return point + self.shift


class PointRotator(StylizedMixin, IPointChanger):
    _repr_fields = (
        Field('center_point', formatter=TemplateFormatter('about {value}')),
        Field(
            'axis_degree_measures',
            formatter=TemplateFormatter('{value}'),
            value_transformer=lambda value: str(list(value))[1:-1] if len(value) > 0 else value
        )
    )

    def __init__(self, axis_degree_measures: Iterable[DegreesOnAxes], center_point: Vector = Vector()):
        self.axis_degree_measures = tuple(axis_degree_measures)
        self.center_point = center_point

    def __call__(self, point: Vector) -> Vector:
        return reduce(
            lambda result_point, axis_degree_measure: (
                (result_point - self.center_point).get_rotated_by(axis_degree_measure)
                + self.center_point
            ),
            (point, *self.axis_degree_measures)
        )


class VectorDivider(Divider, StylizedMixin):
    _repr_fields = (Field('distance_between_points'), )

    def __init__(self, distance_between_points: int | float, rounder: NumberRounder):
        self.distance_between_points = distance_between_points
        self.rounder = rounder

    def is_possible_to_divide(self, data: Vector) -> Report:
        return Report.create_error_report(
            UnableToDivideVectorIntoPointsError(
                f"Can't divide vector {data} into points with length 0"
            )
        ) if data.virtual_vector.length == 0 else super().is_possible_to_divide(data)

    def _divide(self, vector: PositionVector) -> frozenset[Vector, ]:
        distance_factor = self.distance_between_points / vector.virtual_vector.length

        vector_to_next_point = Vector(tuple(
            coordinate * distance_factor for coordinate in vector.virtual_vector.coordinates
        ))

        return self.__create_points(
            vector.start_point,
            vector.virtual_vector.length / vector_to_next_point.length,
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


class Figure(IZone, ABC):
    _vector_divider_factory: Callable[['Line'], VectorDivider] = (
        lambda _: VectorDivider(0.1, ShiftNumberRounder(AccurateNumberRounder(), 1))
    )

    def __init__(self):
        self._vector_divider = self._vector_divider_factory()

    @overload
    def __contains__(self, point: Vector) -> bool:
        return self.is_point_inside(point)

    @overload
    def __contains__(self, vector: PositionVector) -> bool:
        return self.is_vector_passes(vector)

    def is_vector_passes(self, vector: PositionVector) -> bool:
        return any(
            self.is_point_inside(point)
            for point in self._vector_divider(vector)
        )

    def is_vector_entered(self, vector: PositionVector) -> bool:
        return self.is_point_inside(
            vector.end_point
        )


class Angle(Figure, StylizedMixin):
    _repr_fields = Field('center_point'),

    def __init__(self, center_point: PositionVector, degrees: Iterable[DegreeArea]):
        self._center_point = center_point
        self._degree_areas = tuple(degrees)

    @property
    def center_point(self) -> Vector:
        return self._center_point

    @property
    def degree_areas(self) -> tuple[DegreeArea]:
        return self._degree_areas

    def get_degree_area_by_axis(self, first_axis: int, second_axis: int) -> DegreeArea:
        axes = frozenset((first_axis, second_axis))

        for degree_area in self._degree_areas:
            if frozenset(degree_area.axes) == axes:
                return degree_area

        return DegreeArea(first_axis, second_axis, 0, 0)

    def move_by(self, point_changer: IPointChanger) -> None:
        created_vertices = self.create_ray_vertices_by(1)
        self._center_point = point_changer(self._center_point)

        self._update_by_points(tuple(
            point_changer(vertex) for vertex in created_vertices
        ))

    def is_point_inside(self, point: Vector) -> bool:
        return len(self._degree_areas) > 0 and (point == self._center_point or all(
            degree_measure.degrees.degrees in self.get_degree_area_by_axis(
                degree_measure.first_axis,
                degree_measure.second_axis
            ).diapason
            for degree_measure in (point - self._center_point).degrees
        ))

    def create_ray_vertices_by(self, length: int | float) -> tuple[Vector]:
        return tuple(get_collection_with_reduced_nesting_level_by(
            1,
            (
                (
                    self.center_point + Vector.create_by_degrees(
                        length,
                        DegreeMeasure(
                            degree_area.first_axis,
                            degree_area.second_axis,
                            degree_area.shift_degrees
                        )
                    ),
                    self.center_point + Vector.create_by_degrees(
                        length,
                        DegreeMeasure(
                            degree_area.first_axis,
                            degree_area.second_axis,
                            degree_area.degrees + degree_area.shift_degrees
                        )
                    )
                )
                for degree_measure in self._degree_areas
            )
        ))

    @classmethod
    def created_by_points(cls, center_point: PositionVector, points: Iterable[Vector]) -> 'Angle':
        angle = cls(center_point, tuple())
        angle._update_by_points(points)

        return angle

    def _update_by_points(self, points: Iterable[Vector]) -> None:
        self._degree_areas = tuple(self.__create_degree_areas_from(
            tuple(get_collection_with_reduced_nesting_level_by(
                1,
                ((point - self._center_point).degrees for point in points)
            ))
        ))

    def __create_degree_areas_from(self, axis_degree_measures: Iterable[DegreesOnAxes]) -> Generator[DegreeArea, any, None]:
        max_axes = max(get_collection_with_reduced_nesting_level_by(
            1,
            (point_degree_measure.axes for point_degree_measure in axis_degree_measures)
        ))

        for first_axis in range(max_axes + 1):
            for second_axis in range(first_axis + 1, max_axes + 1):
                degree_multitude = frozenset(
                    degree_measure.degrees.degrees
                    for degree_measure in axis_degree_measures
                    if (
                        degree_measure.first_axis == first_axis
                        and degree_measure.second_axis == second_axis
                    )
                )

                min_degrees, max_degrees = min(degree_multitude), max(degree_multitude)

                yield DegreeArea(
                    first_axis,
                    second_axis,
                    DegreeMeasure(max_degrees - min_degrees),
                    DegreeMeasure(min_degrees)
                )


class Site(Figure):
    def __init__(self, point: Vector):
        self.point = point

    def move_by(self, point_changer: IPointChanger) -> None:
        self.point = point_changer(self.point)

    def is_point_inside(self, point: Vector) -> bool:
        return self.point == point


class CompositeFigure(Figure, StylizedMixin):
    _repr_fields = (
        Field(
            'main_figures',
            value_getter=parse_length,
            formatter=TemplateFormatter("{value} main figures")
        ),
        Field(
            'subtraction_figures',
            value_getter=parse_length,
            formatter=TemplateFormatter("{value} subtraction figures")
        )
    )

    def __init__(
        self,
        main_figures: Iterable[Figure, ],
        subtraction_figures: Iterable[Figure, ] = tuple()
    ):
        super().__init__()
        self.main_figures = set(main_figures)
        self.subtraction_figures = set(subtraction_figures)

    def move_by(self, point_changer: IPointChanger) -> None:
        for figure in (*self.main_figures, *self.subtraction_figures):
            figure.move_by(point_changer)

    def is_point_inside(self, point: Vector) -> bool:
        return (
            any(figure.is_point_inside(point) for figure in self.main_figures)
            if all(not figure.is_point_inside(point) for figure in self.subtraction_figures)
            else False
        )


class Line(Figure, StylizedMixin):
    _repr_fields = (
        Field(
            value_getter=lambda line, _: (line.first_point, line.second_point),
            formatter=lambda values, _: f"between {values[0]} and {values[1]}"
        ),
    )

    def __init__(self, first_point: Vector, second_point: Vector):
        super().__init__()

        self._rounder = self._vector_divider.rounder

        self.__first_point = first_point
        self.__second_point = second_point

        self._update_points()

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

    def is_vector_passes(self, vector: PositionVector) -> bool:
        return super().is_vector_passes(vector) if (
            vector.start_point in self.__proposed_location_area or
            vector.end_point in self.__proposed_location_area or
            vector.end_point - vector.virtual_vector*0.5 in self.__proposed_location_area
        ) else False

    def is_point_inside(self, point: Vector) -> bool:
        return (
            point.get_rounded_by(self._rounder) in self.__all_available_points
            if not point in self.__proposed_location_area else True
        )

    def _update_points(self) -> None:
        self.__first_point, self.__second_point = map(
            lambda vector: vector.get_rounded_by(self._rounder),
            (self.__first_point, self.__second_point)
        )

        self.__all_available_points = self._vector_divider(
            PositionVector(self.first_point, self.second_point)
        )
        self.__proposed_location_area = Rectangle(self.first_point, self.second_point)


class Polygon(Figure, StrictToStateMixin, StylizedMixin):
    _repr_fields = (
        Field(
            'summits',
            value_getter=parse_length,
            formatter=TemplateFormatter("{value} summits")
        ),
    )
    _line_factory: Callable[[Vector, Vector], Line] = Line
    _report_analyzer = ReportAnalyzer(
        (BadReportHandler(FigureIsNotCorrect, "Polygon not viable"), )
    )

    def __init__(self, points: Iterable[Vector, ]):
        super().__init__()
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
        self._check_state_errors()

    def is_point_inside(self, point: Vector) -> bool:
        return any(line.is_point_inside(point) for line in self._lines)

    def _is_correct(self) -> Report:
        number_of_measurements = max(
            map(lambda point: len(point.coordinates), self.summits)
        )

        if len(self.summits) <= number_of_measurements:
            return Report.create_error_report(FigureIsNotClosedError(
                f"{number_of_measurements}D figure must contain more than {number_of_measurements} links for closure"
            ))
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
        self._check_state_errors()


class Circle(Figure, StylizedMixin):
    _repr_fields = (Field('radius'), Field('center_point'))

    def __init__(self, center_point: Vector, radius: int | float):
        super().__init__()
        self.center_point = center_point
        self.radius = radius

    def move_by(self, point_changer: IPointChanger) -> None:
        self.center_point = point_changer(self.center_point)

    def is_point_inside(self, point: Vector) -> bool:
        return (self.center_point - point).length <= self.radius


class FigureFactory(IZoneFactory):
    def __init__(self, figure_type: type, *args_to_type, **kwargs_to_type):
        self.figure_type = figure_type
        self.args_to_type = args_to_type
        self.kwargs_to_type = kwargs_to_type

    def __call__(self, unit: IUpdatable) -> 'Figure':
        return self.figure_type(*self.args_to_type, **self.kwargs_to_type)
