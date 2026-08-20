# Unitree G1 backend, same command set as the verified test menu in
# ~/taegyu/Robot/G1/g1_run.py (wired Ethernet DDS via the official unitree_sdk2py
# LocoClient for walking + G1ArmActionClient for arm motions).
# Enter NORMAL mode with the remote first: L2+B -> L2+Up -> R1+Y.
# Tunables (SPARK_G1_*) are read from the environment, see .env.example.

import ast
import os
import time

import numpy as np

from robot.interface import RobotBackend
from robot.syntax import HumanFriendlyPythonSyntaxConverter
from robot.g1.function_library import function_library, condition_library


def detect_nic(subnet="192.168.123."):
    # Find the network interface holding an address on the robot subnet.
    import socket, fcntl, struct
    for _, name in socket.if_nameindex():
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            ip = socket.inet_ntoa(fcntl.ioctl(s.fileno(), 0x8915, struct.pack("256s", name[:15].encode()))[20:24])
        except OSError:
            continue
        finally:
            s.close()
        if ip.startswith(subnet):
            return name
    raise RuntimeError(f"No interface with a {subnet}x address (check cable and PC IP 192.168.123.222, "
                       f"or set SPARK_G1_IFACE)")


class g1_highcommand(RobotBackend):
    DEFAULT_VELOCITY = 0.3            # m/s, forward/backward
    DEFAULT_LATERAL_VELOCITY = 0.3    # m/s, left/right
    DEFAULT_YAW_SPEED = 0.3           # rad/s, turns

    MOVE_SLEEP_TIME = 2.0             # one MOVE_* step duration (Move() is held ~1 s -> resend)
    TURN_SLEEP_TIME = 2.0             # one TURN_* step duration
    MOVE_RESEND_TIME = 0.4

    STAND_UP_SLEEP_TIME = 5           # Squat2StandUp playback
    STAND_DOWN_SLEEP_TIME = 4         # StandUp2Squat playback
    WAVE_HAND_SLEEP_TIME = 3
    SHAKE_HAND_SLEEP_TIME = 3         # between the two ShakeHand() calls (start/stop)
    ARM_ACTION_SLEEP_TIME = 2         # before "release arm" (same as g1_run.py)

    # Arm actions that must be released after playing (same pattern as g1_run.py).
    ARM_ACTIONS_WITH_RELEASE = ("high five", "hug", "heart", "hands up")

    def __init__(self, connection_settings=None, audio=False):
        from unitree_sdk2py.core.channel import ChannelFactoryInitialize
        from unitree_sdk2py.g1.loco.g1_loco_client import LocoClient
        from unitree_sdk2py.g1.arm.g1_arm_action_client import G1ArmActionClient, action_map

        subnet = os.environ.get("SPARK_G1_SUBNET", "192.168.123.")
        iface = connection_settings or os.environ.get("SPARK_G1_IFACE") or detect_nic(subnet)
        print(f"[g1] wired: DDS on interface {iface}")
        ChannelFactoryInitialize(0, iface)

        self.loco_client = LocoClient()
        self.loco_client.SetTimeout(10.0)
        self.loco_client.Init()

        self.arm_client = G1ArmActionClient()
        self.arm_client.SetTimeout(10.0)
        self.arm_client.Init()
        self.action_map = action_map

        self.velocity = float(os.environ.get("SPARK_G1_VX", self.DEFAULT_VELOCITY))
        self.lateral_velocity = float(os.environ.get("SPARK_G1_VY", self.DEFAULT_LATERAL_VELOCITY))
        self.yaw_speed = float(os.environ.get("SPARK_G1_VYAW", self.DEFAULT_YAW_SPEED))
        self.move_seconds = float(os.environ.get("SPARK_G1_MOVE_SECONDS", self.MOVE_SLEEP_TIME))
        self.turn_seconds = float(os.environ.get("SPARK_G1_TURN_SECONDS", self.TURN_SLEEP_TIME))

        self.ready_to_move = False    # walk mode entered (Start(), remote R1+Y equivalent)
        self.found_after_find = {}
        self.search_target = None
        self.allowed_calls = {name.lower() for name in function_library} | {name.lower() for name in condition_library}

    def get_recognized_objects(self):
        return []

    def get_frame(self):
        # No camera source is wired up on the G1 yet; the web stream needs a frame.
        return np.zeros((360, 640, 3), np.uint8)

    def tts(self, text):
        return

    def get_ready_to_move_when_standing(self):
        # Move() needs walk mode: Start() is the menu id 16 / remote R1+Y step.
        if not self.ready_to_move:
            self.loco_client.Start()
            time.sleep(1.0)
            self.ready_to_move = True

    def _move(self, vx, vy, vyaw, seconds):
        # Move() is held for about a second: resend until the step ends, then stop.
        self.get_ready_to_move_when_standing()
        t_end = time.monotonic() + seconds
        while time.monotonic() < t_end:
            self.loco_client.Move(vx, vy, vyaw)
            time.sleep(self.MOVE_RESEND_TIME)
        self.loco_client.StopMove()

    def _arm_action(self, name):
        # Same pattern as g1_run.py: play the arm action, then release if needed.
        ret = self.arm_client.ExecuteAction(self.action_map.get(name))
        if ret not in (0, None):
            print(f"[g1] arm action {name!r} ret={ret}")
        time.sleep(self.ARM_ACTION_SLEEP_TIME)
        if name in self.ARM_ACTIONS_WITH_RELEASE:
            self.arm_client.ExecuteAction(self.action_map.get("release arm"))
            time.sleep(1.0)

    # Conditions for IF / WHILE. No camera is wired up on the real G1 yet,
    # so these stay False (a WHILE FAR loop then simply never runs).
    def far(self):
        return False

    def near(self):
        return False

    def found(self, object_to_find=None):
        if object_to_find in self.found_after_find:
            return self.found_after_find[object_to_find]
        return False

    def stand_up(self):
        # Same sequence as menu id 1 (verified): damp, then Squat2StandUp.
        self.loco_client.Damp()
        time.sleep(0.5)
        self.loco_client.Squat2StandUp()
        time.sleep(self.STAND_UP_SLEEP_TIME)
        self.ready_to_move = False    # walk mode must be (re)entered before Move()

    def stand_down(self):
        self.loco_client.StandUp2Squat()
        time.sleep(self.STAND_DOWN_SLEEP_TIME)
        self.ready_to_move = False

    def stop(self):
        self.loco_client.StopMove()

    def move_forward(self):
        self._move(self.velocity, 0, 0, self.move_seconds)

    def move_backward(self):
        self._move(-self.velocity, 0, 0, self.move_seconds)

    def move_left(self):
        self._move(0, self.lateral_velocity, 0, self.move_seconds)

    def move_right(self):
        self._move(0, -self.lateral_velocity, 0, self.move_seconds)

    def turn_left(self):
        self._move(0, 0, self.yaw_speed, self.turn_seconds)

    def turn_right(self):
        self._move(0, 0, -self.yaw_speed, self.turn_seconds)

    def wave_hand(self):
        self.loco_client.WaveHand()
        time.sleep(self.WAVE_HAND_SLEEP_TIME)

    def shake_hand(self):
        # Menu id 11: first call starts the handshake pose, second call ends it.
        self.loco_client.ShakeHand()
        time.sleep(self.SHAKE_HAND_SLEEP_TIME)
        self.loco_client.ShakeHand()
        time.sleep(1.0)

    def high_five(self):
        self._arm_action("high five")

    def hug(self):
        self._arm_action("hug")

    def clap(self):
        self._arm_action("clap")

    def heart(self):
        self._arm_action("heart")

    def hands_up(self):
        self._arm_action("hands up")

    def find(self, object_to_find=None):
        # No camera source on the G1 yet: remember the target, found() stays False.
        self.search_target = object_to_find
        self.found_after_find[object_to_find] = False
        print(f"[g1] FIND {object_to_find}: camera not wired yet")

    def check_simplified_syntax_validity(self, simplified_code):
        standard_code = HumanFriendlyPythonSyntaxConverter.to_standard_syntax(simplified_code, True)

        try:
            parsed_code = ast.parse(standard_code)

            for node in ast.walk(parsed_code):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                    if isinstance(node.func.value, ast.Name) and node.func.value.id == 'self':
                        attr_name = node.func.attr
                        # Vocabulary check instead of go1's hasattr: only actions from
                        # function_library (+ conditions) are callable commands.
                        if attr_name not in self.allowed_calls:
                            print(f"Function {attr_name} not found")
                            return False
                    else:
                        print("Function call does not start with 'self.'")
                        return False
            return True
        except Exception as e:
            print(f"An error occurred: {e}")
            return False

    def execute_simplified_syntax(self, simplified_code):
        standard_code = HumanFriendlyPythonSyntaxConverter.to_standard_syntax(simplified_code, True)

        try:
            exec(standard_code)
        except Exception as e:
            print(e)
            print(f"Invalid syntax: {simplified_code}")


def create_g1_backend(connection_settings=None, audio=False):
    return g1_highcommand(connection_settings=connection_settings, audio=audio)


__all__ = ["create_g1_backend", "g1_highcommand"]
