import ast
from typing import List, Optional

from robot.interface import RobotBackend
from robot.syntax import HumanFriendlyPythonSyntaxConverter
from robot.rb10_1300e.function_library import function_library, condition_library


class NoopRobotBackend(RobotBackend):
    """Rainbow Robotics RB10-1300E dry-run backend: checks commands against the rb10_1300e vocabulary and logs them (no hardware)."""

    def __init__(self, connection_settings=None, audio=False):
        self.available_classes = [
            "person", "car", "backpack", "suitcase", "bottle", "cup",
            "banana", "apple", "orange", "pizza", "donut", "cake",
            "chair", "sofa", "tvmonitor", "laptop", "microwave",
            "refrigerator", "book", "clock",
        ]
        self.class_ids = []
        # Lower-case method names the converted program may call on self.
        self.allowed_calls = {name.lower() for name in function_library} | {name.lower() for name in condition_library}

    def get_recognized_objects(self) -> List[str]:
        return [self.available_classes[class_id] for class_id in self.class_ids]

    def get_frame(self) -> Optional[object]:
        return None

    def tts(self, text: str) -> None:
        return

    def check_simplified_syntax_validity(self, simplified_code: str) -> bool:
        standard_code = HumanFriendlyPythonSyntaxConverter.to_standard_syntax(simplified_code, True)
        try:
            parsed_code = ast.parse(standard_code)
        except SyntaxError as e:
            print(f"[rb10_1300e-noop] Invalid syntax: {e}")
            return False
        for node in ast.walk(parsed_code):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name) and func.value.id == "self":
                if func.attr not in self.allowed_calls:
                    print(f"[rb10_1300e-noop] Unknown command for rb10_1300e: {func.attr}")
                    return False
            elif isinstance(func, ast.Name) and func.id == "range":
                continue
            else:
                print("[rb10_1300e-noop] Function call does not start with 'self.'")
                return False
        return True

    def execute_simplified_syntax(self, simplified_code: str) -> None:
        print(f"[rb10_1300e-noop] Would execute:\n{simplified_code}")
