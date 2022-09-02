from dataclasses import dataclass


@dataclass(frozen=True)
class Vector:
    coordinates: tuple[float | int] = tuple()

    def __add__(self, other):
        maximum_number_of_measurements = max((len(self.coordinates), len(other.coordinates)))

        return self.__class__(
            tuple(map(
                lambda first, second: first + second,
                self.get_normalized_to_measurements(maximum_number_of_measurements).coordinates,
                other.get_normalized_to_measurements(maximum_number_of_measurements).coordinates
            ))
        )

    def __sub__(self, other):
        return self + other.get_reflected()

    def __len__(self) -> int:
        return len(self.coordinates)

    def get_normalized_to_measurements(
        self,
        number_of_measurements: int,
        default_measurement_point: int | float = 0
    ):
        measurement_difference = number_of_measurements - len(self.coordinates)

        return self.__class__(
            self.coordinates + (default_measurement_point,)*measurement_difference if measurement_difference > 0
            else self.coordinates[:number_of_measurements if number_of_measurements >= 0 else 0]
        )

    def get_reflected(self):
        return self.__class__(
            tuple(map(lambda number: -number, self.coordinates))
        )
