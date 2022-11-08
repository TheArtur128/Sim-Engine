from typing import Optional, Callable, Iterable

from colorama import init, Fore

from simengine import *


init(autoreset=True)


class Snake(DiscreteUnit):
    _part_attribute_names = ('_head', '_tails')

    _head: Optional[MovableUnit] = None
    _tails: Iterable = tuple()

    @property
    def head(self) -> MovableUnit | None:
        return self._head

    @property
    def tails(self) -> tuple[ProcessMovableUnit]:
        return tuple(self._tails)

    def init_parts(
        self,
        head: MovableUnit,
        tail_factory: Callable[[Vector], ProcessMovableUnit],
    ) -> None:
        self._tails = list()
        self._head = head
        self._tail_factory = tail_factory

    def grow_tail(self, tail_length: int) -> None:
        for _ in range(tail_length):
            last_node = self._tails[-1] if self._tails else self._head

            self._tails.append(self._tail_factory(last_node.previous_position))

    def cut_tail(self, tail_length: int) -> None:
        self._tails = self._tails[:-tail_length]

    def update(self) -> None:
        for tail_index, tail in enumerate(self._tails):
            if not isinstance(tail.moving_process.original_process, DirectedMovingProcess):
                continue

            previous_unit = self.__get_prevous_node_by(tail_index)

            tail.moving_process.original_process.vector_to_next_unit_position = (
                previous_unit.position - tail.position
            )

    def __get_prevous_node_by(self, tail_index: int) -> MovableUnit | None:
        return self._head if tail_index - 1 < 0 else self._tails[tail_index - 1]


class SnakeHead(SpeedLimitedUnit):
    _avatar_factory = CustomFactory(PrimitiveAvatar, ConsoleCell('#', Fore.LIGHTBLUE_EX))
    _speed_limit = 1

    def update(self) -> None:
        pass


class SnakeTail(SpeedLimitedUnit):
    _avatar_factory = CustomFactory(PrimitiveAvatar, ConsoleCell('#', Fore.LIGHTWHITE_EX))
    _speed_limit = 1

    def update(self) -> None:
        pass


class SnakeEvent(Process, ABC):
    def __init__(self, snake: Snake):
        super().__init__()
        self.snake = snake

    @property
    def participants(self) -> tuple[Snake]:
        return (self.snake, )


class SnakeTailLengthKepeerEvent(SnakeEvent, DelayedProcess):
    _ticks_of_inactivity = 1

    def __init__(self, snake: Snake, tail_length_diapason: Diapason, tail_number: int = 1):
        super().__init__(snake)
        self.tail_number = tail_number
        self.tail_length_diapason = tail_length_diapason

    def _handle(self) -> None:
        if len(self.snake.tails) == self.tail_length_diapason.start:
            self.__is_growing_mode = True

        elif len(self.snake.tails) >= self.tail_length_diapason.end:
            self.__is_growing_mode = False

        getattr(self.snake, 'grow_tail' if self.__is_growing_mode else 'cut_tail')(self.tail_number)

        self.activate_delay()

    __is_growing_mode: bool = True


class SnakeHeadTurnEvent(SnakeEvent, DelayedProcess):
    _ticks_of_inactivity: int = 10

    def start(self) -> None:
        super().start()
        self._activate_snake_head_moving()

    def _handle(self) -> None:
        self._activate_snake_head_moving()
        self.__snake_head_vector = self.__snake_head_vector.get_rotated_by(
            AxisPlaneDegrees(0, 1, DegreeMeasure(90))
        )

        self.activate_delay()

    def _activate_snake_head_moving(self) -> None:
        self.snake.head.moving_process.original_process.vector_to_next_unit_position = self.__snake_head_vector

    __snake_head_vector = Vector((1, 0))


snake = Snake()
head = SnakeHead(Vector((10, 8)))

snake.init_parts(head, SnakeTail)
snake.grow_tail(5)


CustomAppFactory([CustomFactory(StandardSleepLoopHandler, 0.5)])(
    CustomWorld(
        [SnakeHeadTurnEvent(snake), SnakeTailLengthKepeerEvent(snake, Diapason(2, 9)), snake],
        [UnitMover, UnitUpdater, UnitAvatarRenderResourceParser]
    ),
    (ConsoleRender(ConsoleCell('.')), )
).run()
