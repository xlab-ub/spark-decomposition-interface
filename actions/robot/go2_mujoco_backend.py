import atexit
import os
import ast
import threading
import time
from pathlib import Path
from typing import List, Optional

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from config import (
    GO2_MUJOCO_HEADLESS,
    GO2_MUJOCO_DETECTION_DT,
    GO2_MUJOCO_FIND_TIMEOUT,
    GO2_MUJOCO_FIND_YAW_STEP,
    GO2_MUJOCO_LINEAR_SPEED,
    GO2_MUJOCO_ANGULAR_SPEED,
    GO2_MUJOCO_RENDER_DT,
    GO2_MUJOCO_RENDER_HEIGHT,
    GO2_MUJOCO_RENDER_WIDTH,
    GO2_MUJOCO_ROOT,
    GO2_MUJOCO_SCENE,
    GO2_MUJOCO_SIM_DT,
)
from robot.syntax import HumanFriendlyPythonSyntaxConverter
from robot.interface import RobotBackend
from robot.capabilities import GO2_MUJOCO_ACTIONS
from robot.object_detector import YoloV7TinyDetector


try:
    if GO2_MUJOCO_HEADLESS:
        os.environ["MUJOCO_GL"] = "egl"
    import mujoco
except Exception as exc:  # pragma: no cover - exercised only when mujoco is missing
    mujoco = None
    MUJOCO_IMPORT_ERROR = exc
else:
    MUJOCO_IMPORT_ERROR = None


class Go2MujocoBackend(RobotBackend):
    """Go2 MuJoCo adapter for Spark's discrete, high-level primitives.

    Unitree's MuJoCo bridge accepts low-level motor commands only.  Spark uses
    discrete high-level actions, so this backend maintains a stable kinematic
    pose in the MJCF model instead of pretending that Go2 SportClient RPCs are
    available in the simulator.
    """

    _STAND_UP_JOINT_POS = np.array([
        0.00571868, 0.608813, -1.21763,
        -0.00571868, 0.608813, -1.21763,
        0.00571868, 0.608813, -1.21763,
        -0.00571868, 0.608813, -1.21763,
    ], dtype=float)
    _STAND_DOWN_JOINT_POS = np.array([
        0.0473455, 1.22187, -2.44375,
        -0.0473455, 1.22187, -2.44375,
        0.0473455, 1.22187, -2.44375,
        -0.0473455, 1.22187, -2.44375,
    ], dtype=float)
    _START_POSE = {
        "x": 0.0,
        "y": 0.0,
        "z": 0.445,
        "roll": 0.0,
        "pitch": 0.0,
        "yaw": 0.0,
    }
    _GAIT_CADENCE_HZ = 2.5
    _GAIT_THIGH_SWING = 0.24
    _GAIT_CALF_LIFT = 0.34
    _GAIT_RETURN_RATE = 6.0

    def __init__(self, connection_settings=None, audio=False):
        self.connection_settings = connection_settings
        self.audio = audio
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._last_command = "idle"
        self._recognized_objects = ["go2_mujoco_simulation"]
        self._scene_path = self._resolve_scene_path()
        self._model = None
        self._data = None
        self._renderer = None
        self._front_renderer = None
        self._camera = None
        self._render_mode = "schematic"
        self._command_status = "standing"
        self._search_target = None
        self._pose = dict(self._START_POSE)
        self._target_pose = dict(self._START_POSE)
        self._joint_targets = self._STAND_UP_JOINT_POS.copy()
        self._base_joint_targets = self._STAND_UP_JOINT_POS.copy()
        self._gait_phase = 0.0
        self._standing_height = self._START_POSE["z"]
        self._stand_down_height = 0.18
        self._found_objects = set()
        self._class_ids = []
        self._centers = []
        self._front_frame = None
        self._front_frame_sequence = 0
        self._detection_sequence = 0
        self._detector = None
        self._frame = self._create_placeholder_frame(
            "Go2 MuJoCo simulation is starting..."
        )
        self._simulation_thread = None
        self._detection_thread = None

        self._load_simulation()
        try:
            self._detector = YoloV7TinyDetector()
        except Exception as exc:
            print(f"[go2_mujoco] object detector unavailable: {exc}")
        self._simulation_thread = threading.Thread(target=self._simulation_loop, daemon=True)
        self._simulation_thread.start()
        if self._detector is not None:
            self._detection_thread = threading.Thread(target=self._detection_loop, daemon=True)
            self._detection_thread.start()
        atexit.register(self.close)

    def _resolve_scene_path(self) -> Optional[Path]:
        candidates: List[Path] = []

        if GO2_MUJOCO_SCENE:
            candidates.append(Path(GO2_MUJOCO_SCENE).expanduser())

        root_path = Path(GO2_MUJOCO_ROOT).expanduser()
        candidates.extend(
            [
                root_path / "unitree_robots" / "go2" / "scene.xml",
                root_path / "unitree_robots" / "go2" / "scene_terrain.xml",
            ]
        )

        repo_root = Path(__file__).resolve().parents[2]
        candidates.extend(
            [
                repo_root / "actions" / "robot" / "unitree_mujoco" / "unitree_robots" / "go2" / "scene.xml",
                repo_root / "actions" / "robot" / "unitree_mujoco" / "unitree_robots" / "go2" / "scene_terrain.xml",
            ]
        )

        for candidate in candidates:
            candidate = candidate.resolve()
            if candidate.is_file():
                return candidate

        return None

    def _build_placeholder_xml(self) -> str:
        return """<mujoco model='go2_placeholder'>
  <option timestep='0.005'/>
  <worldbody>
    <light pos='0 0 3' dir='0 0 -1'/>
    <geom name='floor' type='plane' size='4 4 0.1' rgba='0.15 0.18 0.2 1'/>
    <body name='base_link' pos='0 0 0.35'>
      <freejoint/>
      <geom name='torso' type='box' size='0.18 0.08 0.12' rgba='0.14 0.45 0.85 1'/>
      <geom name='head' type='sphere' pos='0.17 0 0.08' size='0.05' rgba='0.85 0.85 0.9 1'/>
      <body name='front_left_leg' pos='0.12 0.08 -0.2'>
        <geom type='capsule' fromto='0 0 0 0 0 -0.24' size='0.025' rgba='0.2 0.2 0.22 1'/>
      </body>
      <body name='front_right_leg' pos='0.12 -0.08 -0.2'>
        <geom type='capsule' fromto='0 0 0 0 0 -0.24' size='0.025' rgba='0.2 0.2 0.22 1'/>
      </body>
      <body name='rear_left_leg' pos='-0.12 0.08 -0.2'>
        <geom type='capsule' fromto='0 0 0 0 0 -0.24' size='0.025' rgba='0.2 0.2 0.22 1'/>
      </body>
      <body name='rear_right_leg' pos='-0.12 -0.08 -0.2'>
        <geom type='capsule' fromto='0 0 0 0 0 -0.24' size='0.025' rgba='0.2 0.2 0.22 1'/>
      </body>
    </body>
  </worldbody>
</mujoco>"""

    def _load_simulation(self) -> None:
        if mujoco is None:
            print(f"[go2_mujoco] mujoco import failed: {MUJOCO_IMPORT_ERROR}")
            return

        if self._scene_path is not None:
            print(f"[go2_mujoco] Loading Go2 scene from {self._scene_path}")
            # Add Spark's sensor camera at model-construction time instead of
            # modifying the external unitree_mujoco checkout. This keeps a
            # normal upstream clone reproducible and clean.
            self._model = mujoco.MjModel.from_xml_path(str(self._scene_path))
            camera_id = mujoco.mj_name2id(
                self._model, mujoco.mjtObj.mjOBJ_CAMERA, "front_camera"
            )
            if camera_id < 0:
                spec = mujoco.MjSpec()
                spec.from_file(str(self._scene_path))
                base_body = spec.find_body("base_link")
                if base_body is not None:
                    front_camera = base_body.add_camera(name="front_camera")
                    front_camera.pos = [0.31, 0.0, 0.015]
                    front_camera.quat = [-0.5, -0.5, 0.5, 0.5]
                    front_camera.fovy = 70.0
                    self._model = spec.compile()
        else:
            print("[go2_mujoco] Go2 scene not found; using a built-in placeholder model")
            self._model = mujoco.MjModel.from_xml_string(self._build_placeholder_xml())

        self._model.opt.timestep = GO2_MUJOCO_SIM_DT
        self._data = mujoco.MjData(self._model)
        mujoco.mj_resetData(self._model, self._data)
        self._recognized_objects = self._extract_named_bodies()
        # Start every Spark session at a deterministic origin in the same
        # standing configuration as the Go2 MJCF.  Previously the base stayed
        # at standing height while folded STAND_DOWN joints were applied,
        # making the robot appear to float above the floor.
        self._pose = dict(self._START_POSE)
        self._apply_joint_targets(self._joint_targets)
        self._apply_pose_to_model()
        self._standing_height = self._calibrate_standing_height()
        self._stand_down_height = self._calibrate_posture_height(
            self._STAND_DOWN_JOINT_POS
        )
        self._pose["z"] = self._standing_height
        self._target_pose = dict(self._pose)
        self._apply_pose_to_model()
        self._last_command = "STAND_UP"
        self._set_status("standing")
        self._frame = self._create_placeholder_frame("Go2 MuJoCo simulation is starting...")

    def _try_create_renderer(self):
        if mujoco is None or self._model is None:
            return None

        try:
            renderer = mujoco.Renderer(
                self._model,
                height=GO2_MUJOCO_RENDER_HEIGHT,
                width=GO2_MUJOCO_RENDER_WIDTH,
            )
            camera = mujoco.MjvCamera()
            base_body_id = mujoco.mj_name2id(self._model, mujoco.mjtObj.mjOBJ_BODY, "base_link")
            camera.type = mujoco.mjtCamera.mjCAMERA_TRACKING
            camera.trackbodyid = base_body_id if base_body_id >= 0 else 1
            camera.distance = 2.8
            camera.azimuth = 135
            camera.elevation = -18
            camera.lookat = np.array([0.0, 0.0, 0.35])
            self._camera = camera
            self._render_mode = "mujoco"
            return renderer
        except Exception:
            self._render_mode = "schematic"
            self._camera = None
            return None

    def _ensure_renderer(self) -> bool:
        if self._renderer is not None:
            return True
        self._renderer = self._try_create_renderer()
        return self._renderer is not None

    def _ensure_front_renderer(self) -> bool:
        if self._front_renderer is not None:
            return True
        if mujoco is None or self._model is None:
            return False
        camera_id = mujoco.mj_name2id(
            self._model, mujoco.mjtObj.mjOBJ_CAMERA, "front_camera"
        )
        if camera_id < 0:
            return False
        try:
            self._front_renderer = mujoco.Renderer(
                self._model,
                height=GO2_MUJOCO_RENDER_HEIGHT,
                width=GO2_MUJOCO_RENDER_WIDTH,
            )
            return True
        except Exception as exc:
            print(f"[go2_mujoco] front camera renderer unavailable: {exc}")
            return False

    def _render_front_camera(self) -> bool:
        """Render the sensor frame only; inference runs on another thread."""
        if not self._ensure_front_renderer():
            return False
        try:
            self._front_renderer.update_scene(self._data, camera="front_camera")
            rgb_frame = self._front_renderer.render()
            self._front_frame = np.asarray(rgb_frame)[:, :, ::-1].copy()
            self._front_frame_sequence += 1
            return True
        except Exception as exc:
            print(f"[go2_mujoco] front camera render failed: {exc}")
            if self._front_renderer is not None:
                try:
                    self._front_renderer.close()
                except Exception:
                    pass
                self._front_renderer = None
            return False

    def _detection_loop(self) -> None:
        """Analyze snapshots without blocking MuJoCo rendering."""
        last_frame_sequence = -1
        while not self._stop_event.is_set():
            started = time.perf_counter()
            with self._lock:
                frame_sequence = self._front_frame_sequence
                frame = (
                    None
                    if self._front_frame is None or frame_sequence == last_frame_sequence
                    else self._front_frame.copy()
                )
            if frame is not None:
                try:
                    class_ids, centers, _ = self._detector.detect(frame)
                    with self._lock:
                        last_frame_sequence = frame_sequence
                        self._class_ids = class_ids
                        self._centers = centers
                        self._recognized_objects = [
                            self._detector.classes[index] for index in class_ids
                        ]
                        self._detection_sequence += 1
                except Exception as exc:
                    print(f"[go2_mujoco] object detection failed: {exc}")
            elapsed = time.perf_counter() - started
            self._stop_event.wait(max(GO2_MUJOCO_DETECTION_DT - elapsed, 0.01))

    def _extract_named_bodies(self) -> List[str]:
        if mujoco is None or self._model is None:
            return ["go2_mujoco_simulation"]

        named_bodies = []
        for index in range(self._model.nbody):
            name = mujoco.mj_id2name(self._model, mujoco.mjtObj.mjOBJ_BODY, index)
            if name and name != "world":
                named_bodies.append(name.replace("_", " "))
        return named_bodies[:10] or ["go2_mujoco_simulation"]

    def _quat_from_rpy(self, roll: float, pitch: float, yaw: float):
        cr = np.cos(roll * 0.5)
        sr = np.sin(roll * 0.5)
        cp = np.cos(pitch * 0.5)
        sp = np.sin(pitch * 0.5)
        cy = np.cos(yaw * 0.5)
        sy = np.sin(yaw * 0.5)
        return np.array([
            cr * cp * cy + sr * sp * sy,
            sr * cp * cy - cr * sp * sy,
            cr * sp * cy + sr * cp * sy,
            cr * cp * sy - sr * sp * cy,
        ])

    def _read_pose_from_data(self):
        if self._data is None or self._model is None or self._model.nq < 7:
            return dict(self._pose)

        qpos = np.asarray(self._data.qpos[:7]).copy()
        quat = qpos[3:7]
        # MuJoCo stores freejoint quaternion as w, x, y, z.
        w, x, y, z = quat
        roll = np.arctan2(2 * (w * x + y * z), 1 - 2 * (x * x + y * y))
        pitch = np.arcsin(np.clip(2 * (w * y - z * x), -1.0, 1.0))
        yaw = np.arctan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z))
        return {
            "x": float(qpos[0]),
            "y": float(qpos[1]),
            "z": float(qpos[2]),
            "roll": float(roll),
            "pitch": float(pitch),
            "yaw": float(yaw),
        }

    def _apply_pose_to_model(self):
        if self._data is None or self._model is None or self._model.nq < 7:
            return

        quat = self._quat_from_rpy(self._pose["roll"], self._pose["pitch"], self._pose["yaw"])
        self._data.qpos[0] = self._pose["x"]
        self._data.qpos[1] = self._pose["y"]
        self._data.qpos[2] = self._pose["z"]
        self._data.qpos[3:7] = quat
        if self._data.qvel.shape[0] >= 6:
            self._data.qvel[:6] = 0.0
        self._apply_joint_targets(self._joint_targets)
        mujoco.mj_forward(self._model, self._data)

    def _apply_joint_targets(self, joint_targets: np.ndarray) -> None:
        if self._data is None or self._model is None or self._model.nq < 19:
            return

        self._joint_targets = np.asarray(joint_targets, dtype=float).copy()
        self._data.qpos[7:19] = self._joint_targets
        if self._data.qvel.shape[0] >= 18:
            self._data.qvel[6:18] = 0.0

    def _calibrate_standing_height(self) -> float:
        """Lower the fixed base pose until the standing feet touch z=0."""
        return self._calibrate_posture_height(self._STAND_UP_JOINT_POS)

    def _calibrate_posture_height(self, joint_targets: np.ndarray) -> float:
        """Return the base height that puts a posture's feet on the floor."""
        if mujoco is None or self._model is None or self._data is None:
            return self._START_POSE["z"]

        saved_qpos = self._data.qpos.copy()
        self._data.qpos[:7] = [
            self._START_POSE["x"], self._START_POSE["y"], self._START_POSE["z"],
            1.0, 0.0, 0.0, 0.0,
        ]
        self._data.qpos[7:19] = joint_targets
        mujoco.mj_forward(self._model, self._data)
        foot_bottoms = []
        for geom_name in ("FL", "FR", "RL", "RR"):
            geom_id = mujoco.mj_name2id(
                self._model, mujoco.mjtObj.mjOBJ_GEOM, geom_name
            )
            if geom_id >= 0:
                foot_bottoms.append(
                    float(self._data.geom_xpos[geom_id][2] - self._model.geom_size[geom_id][0])
                )
        if not foot_bottoms:
            self._data.qpos[:] = saved_qpos
            mujoco.mj_forward(self._model, self._data)
            return self._START_POSE["z"]

        calibrated = self._START_POSE["z"] - min(foot_bottoms)
        self._data.qpos[:] = saved_qpos
        mujoco.mj_forward(self._model, self._data)
        return float(np.clip(calibrated, 0.12, self._START_POSE["z"]))

    def _update_pose(self, **changes):
        self._target_pose.update(changes)
        self._target_pose["z"] = float(np.clip(self._target_pose["z"], 0.12, 0.75))

    def _advance_pose(self, dt: float) -> None:
        """Interpolate discrete Spark actions into renderable motion."""
        moving = any(
            abs(self._target_pose[key] - self._pose[key]) > 1e-5
            for key in ("x", "y", "yaw")
        )
        linear_step = max(GO2_MUJOCO_LINEAR_SPEED * dt, 0.0)
        angular_step = max(GO2_MUJOCO_ANGULAR_SPEED * dt, 0.0)
        for key in ("x", "y", "z"):
            delta = self._target_pose[key] - self._pose[key]
            self._pose[key] += float(np.clip(delta, -linear_step, linear_step))
        for key in ("roll", "pitch", "yaw"):
            delta = self._target_pose[key] - self._pose[key]
            self._pose[key] += float(np.clip(delta, -angular_step, angular_step))
        self._update_gait(dt, moving)

    def _update_gait(self, dt: float, moving: bool) -> None:
        """Animate a diagonal trot while the kinematic base is moving.

        FL/RR and FR/RL form the two diagonal pairs. During each pair's swing
        half-cycle the thigh advances and the calf flexes to visibly lift the
        foot; the other pair remains in stance. This is a visualization-level
        gait adapter, not a torque or contact controller.
        """
        if moving and np.allclose(self._base_joint_targets, self._STAND_UP_JOINT_POS):
            self._gait_phase = (
                self._gait_phase + 2.0 * np.pi * self._GAIT_CADENCE_HZ * dt
            ) % (2.0 * np.pi)
            gait_targets = self._base_joint_targets.copy()
            # Joint order is FL, FR, RL, RR. Diagonal pairs move together.
            phase_offsets = (0.0, np.pi, np.pi, 0.0)
            for leg_index, phase_offset in enumerate(phase_offsets):
                swing = np.sin(self._gait_phase + phase_offset)
                foot_lift = max(float(swing), 0.0)
                joint_index = leg_index * 3
                gait_targets[joint_index + 1] += self._GAIT_THIGH_SWING * swing
                gait_targets[joint_index + 2] -= self._GAIT_CALF_LIFT * foot_lift
            self._joint_targets = gait_targets
            return

        # Settle smoothly instead of snapping every leg back to its base pose.
        blend = min(self._GAIT_RETURN_RATE * dt, 1.0)
        self._joint_targets += (
            self._base_joint_targets - self._joint_targets
        ) * blend

    def _set_status(self, status: str):
        self._command_status = status

    def _create_placeholder_frame(self, message: str) -> np.ndarray:
        image = Image.new("RGB", (GO2_MUJOCO_RENDER_WIDTH, GO2_MUJOCO_RENDER_HEIGHT), (15, 18, 28))
        draw = ImageDraw.Draw(image)
        font = ImageFont.load_default()
        draw.text((24, 24), "Go2 MuJoCo", fill=(235, 245, 255), font=font)
        draw.text((24, 48), message, fill=(180, 200, 220), font=font)
        draw.rectangle((24, 92, GO2_MUJOCO_RENDER_WIDTH - 24, GO2_MUJOCO_RENDER_HEIGHT - 24), outline=(70, 120, 180), width=2)
        return np.asarray(image)[:, :, ::-1].copy()

    def _render_robot_silhouette(self, draw, center_x: int, ground_y: int, scale: float) -> None:
        torso_w = int(scale * 0.9)
        torso_h = int(scale * 0.42)
        torso_x = int(center_x + self._pose["x"] * scale - torso_w // 2)
        torso_y = int(ground_y - self._pose["z"] * scale - torso_h // 2)

        shadow_w = int(scale * 1.1)
        shadow_h = int(scale * 0.12)
        draw.ellipse(
            (torso_x + torso_w // 2 - shadow_w // 2, ground_y + 4, torso_x + torso_w // 2 + shadow_w // 2, ground_y + 4 + shadow_h),
            fill=(10, 12, 18),
        )

        # torso body
        draw.rounded_rectangle(
            (torso_x, torso_y, torso_x + torso_w, torso_y + torso_h),
            radius=max(6, torso_h // 4),
            fill=(36, 102, 176),
            outline=(210, 232, 255),
            width=2,
        )
        # body highlight and camera bar
        draw.rounded_rectangle(
            (torso_x + 6, torso_y + 6, torso_x + torso_w - 6, torso_y + torso_h - 8),
            radius=max(4, torso_h // 5),
            outline=(80, 170, 240),
            width=1,
        )
        draw.rectangle(
            (torso_x + torso_w - 18, torso_y + torso_h // 4, torso_x + torso_w + 8, torso_y + torso_h // 4 + 8),
            fill=(235, 240, 246),
            outline=(35, 40, 48),
        )
        draw.ellipse(
            (torso_x + torso_w - 10, torso_y + torso_h // 4 - 5, torso_x + torso_w + 10, torso_y + torso_h // 4 + 15),
            fill=(74, 160, 220),
            outline=(240, 248, 255),
        )

        body_origin_x = torso_x + torso_w // 2
        body_origin_y = torso_y + torso_h

        front_leg_x = [-0.28, -0.14]
        rear_leg_x = [0.14, 0.28]
        front_colors = [(70, 180, 230), (120, 210, 185)]
        rear_colors = [(64, 150, 206), (92, 200, 170)]

        def draw_leg(offset_x: float, color, knee_dir: int):
            hip_x = int(body_origin_x + offset_x * scale * 0.95 + self._pose["y"] * scale * 0.2)
            hip_y = body_origin_y - 2
            knee_y = int(ground_y - scale * 0.12)
            foot_y = ground_y - 1
            knee_x = hip_x + knee_dir * int(scale * 0.08)
            foot_x = hip_x + knee_dir * int(scale * 0.02)
            draw.line((hip_x, hip_y, knee_x, knee_y), fill=color, width=7)
            draw.line((knee_x, knee_y, foot_x, foot_y), fill=color, width=7)
            draw.ellipse((foot_x - 5, foot_y - 5, foot_x + 5, foot_y + 5), fill=(238, 243, 248), outline=(35, 45, 55))
            draw.ellipse((hip_x - 4, hip_y - 4, hip_x + 4, hip_y + 4), fill=(238, 243, 248), outline=(35, 45, 55))

        draw_leg(front_leg_x[0], front_colors[0], -1)
        draw_leg(front_leg_x[1], front_colors[1], 1)
        draw_leg(rear_leg_x[0], rear_colors[0], -1)
        draw_leg(rear_leg_x[1], rear_colors[1], 1)

        # head/sensor mast
        head_x = torso_x + torso_w - 10
        head_y = torso_y - int(scale * 0.12)
        draw.ellipse((head_x - 16, head_y - 16, head_x + 16, head_y + 16), fill=(236, 241, 248), outline=(35, 45, 60), width=2)
        draw.line((head_x, head_y + 14, head_x + 24, head_y + 6), fill=(240, 248, 255), width=4)

        # motion state overlay
        draw.text((torso_x + 10, torso_y - 18), self._command_status.upper(), fill=(220, 235, 245), font=ImageFont.load_default())

    def _render_schematic_frame(self) -> np.ndarray:
        canvas = Image.new("RGB", (GO2_MUJOCO_RENDER_WIDTH, GO2_MUJOCO_RENDER_HEIGHT), (10, 14, 24))
        draw = ImageDraw.Draw(canvas)
        font = ImageFont.load_default()

        draw.text((20, 18), "Go2 MuJoCo simulation", fill=(240, 248, 255), font=font)
        draw.text((20, 38), f"Mode: {self._render_mode} | Command: {self._last_command}", fill=(200, 210, 220), font=font)

        width = GO2_MUJOCO_RENDER_WIDTH
        height = GO2_MUJOCO_RENDER_HEIGHT
        ground_y = height - 54
        center_x = width // 2
        scale = min(width, height) * 0.36

        # background and floor
        draw.rectangle((0, ground_y, width, height), fill=(8, 10, 16))
        for offset in range(0, 6):
            shade = 18 + offset * 10
            draw.line((0, ground_y - offset * 6, width, ground_y - offset * 6), fill=(shade, shade + 6, shade + 12), width=1)
        for offset in range(-4, 5):
            x = int(center_x + offset * scale * 0.25 + self._pose["y"] * scale * 0.2)
            draw.line((x, 60, x, ground_y), fill=(28, 36, 52), width=1)
        draw.line((20, ground_y, width - 20, ground_y), fill=(75, 120, 170), width=2)

        self._render_robot_silhouette(draw, center_x, ground_y, scale)
        draw.text((20, height - 26), f"Mode: {self._render_mode} | Command: {self._command_status}", fill=(200, 210, 220), font=font)

        return np.asarray(canvas)[:, :, ::-1].copy()

    def _render_frame(self) -> np.ndarray:
        if mujoco is None or self._model is None or self._data is None:
            return self._create_placeholder_frame("MuJoCo model unavailable")

        # Keep the viewer informative even when GL rendering is unavailable.
        if self._renderer is not None:
            try:
                if self._camera is not None:
                    self._camera.lookat = np.array([
                        self._pose["x"],
                        self._pose["y"],
                        max(self._pose["z"], 0.25),
                    ])
                self._renderer.update_scene(self._data, camera=self._camera or -1)
                image = self._renderer.render()
                pil_image = Image.fromarray(image).convert("RGBA")
                draw = ImageDraw.Draw(pil_image)
                font = ImageFont.load_default()
                draw.rectangle((16, 16, 400, 72), fill=(0, 0, 0, 96))
                draw.text((24, 24), "Go2 MuJoCo simulation", fill=(240, 248, 255), font=font)
                draw.text((24, 44), f"Command: {self._command_status}", fill=(210, 220, 235), font=font)
                return np.asarray(pil_image.convert("RGB"))[:, :, ::-1].copy()
            except Exception:
                self._renderer = None

        return self._render_schematic_frame()

    def _simulation_loop(self) -> None:
        if mujoco is None or self._model is None or self._data is None:
            return

        last_render = 0.0
        last_sensor_render = float("-inf")
        last_renderer_attempt = float("-inf")
        last_front_renderer_attempt = float("-inf")
        last_motion_update = time.perf_counter()
        while not self._stop_event.is_set():
            step_started = time.perf_counter()
            # Rendering cost varies substantially across EGL, desktop GL, and
            # software fallback. Advance high-level motion in wall-clock time
            # so 0.4 m/s remains 0.4 m/s instead of slowing with render FPS.
            motion_dt = float(np.clip(
                step_started - last_motion_update,
                self._model.opt.timestep,
                0.05,
            ))
            last_motion_update = step_started
            try:
                with self._lock:
                    # The upstream simulator does not implement Go2's sport-mode
                    # service.  Re-apply the high-level adapter target on every
                    # frame so gravity cannot immediately erase a Spark command.
                    self._advance_pose(motion_dt)
                    self._apply_pose_to_model()
                    self._data.time += motion_dt
                    current_time = time.perf_counter()
                    if current_time - last_render >= GO2_MUJOCO_RENDER_DT:
                        # The web panel gets a smooth external tracking view.
                        # Sensor rendering and YOLO run at a lower independent
                        # rate, since perception does not need display FPS.
                        if (
                            self._renderer is None
                            and current_time - last_renderer_attempt >= 2.0
                        ):
                            last_renderer_attempt = current_time
                            self._ensure_renderer()
                        self._frame = self._render_frame()
                        last_render = current_time
                    if current_time - last_sensor_render >= GO2_MUJOCO_DETECTION_DT:
                        if (
                            self._front_renderer is not None
                            or current_time - last_front_renderer_attempt >= 2.0
                        ):
                            last_front_renderer_attempt = current_time
                            self._render_front_camera()
                        last_sensor_render = current_time
            except Exception as exc:
                print(f"[go2_mujoco] Simulation loop error, switching to placeholder frame: {exc}")
                with self._lock:
                    self._frame = self._create_placeholder_frame("Go2 MuJoCo simulation fallback")
                self._renderer = None
                time.sleep(1.0)
                continue

            elapsed = time.perf_counter() - step_started
            sleep_time = max(self._model.opt.timestep - elapsed, 0.0)
            if sleep_time > 0:
                time.sleep(sleep_time)

    def check_simplified_syntax_validity(self, simplified_code: str) -> bool:
        try:
            standard_code = HumanFriendlyPythonSyntaxConverter.to_standard_syntax(
                simplified_code, class_method=True
            )
            parsed_code = ast.parse(standard_code)
            allowed_commands = self._allowed_command_names()
            allowed_call_names = {"range", "abs", "min", "max", "int", "float", "bool", "len"}

            for node in ast.walk(parsed_code):
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Attribute):
                        if isinstance(node.func.value, ast.Name) and node.func.value.id == "self":
                            if node.func.attr not in allowed_commands:
                                return False
                        else:
                            return False
                    elif isinstance(node.func, ast.Name):
                        if node.func.id not in allowed_call_names:
                            return False
            return True
        except Exception:
            return False

    def _allowed_command_names(self):
        return {
            "stand_down",
            "stand_up",
            "recovery_stand",
            "stop",
            "move_forward",
            "move_backward",
            "move_left",
            "move_right",
            "turn_left",
            "turn_right",
            "find",
            "found",
            "near",
            "far",
            "light",
            "dark",
        }

    def _apply_action_pose(self, action_name: str, target: Optional[str] = None):
        if action_name == "stand_down":
            self._update_pose(z=self._stand_down_height, roll=0.0, pitch=0.0)
            self._base_joint_targets = self._STAND_DOWN_JOINT_POS.copy()
            self._apply_joint_targets(self._STAND_DOWN_JOINT_POS)
            self._set_status("standing down")
        elif action_name == "stand_up":
            self._update_pose(z=self._standing_height, roll=0.0, pitch=0.0)
            self._base_joint_targets = self._STAND_UP_JOINT_POS.copy()
            self._apply_joint_targets(self._STAND_UP_JOINT_POS)
            self._set_status("standing up")
        elif action_name == "recovery_stand":
            self._base_joint_targets = self._STAND_UP_JOINT_POS.copy()
            self._joint_targets = self._STAND_UP_JOINT_POS.copy()
            self._update_pose(z=self._standing_height, roll=0.0, pitch=0.0)
            self._set_status("recovery stand")
        elif action_name == "stop":
            self._target_pose.update(self._pose)
            self._set_status("stopped")
        elif action_name == "move_forward":
            self._prepare_to_walk()
            distance = 0.16
            yaw = self._target_pose["yaw"]
            self._update_pose(
                x=self._target_pose["x"] + distance * np.cos(yaw),
                y=self._target_pose["y"] + distance * np.sin(yaw),
            )
            self._set_status("moving forward")
        elif action_name == "move_backward":
            self._prepare_to_walk()
            distance = 0.16
            yaw = self._target_pose["yaw"]
            self._update_pose(
                x=self._target_pose["x"] - distance * np.cos(yaw),
                y=self._target_pose["y"] - distance * np.sin(yaw),
            )
            self._set_status("moving backward")
        elif action_name == "move_left":
            self._prepare_to_walk()
            distance = 0.10
            yaw = self._target_pose["yaw"]
            self._update_pose(
                x=self._target_pose["x"] - distance * np.sin(yaw),
                y=self._target_pose["y"] + distance * np.cos(yaw),
            )
            self._set_status("moving left")
        elif action_name == "move_right":
            self._prepare_to_walk()
            distance = 0.10
            yaw = self._target_pose["yaw"]
            self._update_pose(
                x=self._target_pose["x"] + distance * np.sin(yaw),
                y=self._target_pose["y"] - distance * np.cos(yaw),
            )
            self._set_status("moving right")
        elif action_name == "turn_left":
            self._prepare_to_walk()
            self._update_pose(yaw=self._target_pose["yaw"] + 0.25)
            self._set_status("turning left")
        elif action_name == "turn_right":
            self._prepare_to_walk()
            self._update_pose(yaw=self._target_pose["yaw"] - 0.25)
            self._set_status("turning right")
        elif action_name == "find":
            self._prepare_to_walk()
            self._search_target = str(target or "").strip().lower() or None
            self._set_status(f"finding {self._search_target or 'object'}")

    def _prepare_to_walk(self) -> None:
        """Put the legs and body in the standing locomotion posture."""
        self._base_joint_targets = self._STAND_UP_JOINT_POS.copy()
        self._target_pose["z"] = self._standing_height
        self._target_pose["roll"] = 0.0
        self._target_pose["pitch"] = 0.0

    def _call_command(self, command_name: str, *args):
        with self._lock:
            self._last_command = command_name.upper()
            self._apply_action_pose(command_name, args[0] if args else None)

    def stand_down(self):
        self._call_command("stand_down")

    def stand_up(self):
        self._call_command("stand_up")

    def recovery_stand(self):
        self._call_command("recovery_stand")

    def stop(self):
        self._call_command("stop")

    def move_forward(self):
        self._call_command("move_forward")

    def move_backward(self):
        self._call_command("move_backward")

    def move_left(self):
        self._call_command("move_left")

    def move_right(self):
        self._call_command("move_right")

    def turn_left(self):
        self._call_command("turn_left")

    def turn_right(self):
        self._call_command("turn_right")

    def found(self, object_to_find):
        normalized = str(object_to_find).strip().lower()
        with self._lock:
            return normalized in self._recognized_objects or normalized in self._found_objects

    def _target_centered(self, target: str) -> bool:
        target_index = self._detector.classes.index(target)
        return any(
            class_id == target_index and 0.35 <= center[0] <= 0.65
            for class_id, center in zip(self._class_ids, self._centers)
        )

    def find(self, object_to_find):
        target = str(object_to_find).strip().lower()
        if not target:
            return False
        if self._detector is None:
            self._set_status("object detector unavailable")
            return False
        if target not in self._detector.classes:
            self._set_status(f"unknown object: {target}")
            return False

        self._call_command("find", target)
        deadline = time.monotonic() + GO2_MUJOCO_FIND_TIMEOUT
        with self._lock:
            self._found_objects.discard(target)

        # A missing GL camera used to look exactly like a normal unsuccessful
        # search. Distinguish that failure before rotating the robot.
        camera_deadline = min(deadline, time.monotonic() + 4.0)
        while time.monotonic() < camera_deadline and not self._stop_event.is_set():
            with self._lock:
                if self._front_frame_sequence > 0 and self._detection_sequence > 0:
                    break
            time.sleep(0.02)
        else:
            self._set_status("front camera or detector unavailable")
            return False

        while time.monotonic() < deadline and not self._stop_event.is_set():
            with self._lock:
                if self._target_centered(target):
                    self._found_objects.add(target)
                    self._set_status(f"found {target}")
                    return True
                scan_yaw = self._target_pose["yaw"] + GO2_MUJOCO_FIND_YAW_STEP
                self._target_pose["yaw"] = scan_yaw
                self._set_status(f"finding {target}")

            # Reach the requested view before accepting a perception result.
            while time.monotonic() < deadline and not self._stop_event.is_set():
                with self._lock:
                    reached_view = abs(self._pose["yaw"] - scan_yaw) <= 0.01
                if reached_view:
                    break
                time.sleep(0.01)
            with self._lock:
                detection_after_reaching = self._detection_sequence
            # Require inference from a newly rendered frame at this view. This
            # prevents FIND from repeatedly evaluating the same stale image.
            while time.monotonic() < deadline and not self._stop_event.is_set():
                with self._lock:
                    if self._detection_sequence > detection_after_reaching:
                        break
                time.sleep(0.01)
        self._set_status(f"could not find {target}")
        return False

    def near(self):
        return abs(self._pose["x"]) < 0.15 and abs(self._pose["y"]) < 0.15

    def far(self):
        return not self.near()

    def light(self):
        return True

    def dark(self):
        return not self.light()

    def execute_simplified_syntax(self, simplified_code: str) -> None:
        standard_code = HumanFriendlyPythonSyntaxConverter.to_standard_syntax(
            simplified_code, class_method=True
        )

        try:
            sandbox_globals = {"__builtins__": {"range": range, "abs": abs, "min": min, "max": max, "int": int, "float": float, "bool": bool, "len": len}}
            sandbox_locals = {"self": self}
            exec(standard_code, sandbox_globals, sandbox_locals)
        except Exception as e:
            print(e)
            print(f"Invalid syntax: {simplified_code}")

    def get_frame(self) -> Optional[object]:
        with self._lock:
            frame = self._frame
            if frame is None:
                return None
            return frame.copy()

    def close(self) -> None:
        if self._stop_event.is_set():
            return

        self._stop_event.set()
        if self._simulation_thread is not None and self._simulation_thread.is_alive():
            if threading.current_thread() is not self._simulation_thread:
                self._simulation_thread.join(timeout=2.0)
        if self._detection_thread is not None and self._detection_thread.is_alive():
            if threading.current_thread() is not self._detection_thread:
                self._detection_thread.join(timeout=2.0)

        with self._lock:
            if self._renderer is not None:
                try:
                    self._renderer.close()
                except Exception:
                    pass
                self._renderer = None
            if self._front_renderer is not None:
                try:
                    self._front_renderer.close()
                except Exception:
                    pass
                self._front_renderer = None

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass

    def get_recognized_objects(self) -> List[str]:
        return list(self._recognized_objects)

    def get_available_actions(self) -> List[str]:
        return list(GO2_MUJOCO_ACTIONS)

    def tts(self, text: str) -> None:
        return


def create_go2_mujoco_backend(connection_settings=None, audio=False):
    return Go2MujocoBackend(connection_settings=connection_settings, audio=audio)
