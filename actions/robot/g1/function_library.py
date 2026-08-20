# Unitree G1 (humanoid) action vocabulary.
# Shared by noop / sim / real backends: SPARK_ROBOT_BACKEND=g1_noop | g1_sim | g1.
# Backend classes must implement a lower-case method for every entry (e.g. move_forward).
# Verified on the real robot via LocoClient + G1ArmActionClient (see ~/taegyu/Robot/G1/g1_run.py).
function_library = ['STAND_UP', 'STAND_DOWN',
                    'MOVE_FORWARD', 'MOVE_BACKWARD', 'MOVE_LEFT', 'MOVE_RIGHT', 'TURN_LEFT', 'TURN_RIGHT',
                    'STOP',
                    'WAVE_HAND', 'SHAKE_HAND',
                    'HIGH_FIVE', 'HUG', 'CLAP', 'HEART', 'HANDS_UP',
                    'FIND']

# Conditions usable in IF / WHILE (evaluated by the backend, not listed as actions).
# The real backend has no camera wired yet: FOUND/NEAR/FAR return False.
condition_library = ['FOUND', 'NEAR', 'FAR']
