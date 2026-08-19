# Unitree Go2 (quadruped) action vocabulary.
# Shared by noop / sim / real backends: SPARK_ROBOT_BACKEND=go2_noop | go2_sim | go2.
# Backend classes must implement a lower-case method for every entry (e.g. move_forward).
function_library = ['STAND_UP', 'STAND_DOWN', 'RECOVERY_STAND',
                    'MOVE_FORWARD', 'MOVE_BACKWARD', 'MOVE_LEFT', 'MOVE_RIGHT', 'TURN_LEFT', 'TURN_RIGHT',
                    'STOP',
                    'FIND']

# Conditions usable in IF / WHILE (evaluated by the backend, not listed as actions).
condition_library = ['FOUND', 'NEAR', 'FAR']
