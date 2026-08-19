# Unitree Go1 action vocabulary (moved verbatim from actions/actions.py).
# Used for SPARK_ROBOT_BACKEND=noop and go1.
function_library = ['STAND_DOWN', 'STAND_UP',
                    'TILT_LEFT_SHOULDER', 'TILT_RIGHT_SHOULDER', 'TILT_HEAD_UP', 'TILT_HEAD_DOWN', 'TILT_HEAD_LEFT', 'TILT_HEAD_RIGHT',
                    'MOVE_FORWARD', 'MOVE_LEFT', 'MOVE_RIGHT', 'TURN_LEFT', 'TURN_RIGHT',
                    'SPIN_JUMP', 'LIFT', 'FIRST_DANCE', 'SECOND_DANCE',
                    'FIND']

# Conditions usable in IF / WHILE (evaluated by the backend, not listed as actions).
condition_library = ['FOUND', 'NEAR', 'FAR', 'LIGHT', 'DARK']
