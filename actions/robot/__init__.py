import os
import sys

from config import ROBOT_BACKEND, TTS_ON

sys.path.insert(0, os.path.dirname(__file__))

from robot.go1.noop_backend import NoopRobotBackend


def create_robot_backend(connection_settings=None, audio=TTS_ON):
    if ROBOT_BACKEND == "go1":
        from robot.go1.go1_backend import create_go1_backend
        return create_go1_backend(connection_settings=connection_settings, audio=audio)
    # Unitree G1
    if ROBOT_BACKEND == "g1":
        from robot.g1.g1_backend import create_g1_backend
        return create_g1_backend(connection_settings=connection_settings, audio=audio)
    if ROBOT_BACKEND == "g1_sim":
        from robot.g1.g1_sim_backend import create_g1_sim_backend
        return create_g1_sim_backend(connection_settings=connection_settings, audio=audio)
    if ROBOT_BACKEND == "g1_noop":
        from robot.g1.noop_backend import NoopRobotBackend as G1NoopRobotBackend
        return G1NoopRobotBackend(connection_settings=connection_settings, audio=audio)
    # Unitree Go2
    if ROBOT_BACKEND == "go2":
        from robot.go2.go2_backend import create_go2_backend
        return create_go2_backend(connection_settings=connection_settings, audio=audio)
    if ROBOT_BACKEND == "go2_sim":
        from robot.go2.go2_sim_backend import create_go2_sim_backend
        return create_go2_sim_backend(connection_settings=connection_settings, audio=audio)
    if ROBOT_BACKEND == "go2_noop":
        from robot.go2.noop_backend import NoopRobotBackend as Go2NoopRobotBackend
        return Go2NoopRobotBackend(connection_settings=connection_settings, audio=audio)
    # Rainbow Robotics RB10-1300E
    if ROBOT_BACKEND == "rb10_1300e":
        from robot.rb10_1300e.rb10_1300e_backend import create_rb10_1300e_backend
        return create_rb10_1300e_backend(connection_settings=connection_settings, audio=audio)
    if ROBOT_BACKEND == "rb10_1300e_sim":
        from robot.rb10_1300e.rb10_1300e_sim_backend import create_rb10_1300e_sim_backend
        return create_rb10_1300e_sim_backend(connection_settings=connection_settings, audio=audio)
    if ROBOT_BACKEND == "rb10_1300e_noop":
        from robot.rb10_1300e.noop_backend import NoopRobotBackend as Rb10NoopRobotBackend
        return Rb10NoopRobotBackend(connection_settings=connection_settings, audio=audio)
    if ROBOT_BACKEND != "noop":
        print(f"[robot] Unknown SPARK_ROBOT_BACKEND={ROBOT_BACKEND!r}; falling back to noop (Go1 vocabulary)")
    return NoopRobotBackend(connection_settings=connection_settings, audio=audio)


def get_function_library():
    """Return the action vocabulary for the robot selected by SPARK_ROBOT_BACKEND (a fresh list)."""
    if ROBOT_BACKEND in ("g1", "g1_sim", "g1_noop"):
        from robot.g1.function_library import function_library
    elif ROBOT_BACKEND in ("go2", "go2_sim", "go2_noop"):
        from robot.go2.function_library import function_library
    elif ROBOT_BACKEND in ("rb10_1300e", "rb10_1300e_sim", "rb10_1300e_noop"):
        from robot.rb10_1300e.function_library import function_library
    else:  # "noop", "go1", or unknown -> original Go1 vocabulary
        from robot.go1.function_library import function_library
    return list(function_library)
