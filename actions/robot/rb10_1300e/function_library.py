# Rainbow Robotics RB10-1300E action vocabulary (SPARK_ROBOT_BACKEND=rb10_1300e | _sim | _noop).
# Backends must implement a lower-case method for every entry; actions may take
# string arguments (PICK CUP -> pick("cup")); without one, PICK/PLACE use the last FIND target.
function_library = ['MOVE_HOME',
                    'MOVE_UP', 'MOVE_DOWN', 'MOVE_LEFT', 'MOVE_RIGHT', 'MOVE_FORWARD', 'MOVE_BACKWARD',
                    'GRIPPER_OPEN', 'GRIPPER_CLOSE',
                    'PICK', 'PLACE',
                    'STOP',
                    'FIND']

# Conditions usable in IF / WHILE (evaluated by the backend, not listed as actions).
condition_library = ['FOUND', 'NEAR', 'FAR', 'GRIPPER_HOLDING']
