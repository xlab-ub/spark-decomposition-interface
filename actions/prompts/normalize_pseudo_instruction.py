PROMPT_TO_MAKE_PSEUDO = """Change the given input into a pseudo code instruction.
Capitalize the pseudo code instruction and if there are multiple words, separate them with a underscore.

Input: go
Pseudo: GO

Input: let's move left
Pseudo: MOVE_LEFT

Input: i wanna spin jump
Pseudo: SPIN_JUMP

Input: find cup please
Pseudo: FIND_CUP

Input: find laptop
Pseudo: FIND_LAPTOP

Input: do push up
Pseudo: PUSH_UP

Input: if far, then move twice
Pseudo: IF_FAR_MOVE_TWICE

Input: if near move backward
Pseudo: IF_NEAR_MOVE_BACKWARD

Input: move forward while far
Pseudo: MOVE_FORWARD_WHILE_FAR

Input: move left until near
Pseudo: MOVE_LEFT_UNTIL_NEAR

Input: move right until near
Pseudo: MOVE_RIGHT_UNTIL_NEAR

Input: move forward until near
Pseudo: MOVE_FORWARD_UNTIL_NEAR

Input: move backward until near
Pseudo: MOVE_BACKWARD_UNTIL_NEAR

Input: move left until far
Pseudo: MOVE_LEFT_UNTIL_FAR

Input: I want you to move
Pseudo: MOVE

Input: move please
Pseudo: MOVE

Input: Please move
Pseudo: MOVE

Input: stand up please
Pseudo: STAND_UP

Input: {instruction}
Pseudo: """