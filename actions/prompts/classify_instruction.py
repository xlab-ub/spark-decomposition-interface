PROMPT_TO_CLASSIFY = """Classify the given input into one of the two categories: Instruction or Conversation. 

Input: go
Category: Instruction

Input: how are you?
Category: Conversation

Input: let's move left
Category: Instruction

Input: move
Category: Instruction

Input: who are you?
Category: Conversation

Input: nice to meet you
Category: Conversation

Input: go three times
Category: Instruction

Input: move backward
Category: Instruction

Input: stand up
Category: Instruction

Input: head up
Category: Instruction

Input: turn left
Category: Instruction

Input: i wanna spin jump
Category: Instruction

Input: find cup please
Category: Instruction

Input: find laptop
Category: Instruction

Input: do push up
Category: Instruction

Input: if light spin jump
Category: Instruction

Input: if far, then move twice
Category: Instruction

Input: if near move backward
Category: Instruction

Input: move forward while far
Category: Instruction

Input: move left until near
Category: Instruction

Input: move right during dark
Category: Instruction

Input: good morning
Category: Conversation

Input: good night
Category: Conversation

Input: how are you doing?
Category: Conversation

Input: go to the chair
Category: Instruction

Input: I want to go
Category: Instruction

Input: I want you to move
Category: Instruction

Input: Let's move
Category: Instruction

Input: Please move
Category: Instruction

Input: {instruction}
Category: """