import os
import sys

SDK_DIR = os.path.join(os.path.dirname(__file__), "free_dog_sdk")
if SDK_DIR not in sys.path:
    sys.path.insert(0, SDK_DIR)

from go1_instruction_with_camera_and_sensors_and_sound import go1_highcommand  # noqa: E402
from ucl.unitreeConnection import HIGH_WIFI_DEFAULTS, HIGH_WIRED_DEFAULTS  # noqa: E402


def create_go1_backend(connection_settings=None, audio=False):
    if connection_settings is None:
        connection_settings = HIGH_WIFI_DEFAULTS
    return go1_highcommand(connection_settings=connection_settings, audio=audio)


__all__ = ["create_go1_backend", "go1_highcommand", "HIGH_WIFI_DEFAULTS", "HIGH_WIRED_DEFAULTS"]
