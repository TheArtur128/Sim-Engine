from dataclasses import dataclass
from random import randint

from interfaces import IAvatar, IProcess


class Animation(IProcess, ABC):
    def __init__(self, avatar: IAvatar):
        self._avatar = avatar


@dataclass(frozen=True)
class RGBColor:
    red: int = 0
    green: int = 0
    blue: int = 0


class RainbowAvatar(IAvatar):
    current_color: RGBColor

    def __init__(self):
        self.change_color()

    @property
    def render_resource(self) -> RGBColor:
        self.change_color()
        return self.current_color

    def change_color(self) -> None:
        self.current_color = RGBColor(randint(0, 255), randint(0, 255), randint(0, 255))
