PROMPT_TO_FIND_SIMILAR = """Find the similar pseudo code instruction for the given input among the available options including new options.
If there is no similar pseudo code instruction, write 'None'.
If there is a similar pseudo code instruction, write the only single similar pseudo code instruction.

Available Options:
{available_options}

The following descriptions are for new available options.{new_available_option_pairs}

Input: GO
Similar: MOVE_FORWARD

Input: GO_LEFT
Similar: MOVE_LEFT

Input: GO_RIGHT
Similar: MOVE_RIGHT

Input: ROTATE_LEFT
Similar: TURN_LEFT

Write None if there is no similar pseudo code instruction.
Write the only single similar pseudo code instruction if there is a similar pseudo code instruction among the available options including new options.
Input: {instruction}
Similar: """