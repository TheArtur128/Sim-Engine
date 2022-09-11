from time import sleep
from typing import Iterable

from interfaces import IUpdatable


class LoopUpdater:
    def __init__(self, updated_object: IUpdatable, timeout: int = 0):
        self.updated_object = updated_object
        self.timeout = timeout

    def run(self) -> None:
        while True:
            self.updated_object.update()

            if self.timeout > 0:
                sleep(self.timeout)
