from abc import ABCMeta, abstractmethod
from typing import Iterable


class TextSplitterInterface(metaclass=ABCMeta):
    @abstractmethod
    def split(self, text: str) -> Iterable[str]:
        ...
