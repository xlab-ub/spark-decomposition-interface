# Rainbow Robotics RB10-1300E (manipulator) action vocabulary.
# Shared by noop / sim / real backends: SPARK_ROBOT_BACKEND=rb10_1300e_noop | rb10_1300e_sim | rb10_1300e.
# Backend classes must implement a lower-case method for every entry (e.g. move_home).
# Actions may take arguments: PICK CUP -> pick("cup"), PLACE CUP TABLE -> place("cup", "table").
# Without an argument, PICK / PLACE act on the object of the most recent FIND.
function_library = ['MOVE_HOME',
                    'MOVE_UP', 'MOVE_DOWN', 'MOVE_LEFT', 'MOVE_RIGHT', 'MOVE_FORWARD', 'MOVE_BACKWARD',
                    'GRIPPER_OPEN', 'GRIPPER_CLOSE',
                    'PICK', 'PLACE',
                    'STOP',
                    'FIND']

# Conditions usable in IF / WHILE (evaluated by the backend, not listed as actions).
condition_library = ['FOUND', 'NEAR', 'FAR', 'GRIPPER_HOLDING']
