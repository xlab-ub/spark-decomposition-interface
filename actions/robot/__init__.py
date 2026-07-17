import os
import sys

from config import ROBOT_BACKEND, TTS_ON

sys.path.insert(0, os.path.dirname(__file__))

from robot.noop_backend import NoopRobotBackend


def create_robot_backend(connection_settings=None, audio=TTS_ON):
    if ROBOT_BACKEND == "go1":
        from robot.go1_backend import create_go1_backend
        return create_go1_backend(connection_settings=connection_settings, audio=audio)
    if ROBOT_BACKEND in {"go2", "go2_mujoco", "mujoco"}:
        from robot.go2_mujoco_backend import create_go2_mujoco_backend

        return create_go2_mujoco_backend(connection_settings=connection_settings, audio=audio)
    return NoopRobotBackend(connection_settings=connection_settings, audio=audio)
