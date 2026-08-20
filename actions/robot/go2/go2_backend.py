import ast
import os
import threading
import time

import numpy as np

from robot.interface import RobotBackend
from robot.syntax import HumanFriendlyPythonSyntaxConverter
from robot.go2.function_library import function_library, condition_library
from robot.object_detector import YoloV7TinyDetector


def detect_nic(subnet="192.168.123."):
    # Find the network interface holding an address on the robot subnet (wired).
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
                       f"or set SPARK_GO2_IFACE)")


class go2_highcommand(RobotBackend):
    DEFAULT_VELOCITY = 0.3            # m/s, forward/backward
    DEFAULT_LATERAL_VELOCITY = 0.3    # m/s, left/right
    DEFAULT_YAW_SPEED = 0.5           # rad/s, turns

    MOVE_SLEEP_TIME = 2.0             # one MOVE_* step duration (firmware holds a Move ~1 s -> resend)
    TURN_SLEEP_TIME = 2.0             # one TURN_* step duration (~57 deg at 0.5 rad/s)
    MOVE_RESEND_TIME = 0.4

    BALANCE_STAND_SLEEP_TIME = 1
    STAND_DOWN_SLEEP_TIME = 2
    RECOVERY_STAND_SLEEP_TIME = 2
    HELLO_SLEEP_TIME = 4
    SIT_SLEEP_TIME = 3
    RISE_SIT_SLEEP_TIME = 3
    STRETCH_SLEEP_TIME = 8
    DANCE1_SLEEP_TIME = 20

    CAMERA_SLEEP_TIME = 0.03
    DETECTION_SLEEP_TIME = 0.3        # YOLO pass period on the latest frame
    FIND_TIMEOUT = 25.0               # total seconds a FIND scan may take
    FIND_YAW_STEP_TIME = 1.0          # one scan rotation burst (~28 deg at 0.5 rad/s)
    NEAR_AREA = 0.05                  # target box area fraction that counts as "near"

    def __init__(self, connection_settings=None, audio=False):
        from unitree_sdk2py.core.channel import ChannelFactoryInitialize
        from unitree_sdk2py.go2.sport.sport_client import SportClient

        subnet = os.environ.get("SPARK_GO2_SUBNET", "192.168.123.")
        iface = connection_settings or os.environ.get("SPARK_GO2_IFACE") or detect_nic(subnet)
        print(f"[go2] DDS on interface {iface}")
        ChannelFactoryInitialize(0, iface)
        self.sport_client = SportClient()
        self.sport_client.SetTimeout(10.0)
        self.sport_client.Init()

        self.velocity = float(os.environ.get("SPARK_GO2_VX", self.DEFAULT_VELOCITY))
        self.lateral_velocity = float(os.environ.get("SPARK_GO2_VY", self.DEFAULT_LATERAL_VELOCITY))
        self.yaw_speed = float(os.environ.get("SPARK_GO2_VYAW", self.DEFAULT_YAW_SPEED))
        self.move_seconds = float(os.environ.get("SPARK_GO2_MOVE_SECONDS", self.MOVE_SLEEP_TIME))
        self.turn_seconds = float(os.environ.get("SPARK_GO2_TURN_SECONDS", self.TURN_SLEEP_TIME))

        self.find_timeout = float(os.environ.get("SPARK_GO2_FIND_TIMEOUT", self.FIND_TIMEOUT))
        self.near_area = float(os.environ.get("SPARK_GO2_NEAR_AREA", self.NEAR_AREA))

        self.ready_to_move = False    # balanced standing, Move() accepted
        self.found_after_find = {}
        self.search_target = None
        self.detector = None
        self.available_classes = []
        self.class_ids = []
        self.centers = []
        self.areas = []
        self.detection_time = 0.0    # monotonic time of the latest YOLO pass
        self.detection_boxes = []    # (x, y, w, h, class_id) of the latest YOLO pass
        self.allowed_calls = {name.lower() for name in function_library} | {name.lower() for name in condition_library}

        self.frame = None
        self.frame_lock = threading.Lock()
        if os.environ.get("SPARK_GO2_CAMERA", "true").lower() in ("1", "true", "yes"):
            threading.Thread(target=self.get_camera_data, daemon=True).start()
            print('Camera loaded')
            try:
                self.detector = YoloV7TinyDetector()
                self.available_classes = self.detector.classes
                threading.Thread(target=self.get_detection_data, daemon=True).start()
                print('Object detection loaded')
            except Exception as e:
                print(f"[go2] object detection unavailable: {e}")

    def get_camera_data(self):
        # Front camera via the VideoClient service, decoded to BGR.
        try:
            import cv2
            from unitree_sdk2py.go2.video.video_client import VideoClient
            video_client = VideoClient()
            video_client.SetTimeout(3.0)
            video_client.Init()
        except Exception as e:
            print(f"[go2] camera unavailable: {e}")
            return
        while True:
            code, data = video_client.GetImageSample()
            if code == 0:
                image = cv2.imdecode(np.frombuffer(bytes(data), dtype=np.uint8), cv2.IMREAD_COLOR)
                if image is not None:
                    with self.frame_lock:
                        self.frame = image
            time.sleep(self.CAMERA_SLEEP_TIME)

    def get_detection_data(self):
        # YOLO pass on the latest camera frame; feeds the conditions and the web overlay.
        while True:
            with self.frame_lock:
                frame = self.frame.copy() if self.frame is not None else None
            if frame is not None:
                try:
                    class_ids, centers, areas, boxes, _ = self.detector.detect(frame)
                    with self.frame_lock:
                        self.class_ids, self.centers, self.areas = class_ids, centers, areas
                        self.detection_boxes = [(x, y, w, h, c) for (x, y, w, h), c in zip(boxes, class_ids)]
                        self.detection_time = time.monotonic()
                except Exception as e:
                    print(f"[go2] detection error: {e}")
            time.sleep(self.DETECTION_SLEEP_TIME)

    def get_recognized_objects(self):
        with self.frame_lock:
            return [self.available_classes[class_id] for class_id in self.class_ids]

    def get_frame(self):
        # Never None (the web stream encodes this directly); boxes from the last
        # YOLO pass are drawn on the newest frame so the video runs at camera rate.
        with self.frame_lock:
            if self.frame is None:
                return np.zeros((360, 640, 3), np.uint8)
            frame = self.frame.copy()
            boxes = list(self.detection_boxes)
        if boxes:
            import cv2
            for x, y, w, h, class_id in boxes:
                cv2.rectangle(frame, (x, y), (x + w, y + h), (60, 220, 120), 2)
                cv2.putText(frame, self.available_classes[class_id], (x, max(y - 6, 12)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.45, (60, 220, 120), 1)
        return frame

    def tts(self, text):
        return

    def get_ready_to_move_when_standing(self):
        # StandUp() locks the joints: balanced standing is required before Move().
        if not self.ready_to_move:
            self.sport_client.BalanceStand()
            time.sleep(0.5)
            self.ready_to_move = True

    def _move(self, vx, vy, vyaw, seconds):
        # The firmware holds one Move() for ~1 s: resend until the step ends, then stop.
        self.get_ready_to_move_when_standing()
        t_end = time.monotonic() + seconds
        while time.monotonic() < t_end:
            ret = self.sport_client.Move(vx, vy, vyaw)
            if ret != 0:
                print(f"[go2] Move ret={ret} (need balanced standing?)")
                break
            time.sleep(self.MOVE_RESEND_TIME)
        self.sport_client.StopMove()

    def _trick(self, name, call, sleep_time):
        # Trick RPCs return before the motion ends: sleep so the next command does not interrupt it.
        self.get_ready_to_move_when_standing()
        ret = call()
        if ret not in (0, None):
            print(f"[go2] {name} ret={ret}")
        time.sleep(sleep_time)

    def _target_area(self):
        # Area of the FIND target, or of the largest detection when no target is set.
        with self.frame_lock:
            if not self.class_ids:
                return None
            if self.search_target in self.available_classes:
                target_id = self.available_classes.index(self.search_target)
                candidate_areas = [a for c, a in zip(self.class_ids, self.areas) if c == target_id]
            else:
                candidate_areas = list(self.areas)
        return max(candidate_areas) if candidate_areas else None

    # Conditions for IF / WHILE: box area approximates distance (monocular).
    def near(self):
        area = self._target_area()
        return area is not None and area >= self.near_area

    def far(self):
        # Not visible -> False, so a WHILE FAR loop stops instead of walking blind.
        area = self._target_area()
        return area is not None and area < self.near_area

    def found(self, object_to_find=None):
        if object_to_find in self.found_after_find:
            return self.found_after_find[object_to_find]
        return False

    def stand_down(self):
        self.sport_client.StandDown()
        time.sleep(self.STAND_DOWN_SLEEP_TIME)
        self.ready_to_move = False

    def stand_up(self):
        self.sport_client.BalanceStand()
        time.sleep(self.BALANCE_STAND_SLEEP_TIME)
        self.ready_to_move = True

    def recovery_stand(self):
        self.sport_client.RecoveryStand()
        time.sleep(self.RECOVERY_STAND_SLEEP_TIME)
        self.ready_to_move = True

    def stop(self):
        self.sport_client.StopMove()

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

    def hello(self):
        self._trick('hello', self.sport_client.Hello, self.HELLO_SLEEP_TIME)

    def sit(self):
        self._trick('sit', self.sport_client.Sit, self.SIT_SLEEP_TIME)
        self.ready_to_move = False

    def rise_sit(self):
        self._trick('rise_sit', self.sport_client.RiseSit, self.RISE_SIT_SLEEP_TIME)
        self.ready_to_move = True

    def stretch(self):
        self._trick('stretch', self.sport_client.Stretch, self.STRETCH_SLEEP_TIME)

    def dance(self):
        self._trick('dance', self.sport_client.Dance1, self.DANCE1_SLEEP_TIME)

    def _fresh_detection_ids(self, after_time):
        # Wait for a YOLO pass newer than after_time (skip stale pre-rotation results).
        deadline = time.monotonic() + 3.0
        while time.monotonic() < deadline:
            with self.frame_lock:
                if self.detection_time > after_time:
                    return list(self.class_ids)
            time.sleep(0.05)
        return []

    def find(self, object_to_find=None):
        # Rotate step by step until the class is seen or the timeout expires.
        self.search_target = object_to_find
        self.found_after_find[object_to_find] = False
        if self.detector is None:
            print(f"[go2] FIND {object_to_find}: object detection unavailable")
            return
        if object_to_find not in self.available_classes:
            print(f"[go2] FIND {object_to_find}: unknown object class (COCO names only)")
            return
        target_id = self.available_classes.index(object_to_find)

        self.get_ready_to_move_when_standing()
        t_end = time.monotonic() + self.find_timeout
        while time.monotonic() < t_end:
            if target_id in self._fresh_detection_ids(time.monotonic()):
                self.found_after_find[object_to_find] = True
                print(f"[go2] FIND {object_to_find}: found")
                return
            step_end = time.monotonic() + self.FIND_YAW_STEP_TIME
            while time.monotonic() < step_end:
                self.sport_client.Move(0, 0, self.yaw_speed)
                time.sleep(self.MOVE_RESEND_TIME)
            self.sport_client.StopMove()
            time.sleep(0.3)  # settle before the fresh detection check
        print(f"[go2] FIND {object_to_find}: not found within {self.find_timeout:.0f}s")

    def check_simplified_syntax_validity(self, simplified_code):
        standard_code = HumanFriendlyPythonSyntaxConverter.to_standard_syntax(simplified_code, True)

        try:
            parsed_code = ast.parse(standard_code)

            for node in ast.walk(parsed_code):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                    if isinstance(node.func.value, ast.Name) and node.func.value.id == 'self':
                        attr_name = node.func.attr
                        # Vocabulary check instead of go1's hasattr.
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


def create_go2_backend(connection_settings=None, audio=False):
    return go2_highcommand(connection_settings=connection_settings, audio=audio)


__all__ = ["create_go2_backend", "go2_highcommand"]
