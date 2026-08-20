import ast
import json
import os
import threading
import time
from pathlib import Path

import numpy as np

from robot.interface import RobotBackend
from robot.syntax import HumanFriendlyPythonSyntaxConverter
from robot.rb10_1300e.function_library import function_library, condition_library
from robot.object_detector import YoloV7TinyDetector


def _wrap180(deg):
    return ((deg + 180.0) % 360.0) - 180.0


class rb10_1300e_highcommand(RobotBackend):
    DEFAULT_IP = "192.168.0.100"
    GRIP_CONN = "ToolFlange"

    HOME = [-4.083, 13.299, 150.997, 14.917, -98.262, -1.652]
    HOME_SPEED_BAR = 0.3
    HOME_JOINT_SPEED, HOME_JOINT_ACCEL = 60, 80

    JOG_SPEED_BAR = 0.5
    JOG_STEP_MM = 50.0            # forward/backward/left/right step
    JOG_STEP_MM_VERTICAL = 15.0   # up/down step
    JOG_SPEED, JOG_ACCEL = 45, 90

    GRIPPER_OPEN_POS = 0
    GRIPPER_CLOSE_POS = 50

    COLOR_W, COLOR_H, FPS = 640, 480, 30
    DETECTION_SLEEP_TIME = 0.3
    NEAR_AREA = 0.05

    REACH_SPEED_BAR = 0.15
    APPROACH_HEIGHT = 80.0            # mm, pass above the target before descending
    REACH_JOINT_SPEED, REACH_JOINT_ACCEL = 15, 30
    MAX_REACH_MM = 900.0              # reject targets farther than this from the base
    HORIZONTAL_RX = 180.0             # tcp rx when the gripper is level with the ground

    IK_MAX_ITERS = 30
    IK_TOL_MM = 1.0
    IK_TOL_DEG = 1.0
    IK_DAMPING = 2.0
    IK_EPS_DEG = 0.5
    IK_MAX_STEP_DEG = 10.0
    IK_ORIENT_WEIGHT = 5.0            # mm-per-degree weight for the rx row

    def __init__(self, connection_settings=None, audio=False):
        import rbpodo as rb
        self.rb = rb

        ip = connection_settings or os.environ.get("SPARK_RB10_IP", self.DEFAULT_IP)
        dry = os.environ.get("SPARK_RB10_DRY", "false").lower() in ("1", "true", "yes")
        print(f"[rb10_1300e] connecting to {ip} ({'Simulation' if dry else 'Real'} operation mode)")
        try:
            self.bot = rb.Cobot(ip)
            self.rc = rb.ResponseCollector()
            mode = rb.OperationMode.Simulation if dry else rb.OperationMode.Real
            self.bot.set_operation_mode(self.rc, mode)
            self.gc = getattr(rb.GripperConnectionPoint, self.GRIP_CONN)
            self.bot.gripper_rts_rhp12rn_select_mode(self.rc, self.gc, 0, 5.0)
            self.bot.flush(self.rc)
        except Exception as exc:
            raise RuntimeError(f"[rb10_1300e] cannot connect to the robot at {ip}: {exc}") from exc
        self._joint_vars = [getattr(rb.SystemVariable, f"SD_J{i}_ANG") for i in range(6)]

        self.near_area = float(os.environ.get("SPARK_RB10_NEAR_AREA", self.NEAR_AREA))
        self.step_mm = float(os.environ.get("SPARK_RB10_STEP_MM", self.JOG_STEP_MM))
        self.step_mm_vertical = float(os.environ.get("SPARK_RB10_STEP_MM_VERTICAL", self.JOG_STEP_MM_VERTICAL))
        self.holding = False          # tracked from gripper commands (no sensor feedback)
        self.found_after_find = {}
        self.search_target = None
        self.allowed_calls = {name.lower() for name in function_library} | {name.lower() for name in condition_library}

        # cam_to_base.json makes reach/PICK land on the correct 3D point; identity
        # fallback keeps the camera usable but reaching will be inaccurate.
        calib_path = Path(os.environ.get("SPARK_RB10_CALIB", "") or Path(__file__).resolve().parent / "cam_to_base.json")
        try:
            self.cam_to_base = np.array(json.loads(calib_path.read_text())["CAM_TO_BASE"])
        except (FileNotFoundError, KeyError, ValueError):
            print(f"[rb10_1300e] WARNING: {calib_path} not found, using identity calibration (PICK will be inaccurate)")
            self.cam_to_base = np.eye(4)

        self.detector = None
        self.available_classes = []
        self.class_ids = []
        self.centers = []
        self.areas = []
        self.detection_boxes = []
        self.detection_time = 0.0
        self.frame = None
        self.depth_m = None           # depth image in meters, aligned to color
        self.intrinsics = None
        self.frame_lock = threading.Lock()
        if os.environ.get("SPARK_RB10_CAMERA", "true").lower() in ("1", "true", "yes"):
            threading.Thread(target=self.get_camera_data, daemon=True).start()
            print('Camera loaded')
            try:
                self.detector = YoloV7TinyDetector()
                self.available_classes = self.detector.classes
                threading.Thread(target=self.get_detection_data, daemon=True).start()
                print('Object detection loaded')
            except Exception as e:
                print(f"[rb10_1300e] object detection unavailable: {e}")

    def get_camera_data(self):
        # RealSense color + aligned depth (the camera is mounted at the workcell).
        try:
            import pyrealsense2 as rs
            self.rs = rs
            pipeline = rs.pipeline()
            cfg = rs.config()
            cfg.enable_stream(rs.stream.color, self.COLOR_W, self.COLOR_H, rs.format.bgr8, self.FPS)
            cfg.enable_stream(rs.stream.depth, self.COLOR_W, self.COLOR_H, rs.format.z16, self.FPS)
            profile = pipeline.start(cfg)
            align = rs.align(rs.stream.color)
            self.intrinsics = profile.get_stream(rs.stream.color).as_video_stream_profile().get_intrinsics()
            depth_scale = profile.get_device().first_depth_sensor().get_depth_scale()
        except Exception as e:
            print(f"[rb10_1300e] camera unavailable: {e}")
            return
        while True:
            try:
                frames = align.process(pipeline.wait_for_frames())
                color, depth = frames.get_color_frame(), frames.get_depth_frame()
                if color and depth:
                    with self.frame_lock:
                        self.frame = np.asanyarray(color.get_data()).copy()
                        self.depth_m = np.asanyarray(depth.get_data()).astype(np.float32) * depth_scale
            except Exception as e:
                print(f"[rb10_1300e] camera error: {e}")
                time.sleep(1.0)

    def get_detection_data(self):
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
                    print(f"[rb10_1300e] detection error: {e}")
            time.sleep(self.DETECTION_SLEEP_TIME)

    def get_recognized_objects(self):
        with self.frame_lock:
            return [self.available_classes[class_id] for class_id in self.class_ids]

    def get_frame(self):
        with self.frame_lock:
            if self.frame is None:
                return np.zeros((self.COLOR_H, self.COLOR_W, 3), np.uint8)
            frame = self.frame.copy()
            # Detection always runs (NEAR/FAR need it), but the overlay only shows
            # the FIND target so the stream stays clean until the user asks.
            if self.search_target in self.available_classes:
                target_id = self.available_classes.index(self.search_target)
                boxes = [b for b in self.detection_boxes if b[4] == target_id]
            else:
                boxes = []
        if boxes:
            import cv2
            for x, y, w, h, class_id in boxes:
                cv2.rectangle(frame, (x, y), (x + w, y + h), (60, 220, 120), 2)
                cv2.putText(frame, self.available_classes[class_id], (x, max(y - 6, 12)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.45, (60, 220, 120), 1)
        return frame

    def tts(self, text):
        return

    # ------------------------------------------------------------------- motion
    def get_joints(self):
        self.bot.flush(self.rc)
        return [float(self.bot.get_system_variable(self.rc, sv)[1]) for sv in self._joint_vars]

    def _wait_move(self, timeout=60.0):
        # Wait in short chunks: the rbpodo waits are blocking C calls, and one
        # indefinite call starves the camera/web threads for the whole motion.
        r = self.bot.wait_for_move_started(self.rc, 1.0)
        if r.type() != self.rb.ReturnType.Success:
            return
        t_end = time.monotonic() + timeout
        while time.monotonic() < t_end:
            r = self.bot.wait_for_move_finished(self.rc, 0.1)
            if r.type() != self.rb.ReturnType.Timeout:
                return
            time.sleep(0.02)
        print("[rb10_1300e] move did not finish within the wait timeout")

    def _jog(self, dx, dy, dz):
        self.bot.flush(self.rc)
        self.bot.set_speed_bar(self.rc, self.JOG_SPEED_BAR)
        delta = np.array([dx, dy, dz, 0.0, 0.0, 0.0], dtype=float)
        self.bot.move_l_rel(self.rc, delta, self.JOG_SPEED, self.JOG_ACCEL, self.rb.ReferenceFrame.Base)
        self._wait_move()

    def move_home(self):
        self.bot.flush(self.rc)
        self.bot.set_speed_bar(self.rc, self.HOME_SPEED_BAR)
        self.bot.move_j(self.rc, np.array(self.HOME, dtype=float), self.HOME_JOINT_SPEED, self.HOME_JOINT_ACCEL)
        self._wait_move()

    def move_forward(self):
        self._jog(self.step_mm, 0.0, 0.0)

    def move_backward(self):
        self._jog(-self.step_mm, 0.0, 0.0)

    def move_left(self):
        self._jog(0.0, self.step_mm, 0.0)

    def move_right(self):
        self._jog(0.0, -self.step_mm, 0.0)

    def move_up(self):
        self._jog(0.0, 0.0, self.step_mm_vertical)

    def move_down(self):
        self._jog(0.0, 0.0, -self.step_mm_vertical)

    def stop(self):
        # Motions run blocking and sequentially, so this only aborts a queued task.
        self.bot.task_stop(self.rc)
        self.bot.flush(self.rc)

    def gripper_open(self):
        self.bot.gripper_rts_rhp12rn_position_control(self.rc, self.gc, self.GRIPPER_OPEN_POS, 5.0)
        self.bot.flush(self.rc)
        self.holding = False

    def gripper_close(self):
        self.bot.gripper_rts_rhp12rn_position_control(self.rc, self.gc, self.GRIPPER_CLOSE_POS, 5.0)
        self.bot.flush(self.rc)
        self.holding = True

    # ---------------------------------------------------------------------- IK
    def _fk(self, q):
        _, pose = self.bot.calc_fk_tcp(self.rc, *q.tolist())
        return np.array(pose)

    def _solve_ik(self, target_xyz, q0, target_rx=None):
        # Damped-least-squares IK with a numeric Jacobian (from rb10_skills.py).
        q = q0.copy()
        target_xyz = np.asarray(target_xyz, dtype=float)

        def err_of(pose):
            pos_err = target_xyz - pose[:3]
            if target_rx is None:
                return pos_err
            return np.append(pos_err, _wrap180(target_rx - pose[3]))

        for _ in range(self.IK_MAX_ITERS):
            pose = self._fk(q)
            err = err_of(pose)
            pos_ok = np.linalg.norm(err[:3]) < self.IK_TOL_MM
            rx_ok = target_rx is None or abs(err[3]) < self.IK_TOL_DEG
            if pos_ok and rx_ok:
                return q, True

            m = len(err)
            J = np.zeros((m, 6))
            for k in range(6):
                q_pert = q.copy()
                q_pert[k] += self.IK_EPS_DEG
                pose_pert = self._fk(q_pert)
                d_pos = (pose_pert[:3] - pose[:3]) / self.IK_EPS_DEG
                if target_rx is None:
                    J[:, k] = d_pos
                else:
                    d_rx = _wrap180(pose_pert[3] - pose[3]) / self.IK_EPS_DEG
                    J[:, k] = np.append(d_pos, d_rx)

            w = np.ones(m)
            if target_rx is not None:
                w[3] = self.IK_ORIENT_WEIGHT
            err_w, J_w = err * w, J * w[:, None]
            delta = J_w.T @ np.linalg.solve(J_w @ J_w.T + self.IK_DAMPING ** 2 * np.eye(m), err_w)
            q += np.clip(delta, -self.IK_MAX_STEP_DEG, self.IK_MAX_STEP_DEG)

        return q, False

    def _move_j(self, q):
        self.bot.flush(self.rc)
        self.bot.set_speed_bar(self.rc, self.REACH_SPEED_BAR)
        self.bot.move_j(self.rc, q, self.REACH_JOINT_SPEED, self.REACH_JOINT_ACCEL)
        self._wait_move()

    def _reach_point(self, x, y, z):
        # Approach from above, gripper level with the ground.
        dist = float(np.linalg.norm([x, y, z]))
        if dist > self.MAX_REACH_MM:
            print(f"[rb10_1300e] target is {dist:.0f}mm from base, exceeds {self.MAX_REACH_MM:.0f}mm, skipped")
            return False
        q0 = np.array(self.get_joints())
        q_approach, ok = self._solve_ik([x, y, z + self.APPROACH_HEIGHT], q0, target_rx=self.HORIZONTAL_RX)
        if not ok:
            print("[rb10_1300e] IK did not converge for the approach point, aborting")
            return False
        self._move_j(q_approach)
        q_target, ok = self._solve_ik([x, y, z], q_approach, target_rx=self.HORIZONTAL_RX)
        if not ok:
            print("[rb10_1300e] IK did not converge for the target point, aborting")
            return False
        self._move_j(q_target)
        return True

    def _target_pixel(self, object_name):
        # Center pixel of the freshest, largest detection of the object class.
        if object_name not in self.available_classes:
            return None
        target_id = self.available_classes.index(object_name)
        with self.frame_lock:
            candidates = [(w * h, x + w // 2, y + h // 2)
                          for (x, y, w, h, c) in self.detection_boxes if c == target_id]
        if not candidates:
            return None
        _, u, v = max(candidates)
        return u, v

    def reach(self, object_to_reach=None):
        # Move the TCP to the detected object (no gripper action: the program
        # composes REACH / GRIPPER_CLOSE / MOVE_UP explicitly).
        target = object_to_reach or self.search_target
        if target is None:
            print("[rb10_1300e] REACH: no target (say e.g. REACH APPLE, or FIND first)")
            return
        if self.detector is None or self.intrinsics is None:
            print(f"[rb10_1300e] REACH {target}: camera/detection unavailable")
            return
        pixel = self._target_pixel(target)
        if pixel is None:
            print(f"[rb10_1300e] REACH {target}: not in view")
            return
        u, v = pixel
        with self.frame_lock:
            z = float(self.depth_m[v, u]) if self.depth_m is not None else 0.0
        if z <= 0:
            print(f"[rb10_1300e] REACH {target}: no valid depth at ({u},{v})")
            return
        point_cam = np.array(self.rs.rs2_deproject_pixel_to_point(self.intrinsics, [u, v], z))
        x, y, z_mm = (self.cam_to_base @ np.append(point_cam * 1000.0, 1.0))[:3]
        print(f"[rb10_1300e] REACH {target}: pixel=({u},{v}) -> base(mm)=({x:.0f},{y:.0f},{z_mm:.0f})")
        self._reach_point(x, y, z_mm)

    # ------------------------------------------------------------------- vision
    def find(self, object_to_find=None):
        # The camera is fixed: just check the current view (no scanning motion).
        self.search_target = object_to_find
        self.found_after_find[object_to_find] = False
        if self.detector is None:
            print(f"[rb10_1300e] FIND {object_to_find}: object detection unavailable")
            return
        if object_to_find not in self.available_classes:
            print(f"[rb10_1300e] FIND {object_to_find}: unknown object class (COCO names only)")
            return
        deadline = time.monotonic() + 2.0
        target_id = self.available_classes.index(object_to_find)
        while time.monotonic() < deadline:
            with self.frame_lock:
                fresh = self.detection_time > 0 and target_id in self.class_ids
            if fresh:
                self.found_after_find[object_to_find] = True
                print(f"[rb10_1300e] FIND {object_to_find}: found")
                return
            time.sleep(0.1)
        print(f"[rb10_1300e] FIND {object_to_find}: not in view")

    def found(self, object_to_find=None):
        if object_to_find in self.found_after_find:
            return self.found_after_find[object_to_find]
        return False

    def _target_area(self):
        with self.frame_lock:
            if not self.class_ids:
                return None
            if self.search_target in self.available_classes:
                target_id = self.available_classes.index(self.search_target)
                candidate_areas = [a for c, a in zip(self.class_ids, self.areas) if c == target_id]
            else:
                candidate_areas = list(self.areas)
        return max(candidate_areas) if candidate_areas else None

    def near(self):
        area = self._target_area()
        return area is not None and area >= self.near_area

    def far(self):
        area = self._target_area()
        return area is not None and area < self.near_area

    def gripper_holding(self):
        return self.holding

    # -------------------------------------------------------------------- spark
    def check_simplified_syntax_validity(self, simplified_code):
        standard_code = HumanFriendlyPythonSyntaxConverter.to_standard_syntax(simplified_code, True)

        try:
            parsed_code = ast.parse(standard_code)

            for node in ast.walk(parsed_code):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                    if isinstance(node.func.value, ast.Name) and node.func.value.id == 'self':
                        attr_name = node.func.attr
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


def create_rb10_1300e_backend(connection_settings=None, audio=False):
    return rb10_1300e_highcommand(connection_settings=connection_settings, audio=audio)


__all__ = ["create_rb10_1300e_backend", "rb10_1300e_highcommand"]
