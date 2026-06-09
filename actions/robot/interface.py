from abc import ABC, abstractmethod
from typing import List, Optional


class RobotBackend(ABC):
    @abstractmethod
    def check_simplified_syntax_validity(self, simplified_code: str) -> bool:
        pass

    @abstractmethod
    def execute_simplified_syntax(self, simplified_code: str) -> None:
        pass

    @abstractmethod
    def get_frame(self) -> Optional[object]:
        pass

    @abstractmethod
    def get_recognized_objects(self) -> List[str]:
        pass

    def tts(self, text: str) -> None:
        pass
