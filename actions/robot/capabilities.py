"""Backend-specific primitive actions exposed to Spark and the web UI."""

GO1_ACTIONS = (
    "STAND_DOWN", "STAND_UP",
    "TILT_LEFT_SHOULDER", "TILT_RIGHT_SHOULDER",
    "TILT_HEAD_UP", "TILT_HEAD_DOWN", "TILT_HEAD_LEFT", "TILT_HEAD_RIGHT",
    "MOVE_FORWARD", "MOVE_LEFT", "MOVE_RIGHT", "TURN_LEFT", "TURN_RIGHT",
    "SPIN_JUMP", "LIFT", "FIRST_DANCE", "SECOND_DANCE", "FIND",
)

# unitree_mujoco exposes LowCmd/LowState, not the Go2 sport-mode RPC service.
# This list therefore contains only primitives implemented by our local MuJoCo
# controller.  Go2 sport-only tricks must not be promised by the UI or prompts.
GO2_MUJOCO_ACTIONS = (
    "STAND_DOWN", "STAND_UP", "RECOVERY_STAND", "STOP",
    "MOVE_FORWARD", "MOVE_BACKWARD", "MOVE_LEFT", "MOVE_RIGHT",
    "TURN_LEFT", "TURN_RIGHT",
    "FIND",
)


def get_backend_action_names(backend_name: str):
    normalized = (backend_name or "noop").lower()
    if normalized in {"go2", "go2_mujoco", "mujoco"}:
        return list(GO2_MUJOCO_ACTIONS)
    # Keep the historical vocabulary for Go1 and noop development mode.
    return list(GO1_ACTIONS)
