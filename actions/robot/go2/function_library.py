# Unitree Go2 action vocabulary (SPARK_ROBOT_BACKEND=go2 | go2_sim | go2_noop).
# Backends must implement a lower-case method for every entry (e.g. move_forward).
function_library = ['STAND_UP', 'STAND_DOWN', 'RECOVERY_STAND',
                    'MOVE_FORWARD', 'MOVE_BACKWARD', 'MOVE_LEFT', 'MOVE_RIGHT', 'TURN_LEFT', 'TURN_RIGHT',
                    'STOP',
                    'HELLO', 'SIT', 'RISE_SIT', 'STRETCH', 'DANCE',
                    'FIND']

# Conditions usable in IF / WHILE (evaluated by the backend, not listed as actions).
# The real backend has no perception wired yet: FOUND/NEAR/FAR return False.
condition_library = ['FOUND', 'NEAR', 'FAR']
