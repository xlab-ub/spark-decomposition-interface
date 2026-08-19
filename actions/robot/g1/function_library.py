# Unitree G1 (humanoid) action vocabulary.
# Shared by noop / sim / real backends: SPARK_ROBOT_BACKEND=g1_noop | g1_sim | g1.
# Backend classes must implement a lower-case method for every entry (e.g. move_forward).
function_library = ['STAND_UP', 'STAND_DOWN',
                    'MOVE_FORWARD', 'MOVE_BACKWARD', 'MOVE_LEFT', 'MOVE_RIGHT', 'TURN_LEFT', 'TURN_RIGHT',
                    'WAVE_HAND', 'SQUAT', 'DANCE',
                    'STOP',
                    'FIND']

# Conditions usable in IF / WHILE (evaluated by the backend, not listed as actions).
condition_library = ['FOUND', 'NEAR', 'FAR']
