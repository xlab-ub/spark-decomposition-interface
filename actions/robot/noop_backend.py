from typing import List, Optional

from robot.interface import RobotBackend
from robot.capabilities import GO1_ACTIONS


class NoopRobotBackend(RobotBackend):
    """Safe default backend: validates and accepts commands without hardware."""

    def __init__(self, connection_settings=None, audio=False):
        self.available_classes = [
            "person", "car", "backpack", "suitcase", "bottle", "cup",
            "banana", "apple", "orange", "pizza", "donut", "cake",
            "chair", "sofa", "tvmonitor", "laptop", "microwave",
            "refrigerator", "book", "clock",
        ]
        self.class_ids = []

    def get_recognized_objects(self) -> List[str]:
        return [self.available_classes[class_id] for class_id in self.class_ids]

    def get_frame(self) -> Optional[object]:
        return None

    def tts(self, text: str) -> None:
        return

    def check_simplified_syntax_validity(self, simplified_code: str) -> bool:
        return True

    def execute_simplified_syntax(self, simplified_code: str) -> None:
        print(f"[noop] Would execute:\n{simplified_code}")

    def get_available_actions(self) -> List[str]:
        return list(GO1_ACTIONS)
