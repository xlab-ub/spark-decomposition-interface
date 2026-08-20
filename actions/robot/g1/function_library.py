# Unitree G1 action vocabulary (SPARK_ROBOT_BACKEND=g1 | g1_sim | g1_noop).
# Backends must implement a lower-case method for every entry (e.g. move_forward).
function_library = ['STAND_UP', 'STAND_DOWN',
                    'MOVE_FORWARD', 'MOVE_BACKWARD', 'MOVE_LEFT', 'MOVE_RIGHT', 'TURN_LEFT', 'TURN_RIGHT',
                    'STOP',
                    'WAVE_HAND', 'SHAKE_HAND',
                    'HIGH_FIVE', 'HUG', 'CLAP', 'HEART', 'HANDS_UP',
                    'FIND']

# Conditions usable in IF / WHILE (evaluated by the backend, not listed as actions).
# The real backend has no camera wired yet: FOUND/NEAR/FAR return False.
condition_library = ['FOUND', 'NEAR', 'FAR']
