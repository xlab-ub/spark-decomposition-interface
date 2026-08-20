# RB10-1300E variant of revise_block.py (vocabulary and example programs).
PROMPT_TO_REVISE = """Think step by step to carry out the pseudo instruction.
Write an executable program for the robot based on given pseudo instructions.
Use only available options to write the program.
Try to use the new available options as much as possible.
Ambiguous instructions must be interpreted in the most reasonable way and the program must be written accordingly.

Available Options:
{available_options}

The following descriptions are for new available options.{new_available_option_pairs}

MOVE_HOME, MOVE_UP, MOVE_DOWN, MOVE_LEFT, MOVE_RIGHT, MOVE_FORWARD, MOVE_BACKWARD, GRIPPER_OPEN, GRIPPER_CLOSE, STOP take no arguments. REACH takes one object argument (REACH APPLE).
This robot is a fixed manipulator arm. Use ONLY these action names. Do NOT invent other names (STAND_UP, TURN_LEFT, TURN_RIGHT, SPIN_JUMP do not exist).
FIND only takes one argument: a string to be matched with the object name. For example, FIND CUP will find a cup. You must not use FIND with parentheses, for example, FIND(CUP) is not allowed.
Available objects for FIND are only as follows: 
person
bicycle
car
motorbike
aeroplane
bus
train
truck
boat
traffic light
fire hydrant
stop sign
parking meter
bench
bird
cat
dog
horse
sheep
cow
elephant
bear
zebra
giraffe
backpack
umbrella
handbag
tie
suitcase
frisbee
skis
snowboard
sports ball
kite
baseball bat
baseball glove
skateboard
surfboard
tennis racket
bottle
wine glass
cup
fork
knife
spoon
bowl
banana
apple
sandwich
orange
broccoli
carrot
hot dog
pizza
donut
cake
chair
sofa
pottedplant
bed
diningtable
toilet
tvmonitor
laptop
mouse
remote
keyboard
cell phone
microwave
oven
toaster
sink
refrigerator
book
clock
vase
scissors
teddy bear
hair drier
toothbrush

For repeated actions, use REPEAT N TIMES. For example, REPEAT 3 TIMES will repeat the following actions 3 times.
The number of times, N, must be a positive integer.
The repeated actions must be indented by 4 spaces.
After the repeated actions, write END REPEAT.

For conditional execution, use IF CONDITION syntax. For example, IF NEAR will execute the following actions if the robot is near the object.
The conditional actions must be indented by 4 spaces.
After the conditional actions, write END IF.
Available conditions for IF only include FAR, NEAR, FOUND, GRIPPER_HOLDING.
FOUND is used along with FIND. For example, IF FOUND CUP will execute the following actions if the robot found a cup with FIND CUP.

For conditional repetition, use WHILE CONDITION syntax. For example, WHILE FAR will repeat the following actions while the robot is far from the object.
The conditional actions must be indented by 4 spaces.
After the conditional actions, write END WHILE.
Available conditions for WHILE only include FAR, NEAR.

For each form of instruction received, translate it into the robot's programming language.
Instruction: GO
Program:
MOVE_FORWARD

Instruction: MOVE_LEFT
Program:
MOVE_LEFT

Instruction: MOVE
Program:
MOVE_FORWARD

Instruction: MOVE_BACKWARD
Program:
MOVE_BACKWARD

Instruction: MOVE_HOME
Program:
MOVE_HOME

Instruction: GRIPPER_OPEN
Program:
GRIPPER_OPEN

Instruction: GRIPPER_CLOSE
Program:
GRIPPER_CLOSE

Instruction: PICK_APPLE
Program:
GRIPPER_OPEN
REACH APPLE
GRIPPER_CLOSE
MOVE_UP

Instruction: FIND_CUP
Program:
FIND CUP

Instruction: FIND_LAPTOP
Program:
FIND LAPTOP

Instruction: PUSH_UP
Program:
REPEAT 3 TIMES
    MOVE_UP
    MOVE_DOWN
END REPEAT
MOVE_UP
    
Instruction: IF_FAR_MOVE_TWICE
Program:
IF FAR
    REPEAT 2 TIMES
        MOVE_FORWARD
    END REPEAT
END IF

Instruction: IF_NEAR_MOVE_BACKWARD
Program:
IF NEAR
    MOVE_BACKWARD
END IF

Instruction: MOVE_FORWARD_WHILE_FAR
Program:
WHILE FAR
    MOVE_FORWARD
END WHILE

Instruction: MOVE_LEFT_UNTIL_NEAR
Program:
WHILE FAR
    MOVE_LEFT
END WHILE

Instruction: GO_TO_CHAIR
Program:
FIND CHAIR
IF FOUND CHAIR
    WHILE FAR
        MOVE_FORWARD
    END WHILE
END IF

Instruction: REPEAT_2_TIMES
Program:
REPEAT 2 TIMES

Instruction: IF_NEAR
Program:
IF NEAR

Instruction: IF_FOUND_CAR
Program:
IF FOUND CAR

Instruction: WHILE_FAR
Program:
WHILE FAR
{new_instruction_program_pairs}
Do not write the program in the form of a conversation.
Do not explain the program in the form of a conversation.
Do not write brackets or parentheses in the program.
Do not omit indentation, spaces, or new lines.
Each indented block must be indented by 4 spaces.
Instruction: {instruction}
Program:
"""