# Go2 commands and MuJoCo integration

## What the Go2 supports

Go2 uses Unitree SDK2 rather than the Go1 `HighCmd` UDP packet used by the
vendored free-dog SDK. On a physical Go2, `SportClient` sends request/response
commands such as `StandUp`, `StandDown`, `RecoveryStand`, `BalanceStand`,
`StopMove`, `Euler(roll, pitch, yaw)`, and `Move(vx, vy, vyaw)`. Depending on
robot edition and firmware it also declares sitting, greeting, stretching,
dances, jumps/flips, gait-selection, and avoidance-mode APIs.

Those sport APIs are **not** an input supported by `unitree_mujoco`. The
official simulator currently accepts motor-level `LowCmd` messages and
publishes `LowState` plus `SportModeState`. Therefore sending a Go2
`SportClient.Move()` call to the simulator does not provide locomotion. A
high-level Spark action must either:

1. drive a low-level locomotion policy/controller through `LowCmd`, or
2. be implemented by a simulator-only adapter.

This repository currently uses option 2: `Go2MujocoBackend` maps discrete Spark
commands to stable MJCF poses. It is intentionally not presented as a
sim-to-real low-level controller.

## Primitive action mapping

| Spark primitive | Go2 SportClient equivalent | MuJoCo adapter |
|---|---|---|
| `STAND_UP` | `StandUp()` | supported |
| `STAND_DOWN` | `StandDown()` | supported |
| `RECOVERY_STAND` | `RecoveryStand()` | supported |
| `STOP` | `StopMove()` | supported |
| `MOVE_FORWARD` / `MOVE_BACKWARD` | timed `Move(vx, 0, 0)`, then `StopMove()` | supported |
| `MOVE_LEFT` / `MOVE_RIGHT` | timed `Move(0, vy, 0)`, then `StopMove()` | supported |
| `TURN_LEFT` / `TURN_RIGHT` | timed `Move(0, 0, vyaw)`, then `StopMove()` | supported |
| `FIND <object>` | application-defined camera search | supported with simulated front camera and YOLOv7-tiny |

Go1's `TILT_*`, `SPIN_JUMP`, and `LIFT` semantics do not map cleanly to the
current Go2 MuJoCo adapter. They are hidden when this backend is active. Go2
sport trick commands should only be exposed after a real-Go2 backend is added
and its edition/firmware capabilities are detected.

`FIND` renders the `front_camera` attached to the simulated Go2 base and runs
the same bundled YOLOv7-tiny/COCO assets used by the Go1 camera path. The robot
rotates by `SPARK_GO2_MUJOCO_FIND_YAW_STEP` between observations until the
requested object is horizontally centered or `SPARK_GO2_MUJOCO_FIND_TIMEOUT`
expires. Detection consumes the robot-mounted front camera while the web panel
continues showing the smooth external tracking view.
Each scan step now waits for the requested yaw and then requires a newly
rendered/inferred camera frame, preventing stale observations from being reused.
Camera or detector startup failure is reported separately from “object not
found.”

The default Unitree scene contains terrain but no COCO object assets. Detection
therefore requires adding a sufficiently realistic, textured object to the
scene; body or geom names alone are deliberately not treated as detections.
The bundled model is in Darknet `.cfg`/`.weights` format, so it requires
`opencv-python>=4.8,<4.12`; OpenCV 5 removed the Darknet importer.

## Rendering and streaming rates

Simulation stepping, display rendering, perception, and browser delivery are
separate workloads:

- MuJoCo state updates at `SPARK_GO2_MUJOCO_SIM_DT` (default 200 Hz).
- The external tracking view renders at `SPARK_GO2_MUJOCO_RENDER_DT` (default
  25 FPS).
- The front sensor and YOLO run at `SPARK_GO2_MUJOCO_DETECTION_DT` (default
  5 FPS) on a separate inference thread.
- The shared Go1/Go2 MJPEG endpoint is paced by `SPARK_VIDEO_STREAM_FPS`
  (default 20 FPS) and `SPARK_VIDEO_JPEG_QUALITY` (default 80).

Go1 capture is likewise independent from YOLO, so a slow inference pass no
longer stalls the physical camera feed. Go2 discrete position and yaw commands
are interpolated at configurable linear/angular rates to make movement visible
instead of teleporting between poses. While translation or rotation is active,
the MuJoCo adapter animates a diagonal trot (FL/RR opposite FR/RL), flexes each
swing-leg calf for visible foot clearance, and blends smoothly back to the
standing joint pose after motion. This remains a visualization-level kinematic
gait; a contact-aware locomotion policy is still required for dynamic sim-to-real
control.

Locomotion integration uses measured monotonic wall time rather than assuming
that every simulation loop finishes within `SPARK_GO2_MUJOCO_SIM_DT`. This keeps
the configured linear/angular speeds stable when GL rendering is slower than the
nominal 200 Hz state loop. With the defaults, one `MOVE_FORWARD` travels 0.16 m
at 0.4 m/s and should finish in approximately 0.4 seconds.

## Organized TODOs

### Correctness completed here

- Select primitive actions from the configured backend for both LLM prompts and
  the web action panel.
- Remove unsupported Go1 actions from the Go2 MuJoCo vocabulary.
- Add missing backward motion, recovery stand, and stop primitives.
- Apply translation in the robot's yaw-relative frame.
- Keep the commanded MJCF pose stable between render frames and serialize
  commands with the simulation thread.
- Initialize at `(x=0, y=0)` in `STAND_UP` and calibrate base height from the
  four foot collision geometries so the feet start on the ground.
- Calibrate `STAND_DOWN` independently from its folded joint geometry instead
  of using a hard-coded base height.
- Add a forward simulated camera, YOLO inference, annotated stream, and active
  scan behavior for `FIND`/`FOUND`.

### Next: physics-based locomotion

- Integrate a Go2 locomotion policy or MPC that consumes velocity targets and
  publishes 12-motor `LowCmd` targets/torques.
- Replace the kinematic adapter with that controller and test stand/walk/turn on
  flat and terrain scenes.
- Add command duration/speed parameters to Spark's syntax rather than relying
  only on repeated fixed-size primitives.

### Next: physical Go2 backend

- Add an SDK2 `SportClient` backend with network-interface, timeout, lease, and
  emergency-stop handling.
- Query robot edition/firmware capabilities before showing special motions.
- Connect the physical Go2 camera stream to the shared detector before enabling
  `FIND`/`FOUND` on a future real-Go2 backend; add range sensing before treating
  `NEAR` or `FAR` as physical perception semantics.

## Primary references

- [Unitree SDK2 C++ `go2/sport/sport_client.hpp`](https://github.com/unitreerobotics/unitree_sdk2/blob/main/include/unitree/robot/go2/sport/sport_client.hpp)
- [Unitree SDK2 Python high-level examples](https://github.com/unitreerobotics/unitree_sdk2_python/tree/master/example/high_level)
- [Unitree `unitree_mujoco` README](https://github.com/unitreerobotics/unitree_mujoco#supported-unitree-sdk2-messages), especially the supported-message section
