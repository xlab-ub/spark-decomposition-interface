PROMPT = """Think step by step to carry out the instruction.
Write an executable program for the robot based on given instructions.
Use only available options to write the program.
Try to use the new available options as much as possible.
Ambiguous instructions must be interpreted in the most reasonable way and the program must be written accordingly.

Available Options:
{available_options}

The following descriptions are for new available options.{new_available_option_pairs}

STAND_UP, TILT_LEFT_SHOULDER, TILT_RIGHT_SHOULDER, TILT_HEAD_UP, TILT_HEAD_DOWN, TILT_HEAD_LEFT, TILT_HEAD_RIGHT, MOVE_FORWARD, MOVE_LEFT, MOVE_RIGHT, TURN_LEFT, TURN_RIGHT, SPIN_JUMP, LIFT, FIRST_DANCE, SECOND_DANCE take no arguments.
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
Available conditions for IF only include FAR, NEAR, FOUND.
FOUND is used along with FIND. For example, IF FOUND CUP will execute the following actions if the robot found a cup with FIND CUP.

For conditional repetition, use WHILE CONDITION syntax. For example, WHILE FAR will repeat the following actions while the robot is far from the object.
The conditional actions must be indented by 4 spaces.
After the conditional actions, write END WHILE.
Available conditions for WHILE only include FAR, NEAR.

Instructions can be varied in format, but should all be translated to the same program if they have the same meaning.
Examples:
{{instruction}}
I want to {{instruction}}
I want you to {{instruction}}
Let's {{instruction}}
Please {{instruction}}
{{instruction}} please
{{instruction}} now
{{instruction}} please now

For each form of instruction received, translate it into the robot's programming language.
Instruction: go
Program:
MOVE_FORWARD

Instruction: let's move left
Program:
MOVE_LEFT

Instruction: move
Program:
MOVE_FORWARD

Instruction: move backward
Program:
REPEAT 2 TIMES
    TURN_LEFT
END REPEAT
MOVE_FORWARD

Instruction: stand up
Program:
STAND_UP

Instruction: head up
Program:
TILT_HEAD_UP

Instruction: turn left
Program:
TURN_LEFT

Instruction: i wanna spin jump
Program:
SPIN_JUMP

Instruction: find cup please
Program:
FIND CUP

Instruction: find laptop
Program:
FIND LAPTOP

Instruction: do push up
Program:
REPEAT 3 TIMES
    STAND_UP
    STAND_DOWN
END REPEAT
STAND_UP
    
Instruction: if far, then move twice
Program:
IF FAR
    REPEAT 2 TIMES
        MOVE_FORWARD
    END REPEAT
END IF

Instruction: if near move backward
Program:
IF NEAR
    REPEAT 2 TIMES
        TURN_LEFT
    END REPEAT
    MOVE_FORWARD
END IF

Instruction: move forward while far
Program:
WHILE FAR
    MOVE_FORWARD
END WHILE

Instruction: move left until near
Program:
WHILE FAR
    MOVE_LEFT
END WHILE

Instruction: go to the chair
Program:
FIND CHAIR
IF FOUND CHAIR
    WHILE FAR
        MOVE_FORWARD
    END WHILE
END IF
{new_instruction_program_pairs}
Do not write brackets or parentheses in the program.
Do not write the program in the form of a conversation.
Do not explain the program in the form of a conversation.
Do not omit indentation, spaces, or new lines.
Instruction: {instruction}
Program:
"""