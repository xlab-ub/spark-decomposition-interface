# Rainbow Robotics RB10-1300E action vocabulary (SPARK_ROBOT_BACKEND=rb10_1300e | _sim | _noop).
# Backends must implement a lower-case method for every entry; REACH takes an
# object argument (REACH APPLE -> reach("apple")); "pick up" decomposes at the
# LLM level into GRIPPER_OPEN, REACH <object>, GRIPPER_CLOSE, MOVE_UP.
function_library = ['MOVE_HOME',
                    'MOVE_UP', 'MOVE_DOWN', 'MOVE_LEFT', 'MOVE_RIGHT', 'MOVE_FORWARD', 'MOVE_BACKWARD',
                    'REACH',
                    'GRIPPER_OPEN', 'GRIPPER_CLOSE',
                    'STOP',
                    'FIND']

# Conditions usable in IF / WHILE (evaluated by the backend, not listed as actions).
condition_library = ['FOUND', 'NEAR', 'FAR', 'GRIPPER_HOLDING']
