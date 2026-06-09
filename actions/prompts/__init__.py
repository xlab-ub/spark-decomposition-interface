"""Spark decomposition prompt templates.

File naming convention: <verb>_<object>.py
Each module exports one PROMPT_* string used by actions/engine/generator.py.
"""

from prompts.classify_instruction import PROMPT_TO_CLASSIFY
from prompts.decompose_direct import PROMPT
from prompts.decompose_structured import PROMPT_PSEUDO
from prompts.find_similar_instruction import PROMPT_TO_FIND_SIMILAR
from prompts.normalize_pseudo_instruction import PROMPT_TO_MAKE_PSEUDO
from prompts.revise_block import PROMPT_TO_REVISE

PROMPT_MODULES = {
    "decompose_direct": ("decompose_direct.py", PROMPT),
    "decompose_structured": ("decompose_structured.py", PROMPT_PSEUDO),
    "revise_block": ("revise_block.py", PROMPT_TO_REVISE),
    "classify_instruction": ("classify_instruction.py", PROMPT_TO_CLASSIFY),
    "normalize_pseudo_instruction": ("normalize_pseudo_instruction.py", PROMPT_TO_MAKE_PSEUDO),
    "find_similar_instruction": ("find_similar_instruction.py", PROMPT_TO_FIND_SIMILAR),
}

# Legacy reference prompt (not wired into actions.py by default).
# See decompose_structured_exp2.py
