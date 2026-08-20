# This files contains your custom actions which can be used to run
# custom Python code.
#
# See this guide on how to implement these action:
# https://rasa.com/docs/rasa/custom-actions

# rasa run --enable-api -p 15005 
# rasa run actions -p 15055 

import os 
import sys 
import threading 
import re 
import time
from typing import Any, Text, Dict, List
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.forms import FormValidationAction
from rasa_sdk.events import SlotSet

sys.path.insert(0, os.path.dirname(__file__))

from config import (
    ROBOT_BACKEND,
    RASA_TEST,
    WEB_SERVER,
    TTS_ON,
    DATABASE_ON,
    DATABASE_USER,
    GPT_WITH_LOCAL_LLM,
    FIND_SIMILAR,
    RASA_SERVER_URL,
    WEB_SERVER_PORT,
)
from engine.generator import ProgramGenerator, ProgramGenerator_openai
from prompts.decompose_direct import PROMPT
from prompts.classify_instruction import PROMPT_TO_CLASSIFY
from prompts.normalize_pseudo_instruction import PROMPT_TO_MAKE_PSEUDO
from prompts.find_similar_instruction import PROMPT_TO_FIND_SIMILAR

# Per-robot prompt override: prompts/<name>_<robot>.py is used when it exists
# (e.g. decompose_structured_go2 for SPARK_ROBOT_BACKEND=go2 / go2_sim / go2_noop),
# otherwise the original file (Go1 vocabulary) is used.
import importlib

def _robot_prompt(module_name, attribute):
    robot = ROBOT_BACKEND
    for suffix in ("_sim", "_noop"):
        if robot.endswith(suffix):
            robot = robot[: -len(suffix)]
    try:
        module = importlib.import_module(f"prompts.{module_name}_{robot}")
        print(f"Using robot prompt: prompts/{module_name}_{robot}.py")
    except ImportError:
        module = importlib.import_module(f"prompts.{module_name}")
    return getattr(module, attribute)

PROMPT_PSEUDO = _robot_prompt("decompose_structured", "PROMPT_PSEUDO")
PROMPT_TO_REVISE = _robot_prompt("revise_block", "PROMPT_TO_REVISE")
from robot import create_robot_backend, get_function_library
from robot.syntax import get_first_indent

lock = threading.Lock()

if RASA_TEST:
    import numpy as np
    from PIL import Image
    from io import BytesIO
else:
    import cv2

if WEB_SERVER:
    from flask import Flask, render_template, Response, request, jsonify
    from flask_socketio import SocketIO

    WEB_DIR = os.path.join(os.path.dirname(__file__), "web")
    app = Flask(
        __name__,
        template_folder=os.path.join(WEB_DIR, "templates"),
        static_folder=os.path.join(WEB_DIR, "static"),
    )
    socketio = SocketIO(app)

# function_library = ['stand_down', 'stand_up', 
#                     'tilt_left_shoulder', 'tilt_right_shoulder', 'tilt_head_up', 'tilt_head_down', 'tilt_head_left', 'tilt_head_right',
#                     'move_forward', 'move_left', 'move_right', 'turn_left', 'turn_right',
#                     'spin_jump', 'lift', 'first_dance', 'second_dance', 
#                     'find']
function_library = get_function_library()  # per-robot vocabulary from actions/robot/<robot>/function_library.py
basic_function_library = function_library.copy()
new_function_library = {}

new_instruction = ''
new_instruction_candidate = ''
new_instruction_user_input = ''
new_instruction_user_input_candidate = ''
new_available_option_pair = """
New available option: {instruction}
Program:
{program}
""".strip()
new_available_option_pairs = ''

new_instruction_program_pair = """
Instruction: {instruction}
Program:
{program}
""".strip()
new_instruction_program_pairs = ''

block_number_list = []
new_instruction_to_decompose_list = [] 
new_instruction_user_input_list = []

intent_to_revise_decomposed_actions = ''
intent_to_revise_decomposed_actions_list = []

if DATABASE_ON:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "optional", "database"))
    from database_operations import create_tables, insert_user, insert_new_function_library, load_database_data

    create_tables()
    # Insert user and get user_id
    user_id = insert_user(DATABASE_USER)
    new_function_library, new_instruction_program_pairs = load_database_data(function_library, new_instruction_program_pair, user_id)

def create_prompt(available_options, new_available_option_pairs, new_instruction_program_pairs, instruction):
    return PROMPT.format(available_options=available_options, new_available_option_pairs=new_available_option_pairs, new_instruction_program_pairs=new_instruction_program_pairs, instruction=instruction)

def create_prompt_to_revise(available_options, new_available_option_pairs, new_instruction_program_pairs, instruction):
    return PROMPT_TO_REVISE.format(available_options=available_options, new_available_option_pairs=new_available_option_pairs, new_instruction_program_pairs=new_instruction_program_pairs, instruction=instruction)

def create_prompt_to_classify(instruction):
    return PROMPT_TO_CLASSIFY.format(instruction=instruction)

def create_prompt_to_make_pseudo(instruction):
    return PROMPT_TO_MAKE_PSEUDO.format(instruction=instruction)

def create_prompt_pseudo(available_options, new_available_option_pairs, new_instruction_program_pairs, instruction):
    return PROMPT_PSEUDO.format(available_options=available_options, new_available_option_pairs=new_available_option_pairs, new_instruction_program_pairs=new_instruction_program_pairs, instruction=instruction)

def create_prompt_to_find_similar(available_options, new_available_option_pairs, instruction):
    return PROMPT_TO_FIND_SIMILAR.format(available_options=available_options, new_available_option_pairs=new_available_option_pairs, instruction=instruction)

go1 = create_robot_backend(audio=TTS_ON)

def go1_run():
    # Main loop.
    # Hold the lock only while taking the program off the queue: executing a
    # long program (FIND scan, walking) under the lock blocked every Rasa
    # action handler waiting on it, and the Sanic event loop with them
    # ("Couldn't connect to the server at ...:15055/webhook"). The sleep keeps
    # this polling thread from busy-waiting the GIL away from the camera and
    # detection threads.
    while True: 
        global message 
        
        program = None
        with lock:
            if len(message) > 0:
                program = '\n'.join(message)
                message.clear() 
        if program is not None:
            go1.execute_simplified_syntax(program)
        time.sleep(0.05)

def go1_run_with_tts():
    while True: 
        global message 
        global message_for_tts
        
        program = None
        tts_messages = []
        with lock:
            if len(message_for_tts) > 0:
                tts_messages = list(message_for_tts)
                message_for_tts.clear()
            
                if len(message) > 0:
                    program = '\n'.join(message)
                    message.clear()
        for m in tts_messages:
            go1.tts(m)
        if program is not None:
            go1.execute_simplified_syntax(program)
        time.sleep(0.05)
        
message = [] 
message_for_tts = []

splitted_prog = []
splitted_prog_candidate = [] 
splitted_prog_list = []

high_level_task = ''
natural_language_plans = ''
logical_relations = ''
components_for_pseudo_code = ''
explanation = ''

ASK_INSTRUCTION_FIRST_TIME = True
number_of_explanation_for_addition = 0 

# https://stackoverflow.com/questions/17894168/python-input-and-output-threading 
# https://stackoverflow.com/questions/60148137/what-happens-if-i-dont-join-a-python-thread 
if TTS_ON:
    go1_run_thread = threading.Thread(target=go1_run_with_tts, daemon=True)
else:
    go1_run_thread = threading.Thread(target=go1_run, daemon=True)
go1_run_thread.start()

generator = ProgramGenerator(prompter=create_prompt)
generator.add_prompter(create_prompt_to_revise)
generator.add_prompter(create_prompt_to_classify)
generator.add_prompter(create_prompt_to_make_pseudo)
generator.add_prompter(create_prompt_pseudo)
generator.add_prompter(create_prompt_to_find_similar)

if GPT_WITH_LOCAL_LLM:
    generator_openai = ProgramGenerator_openai(prompter=create_prompt_pseudo, local=False)
    generator_openai_to_revise = ProgramGenerator_openai(prompter=create_prompt_to_revise, local=False)

#
#
# class ActionHelloWorld(Action):
#
#     def name(self) -> Text:
#         return "action_hello_world"
#
#     def run(self, dispatcher: CollectingDispatcher,
#             tracker: Tracker,
#             domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
#
#         dispatcher.utter_message(text="Hello World!")
#
#         return []

def serialize_prog_with_block_number(prog, prefix=''):
    global new_function_library
    serialized_prog = []
    for index, line in enumerate(prog):
        func_name = line.strip().split('(')[0]
        if func_name in new_function_library:
            serialized_func_name = serialize_prog_with_block_number(new_function_library[func_name], prefix=prefix+f'{index+1}-')
            serialized_prog.append(f"{prefix}{index+1}. {line}")
            for serialized_line in serialized_func_name:
                serialized_prog.append(serialized_line)
        else:
            serialized_prog.append(f"{prefix}{index+1}. {line}")
    return serialized_prog

def serialize_prog_with_block_number_for_addition(prog):
    serialized_prog = []
    for index, line in enumerate(prog):
        serialized_prog.append(f"{index+1:02}. {line}")
        # serialized_prog.append(f"{line}")
    # serialized_prog.append(f"{len(prog)+1}.")
    return serialized_prog

def serialize_prog_with_block_number_for_change_or_deletion(prog):
    serialized_prog = []
    for index, line in enumerate(prog):
        if line.strip().split(' ')[0].lower() != "end":
            serialized_prog.append(f"{index+1:02}. {line}")
        else:
            serialized_prog.append(f"    {line}")
    return serialized_prog

def serialize_prog(prog):
    global new_function_library
    serialized_prog = []
    for line in prog:
        indent, _ = get_first_indent(line)
        func_name = line.strip().split('(')[0]
        if func_name in new_function_library:
            for serialized_line in new_function_library[func_name]:
                # serialized_prog.append(serialized_line)
                serialized_prog.append(indent + serialized_line)
        else:
            serialized_prog.append(line)
    return serialized_prog

def get_valid_block_number(prog):
    valid_block_number = []
    for index, line in enumerate(prog):
        if line.strip().split(' ')[0].lower() != "end":
            valid_block_number.append(index+1)
    return valid_block_number

def extract_components(output_text):
    # Use regex patterns to capture each section
    nl_plans_pattern = r"### Natural Language Plans ###\s*(.*?)\s*### Pseudo Code ###"
    pseudo_code_pattern = r"### Pseudo Code ###\s*(.*?)\s*### Explanation ###"
    explanation_pattern = r"### Explanation ###\s*(.*)"

    # Extract the content of each component
    natural_language_plans = re.search(nl_plans_pattern, output_text, re.DOTALL).group(1).strip()
    pseudo_code = re.search(pseudo_code_pattern, output_text, re.DOTALL).group(1).strip()
    explanation = re.search(explanation_pattern, output_text, re.DOTALL).group(1).strip()

    return natural_language_plans, pseudo_code, explanation

def _normalize_decomposition_headers(output_text):
    sections = [
        "High-Level Task",
        "Pseudo Instruction",
        "Natural Language Plans",
        "Logical Relations",
        "Components for Pseudo Code",
        "Pseudo Code",
        "Explanation",
    ]
    normalized = output_text
    for section in sections:
        normalized = re.sub(
            rf"###\s*{re.escape(section)}\s*#*\s*",
            f"### {section} ###\n",
            normalized,
            flags=re.IGNORECASE,
        )
    return normalized

def _extract_section(output_text, section_name, next_section_name=None):
    if next_section_name:
        pattern = (
            rf"###\s*{re.escape(section_name)}\s*###\s*(.*?)\s*"
            rf"###\s*{re.escape(next_section_name)}\s*###"
        )
    else:
        pattern = rf"###\s*{re.escape(section_name)}\s*###\s*(.*)"
    match = re.search(pattern, output_text, re.DOTALL | re.IGNORECASE)
    if not match:
        return None
    return match.group(1).strip()

def extract_components2(output_text):
    if not output_text or not output_text.strip():
        raise ValueError("LLM returned empty decomposition output.")

    normalized_text = _normalize_decomposition_headers(output_text)
    section_pairs = [
        ("high_level_task", "High-Level Task", "Pseudo Instruction"),
        ("pseudo_instruction", "Pseudo Instruction", "Natural Language Plans"),
        ("natural_language_plans", "Natural Language Plans", "Logical Relations"),
        ("logical_relations", "Logical Relations", "Components for Pseudo Code"),
        ("components_for_pseudo_code", "Components for Pseudo Code", "Pseudo Code"),
        ("pseudo_code", "Pseudo Code", "Explanation"),
    ]

    extracted = {}
    for key, section_name, next_section_name in section_pairs:
        value = _extract_section(normalized_text, section_name, next_section_name)
        if value is None:
            raise ValueError(f"Could not parse LLM section: {section_name}")
        extracted[key] = value

    explanation = _extract_section(normalized_text, "Explanation")
    if explanation is None:
        raise ValueError("Could not parse LLM section: Explanation")

    high_level_task = extracted["high_level_task"]
    pseudo_instruction = extracted["pseudo_instruction"]
    natural_language_plans = extracted["natural_language_plans"]
    logical_relations = extracted["logical_relations"]
    components_for_pseudo_code = extracted["components_for_pseudo_code"]
    pseudo_code = extracted["pseudo_code"]

    # print(f"high_level_task: {high_level_task}")
    # print(f"pseudo_instruction: {pseudo_instruction}")
    # print(f"natural_language_plans: {natural_language_plans}")
    # print(f"logical_relations: {logical_relations}")
    # print(f"components_for_pseudo_code: {components_for_pseudo_code}")
    # print(f"pseudo_code: {pseudo_code}")
    # print(f"explanation: {explanation}")

    return high_level_task, pseudo_instruction, natural_language_plans, logical_relations, components_for_pseudo_code, pseudo_code, explanation

class ValidateInstructionForm(FormValidationAction):
    def name(self) -> Text:
        return "validate_instruction_form"
    
    def validate_instruction(self,
                             slot_value: Any,
                             dispatcher: CollectingDispatcher,
                             tracker: Tracker,
                             domain: Dict[Text, Any]) -> Dict[Text, Any]:
        global function_library
        global new_available_option_pairs
        global new_instruction_program_pairs
        global new_function_library
        global splitted_prog
        global high_level_task
        global natural_language_plans
        global logical_relations
        global components_for_pseudo_code
        global explanation
        global ASK_INSTRUCTION_FIRST_TIME

        print("Validating instruction...")
        # Check if the instruction is valid
        if slot_value is None or slot_value.strip() == '':
            dispatcher.utter_message(text="Please give me an instruction.")
            ASK_INSTRUCTION_FIRST_TIME = False
            return {"instruction": None}
        
        # Classify the instruction: Instruction or Conversation 
        # if LOCAL_LLM:
        #     classification, _ = generator.generate([slot_value], 2) 
        #     # print(f"classification: {classification}")
        #     # print(f"typeof classification: {type(classification)}")
        #     if "Conversation" in classification:
        #         # print("conversation, before send_text_to_chat")
        #         chat_response = generator.send_text_to_chat(slot_value)
        #         # print("conversation, after send_text_to_chat")
        #         print(f"chat_response: {chat_response}")
        #         dispatcher.utter_message(text=chat_response)
        #         return {"instruction": None}
        #     # else:
        #     #     print(f"not conversation, classification: {classification}")

        # normalized_slot_value = slot_value.strip().replace(' ', '_').upper()
        # normalized_slot_value = re.sub('\W+','', slot_value.strip().replace(' ', '_').upper())
        # if normalized_slot_value in new_function_library:
        #     splitted_prog = [normalized_slot_value]
        # elif (normalized_slot_value != 'FIND') and (normalized_slot_value in function_library):
        #     splitted_prog = [normalized_slot_value] 
        # else:
        # Make the instruction to be pseudo instruction
        # if LOCAL_LLM:
        #     pseudo_instruction, _ = generator.generate([slot_value], 3) 
        #     print(f"pseudo_instruction: {pseudo_instruction}")
        #     if FIND_SIMILAR:
        #         similar_pseudo_instruction, _ = generator.generate([','.join(function_library), new_available_option_pairs, pseudo_instruction], 5)
        #         if 'None' not in similar_pseudo_instruction:
        #             print(f"similar_pseudo_instruction: {similar_pseudo_instruction}")
        #             pseudo_instruction = similar_pseudo_instruction 
        #     if pseudo_instruction in new_function_library:
        #         splitted_prog = [pseudo_instruction]
        #     elif (pseudo_instruction != 'FIND') and (pseudo_instruction in function_library):
        #         splitted_prog = [pseudo_instruction] 
        #     else:
        #         slot_value = pseudo_instruction

        if GPT_WITH_LOCAL_LLM:
            prog, _ = generator_openai.generate(
                (','.join(function_library), new_available_option_pairs, new_instruction_program_pairs, slot_value)
            )
            if not prog:
                dispatcher.utter_message(
                    text="Sorry, I could not generate a program for that instruction. Please try again."
                )
                ASK_INSTRUCTION_FIRST_TIME = False
                return {"instruction": None}
            try:
                high_level_task, pseudo_instruction, natural_language_plans, logical_relations, components_for_pseudo_code, pseudo_code, explanation = extract_components2(prog)
            except ValueError as exc:
                print(f"Failed to parse LLM output: {exc}")
                print(f"raw_output: {prog}")
                dispatcher.utter_message(
                    text="Sorry, I could not understand the generated program. Please try a different instruction."
                )
                ASK_INSTRUCTION_FIRST_TIME = False
                return {"instruction": None}
            prog = pseudo_code
        else:
            pseudo_instruction = re.sub(r'\W+', '', slot_value.strip().replace(' ', '_').upper())
            prog, _ = generator.generate(
                (','.join(function_library), new_available_option_pairs, new_instruction_program_pairs, slot_value), 4
            )
        prog = prog.upper()
        
        if not go1.check_simplified_syntax_validity(prog):
            dispatcher.utter_message(text="Sorry, I cannot understand the given instruction. Please give me a different instruction.")
            ASK_INSTRUCTION_FIRST_TIME = False
            return {"instruction": None}
        else:
            splitted_prog = prog.split('\n') 

        # return {"instruction": slot_value}
        return {"instruction": pseudo_instruction}

class ActionAskInstruction(Action):
    def name(self) -> Text:
        return "action_ask_instruction"
    
    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]: 

        global ASK_INSTRUCTION_FIRST_TIME
        if ASK_INSTRUCTION_FIRST_TIME:
            dispatcher.utter_message(text="Yes, What do you want me to do?")
        else:
            dispatcher.utter_message(text="What do you want me to do?")
            ASK_INSTRUCTION_FIRST_TIME = True

        return []

class ValidateBlockChangeForm(FormValidationAction):
    def name(self) -> Text:
        return "validate_block_change_form"
    
    # https://rasa.com/docs/rasa/forms/#custom-slot-mappings 
    async def required_slots(self,
                             domain_slots: List[Text],
                             dispatcher: CollectingDispatcher,
                             tracker: Tracker,
                             domain: Dict[Text, Any]) -> List[Text]:
        global intent_to_revise_decomposed_actions 

        additional_slots = []

        if intent_to_revise_decomposed_actions in ["change", "add"]: 
            additional_slots.append("instruction_to_change_into")

        return domain_slots + additional_slots

    def validate_block_number(self,
                              slot_value: Any,
                              dispatcher: CollectingDispatcher,
                              tracker: Tracker,
                              domain: Dict[Text, Any]) -> Dict[Text, Any]:
        # Check if the block number is valid
        global splitted_prog
        global intent_to_revise_decomposed_actions 

        if type(slot_value) == int:
            pass
        elif slot_value.strip() == '':
            dispatcher.utter_message(text="Please enter a block number.")
            return {"block_number": None, "number": None, "ordinal": None}
        else:
            # https://forum.rasa.com/t/using-duckling-to-fill-multiple-time-slots-in-rasa-form/28380/3 
            duckling_number = tracker.get_slot("number")
            duckling_ordinal = tracker.get_slot("ordinal")
            print(f"duckling_number: {duckling_number} duckling_ordinal: {duckling_ordinal}")
            print(f"duckliing_number type: {type(duckling_number)} duckling_ordinal type: {type(duckling_ordinal)}")
            # dispatcher.utter_message(text=f"duckling_number: {duckling_number} duckling_ordinal: {duckling_ordinal}")
            if duckling_number is not None:
                slot_value = duckling_number
            elif duckling_ordinal is not None: 
                slot_value = duckling_ordinal
            else:
                dispatcher.utter_message(text="Please enter a block number.")
                return {"block_number": None, "number": None, "ordinal": None}
        
        offset = 0
        if intent_to_revise_decomposed_actions == "add":
            offset = 1 
            latest_message = tracker.latest_message['text'].strip()
            if "before" in latest_message:
                pass
            elif "after" in latest_message:
                slot_value = slot_value + 1
            else:
                dispatcher.utter_message(text="Please say a block number with 'before' or 'after'.")
                return {"block_number": None, "number": None, "ordinal": None}
        if (slot_value < 1) or (slot_value > (len(splitted_prog) + offset)):
            dispatcher.utter_message(text="Please enter a valid block number.")
            return {"block_number": None, "number": None, "ordinal": None}
        if intent_to_revise_decomposed_actions == "change" or intent_to_revise_decomposed_actions == "delete":
            if slot_value not in get_valid_block_number(splitted_prog):
                dispatcher.utter_message(text=f"END block cannot be {intent_to_revise_decomposed_actions}d.")
                return {"block_number": None, "number": None, "ordinal": None}
        return {"block_number": slot_value, "number": None, "ordinal": None, "instruction_to_change_into": None}
    
    def validate_instruction_to_change_into(self,
                                            slot_value: Any,
                                            dispatcher: CollectingDispatcher,
                                            tracker: Tracker,
                                            domain: Dict[Text, Any]) -> Dict[Text, Any]:
        # Check if the instruction is valid
        slot_value = tracker.get_slot("instruction_to_change_into")
        if (slot_value is None):
            return {}
        elif (slot_value.strip() == ''):
            dispatcher.utter_message(text="Please give me an instruction.")
            return {"instruction_to_change_into": None}

        print(f"slot_value: {slot_value} tracker.get_slot('instruction_to_change_into'): {tracker.get_slot('instruction_to_change_into')}")

        global function_library
        global new_available_option_pairs 
        global new_instruction_program_pairs
        global new_instruction 

        normalized_slot_value = re.sub('\W+','', slot_value.strip().replace(' ', '_').upper())
        if normalized_slot_value in new_function_library:
            # local_splitted_prog = [normalized_slot_value]
            return {"instruction_to_change_into": normalized_slot_value}
        elif (normalized_slot_value != 'FIND') and (normalized_slot_value in function_library):
            # local_splitted_prog = [normalized_slot_value] 
            return {"instruction_to_change_into": normalized_slot_value}
        else:
            pseudo_instruction, _ = generator.generate([slot_value], 3)
            print(f"pseudo_instruction: {pseudo_instruction}")
            if pseudo_instruction in new_function_library:
                return {"instruction_to_change_into": pseudo_instruction}
            elif (pseudo_instruction != 'FIND') and (pseudo_instruction in function_library):
                return {"instruction_to_change_into": pseudo_instruction}
            else:
                slot_value = pseudo_instruction

            if GPT_WITH_LOCAL_LLM:
                prog, _ = generator_openai_to_revise.generate(
                    (','.join(function_library), new_available_option_pairs, new_instruction_program_pairs, slot_value)
                )
            else:
                prog, _ = generator.generate(
                    (','.join(function_library), new_available_option_pairs, new_instruction_program_pairs, slot_value), 1
                )

            prog = prog.replace('+', ' ')
            prog = prog.upper()
            
            if not go1.check_simplified_syntax_validity(prog):
                dispatcher.utter_message(text="Sorry, I cannot understand the given instruction. Please give me a different instruction.")
                return {"instruction_to_change_into": None} 
            
            local_splitted_prog = prog.split('\n')
            print(f"local_splitted_prog: {local_splitted_prog}")
        
        if len(local_splitted_prog) > 1:
            if (normalized_slot_value == new_instruction) or (normalized_slot_value in new_instruction_to_decompose_list):
                dispatcher.utter_message(text=f"This instruction is already being saved. Please give me a different instruction.")
                return {"instruction_to_change_into": None}
            global new_instruction_candidate 
            new_instruction_candidate = normalized_slot_value
            global new_instruction_user_input_candidate
            new_instruction_user_input_candidate = slot_value
            global splitted_prog_candidate
            splitted_prog_candidate = local_splitted_prog

            return {"instruction_to_change_into": normalized_slot_value, "new_instruction_while_defining": True}

        if normalized_slot_value == new_instruction:
            dispatcher.utter_message(text=f"This instruction is already being saved. Please give me a different instruction.")
            return {"instruction_to_change_into": None}

        return {"instruction_to_change_into": local_splitted_prog[0]}

# https://rasa.com/docs/rasa/forms/#using-a-custom-action-to-ask-for-the-next-slot 
# https://forum.rasa.com/t/dynamic-utter-ask-in-form/48169/3 
class ActionAskBlockNumber(Action):
    def name(self) -> Text:
        return "action_ask_block_number"
    
    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]: 

        global intent_to_revise_decomposed_actions 
        current_intent = intent_to_revise_decomposed_actions 

        if current_intent == "change":
            dispatcher.utter_message(text="Which block do you want to change?")
        elif current_intent == "add":
            dispatcher.utter_message(text="Where do you want to add a new block?")
        elif current_intent == "delete":
            dispatcher.utter_message(text="Which block do you want to remove?")
        else:
            print(f"In ActionAskBlockNumber class, current_intent: {current_intent}")
            raise NotImplementedError(current_intent)
        return [SlotSet("instruction_to_change_into", None), SlotSet("block_number", None), SlotSet("number", None), SlotSet("ordinal", None)] 

class ActionAskInstructionToChangeInto(Action):
    def name(self) -> Text:
        return "action_ask_instruction_to_change_into"
    
    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]: 

        global intent_to_revise_decomposed_actions
        current_intent = intent_to_revise_decomposed_actions

        if current_intent == "change":
            dispatcher.utter_message(text="Which instruction do you want to change into?")
        elif current_intent == "add":
            dispatcher.utter_message(text="Which instruction do you want to add?")
        else:
            print(f"In ActionAskInstructionToChangeInto class, current_intent: {current_intent}")
            raise NotImplementedError(current_intent)
        
        return []

class ActionProcessInstruction(Action):
    def name(self) -> Text:
        return "action_process_instruction"
    
    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        global splitted_prog
        global new_instruction
        global new_instruction_user_input

        # Get the instruction from the user
        print("Getting instruction from the user...")
        print(f"tracker.get_slot('instruction'): {tracker.get_slot('instruction')}")
        instruction = tracker.get_slot("instruction")
        # new_instruction = re.sub('\W+','', instruction.strip().replace(' ', '_').lower())
        new_instruction = re.sub('\W+','', instruction.strip().replace(' ', '_').upper())
        new_instruction_user_input = instruction 
        print(f"instruction: {instruction}")

        # numbered_splitted_prog = serialize_prog_with_block_number(splitted_prog)
        # numbered_prog = '\n'.join(numbered_splitted_prog)

        # dispatcher.utter_message(text="Sure, this is what I am going to do:\n")
        # dispatcher.utter_message(text=f'{new_instruction}\n' + numbered_prog)
        dispatcher.utter_message(text=f'I am going to do {new_instruction}')

        return [SlotSet("instruction", None), SlotSet("complicated_instruction", len(splitted_prog) > 1)]

class ActionTellInstruction(Action):
    def name(self) -> Text:
        return "action_tell_instruction"
    
    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        global splitted_prog
        global new_instruction

        print(f"ActionTellInstruction: new_instruction: {new_instruction}")

        dispatcher.utter_message(text=f'I did {new_instruction}')

        return [SlotSet("instruction", None), SlotSet("complicated_instruction", len(splitted_prog) > 1)]

class ActionRunProgram(Action):
    def name(self) -> Text:
        return "action_run_program"
    
    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        global message
        global splitted_prog

        dispatcher.utter_message(text="Let's run the program!")

        complicated = tracker.get_slot("complicated_instruction")

        # Acquire the lock before modifying the shared variable
        with lock:
            message = serialize_prog(splitted_prog)
        # print(f"message: {message}")
        
        if not complicated:
            splitted_prog = []

        return []

class ActionRunProgramWithoutConfirm(Action):
    def name(self) -> Text:
        return "action_run_program_without_confirm"
    
    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        global message
        global splitted_prog
        global block_number_list

        print(f"ActionRunProgramWithoutConfirm")

        complicated = tracker.get_slot("complicated_instruction")
        print(f"complicated: {complicated}")
        dispatcher.utter_message(text="Let's run the program!")

        # Acquire the lock before modifying the shared variable
        with lock:
            message = serialize_prog(splitted_prog)
        # print(f"message: {message}")
        
        if not complicated:
            splitted_prog = []

        return [SlotSet("complicated_instruction", complicated)] 

class ActionRunProgramWithoutConfirmWithAsking(Action):
    def name(self) -> Text:
        return "action_run_program_without_confirm_with_asking"
    
    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        global message
        global splitted_prog
        global block_number_list

        print(f"ActionRunProgramWithoutConfirmWithAsking")

        complicated = tracker.get_slot("complicated_instruction")
        print(f"complicated: {complicated}")
        dispatcher.utter_message(text="Let's run the program!")

        # Acquire the lock before modifying the shared variable
        with lock:
            message = serialize_prog(splitted_prog)
        # print(f"message: {message}")
        
        if not complicated:
            splitted_prog = []
        
        dispatcher.utter_message(text=f'I am going to do {new_instruction}')
        # dispatcher.utter_message(text="Are you satisfied with it?")
        # dispatcher.utter_message(text="If you are satisfied with it, please say 'Yes'. Otherwise, please say 'No'.")
        dispatcher.utter_message(text="If you are satisfied with it, please say 'Yes'. Otherwise, please say 'Hi Spark'.")

        return [] 

class ActionProcessInstructionWithoutConfirm(Action):
    def name(self) -> Text:
        return "action_process_instruction_without_confirm"
    
    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        global splitted_prog
        global new_instruction
        global new_instruction_user_input

        print(f"ActionProcessInstructionWithoutConfirm")
        # Get the instruction from the user
        print("Getting instruction from the user...")
        print(f"tracker.get_slot('instruction'): {tracker.get_slot('instruction')}")
        instruction = tracker.get_slot("instruction")
        # new_instruction = re.sub('\W+','', instruction.strip().replace(' ', '_').lower())
        new_instruction = re.sub('\W+','', instruction.strip().replace(' ', '_').upper())
        new_instruction_user_input = instruction 
        print(f"instruction: {instruction}")
        print(f"new_instruction: {new_instruction}")

        return [SlotSet("instruction", None), SlotSet("complicated_instruction", len(splitted_prog) > 1)]

class ActionShowProgram(Action):
    def name(self) -> Text:
        return "action_show_program"
    
    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        global splitted_prog
        # global new_instruction

        # numbered_splitted_prog = serialize_prog_with_block_number(splitted_prog)
        # numbered_prog = '\n'.join(numbered_splitted_prog)

        # dispatcher.utter_message(text=f'{new_instruction}\n' + numbered_prog)
        dispatcher.utter_message(text=f'The program code is on the left side.')

        return [SlotSet("instruction", None), SlotSet("complicated_instruction", len(splitted_prog) > 1)]

class ActionTellandShowProgram(Action):
    def name(self) -> Text:
        return "action_tell_and_show_instruction"
    
    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        global splitted_prog
        global new_instruction
        
        print(f"action_tell_and_show_program: new_instruction: {new_instruction}")

        dispatcher.utter_message(text=f'I did {new_instruction}')

        numbered_splitted_prog = serialize_prog_with_block_number(splitted_prog)
        numbered_prog = '\n'.join(numbered_splitted_prog)

        
        dispatcher.utter_message(text=f'{new_instruction}\n' + numbered_prog)

        return [SlotSet("instruction", None), SlotSet("complicated_instruction", len(splitted_prog) > 1)]

class ActionReviseDecomposedActions(Action):
    def name(self) -> Text:
        return "action_revise_decomposed_actions"
    
    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        global splitted_prog
        global new_instruction
        global intent_to_revise_decomposed_actions
        global INTENT_TO_REVISE_DECOMPOSED_ACTIONS_ASSIGNED
        current_intent = intent_to_revise_decomposed_actions
        INTENT_TO_REVISE_DECOMPOSED_ACTIONS_ASSIGNED = False 

        block_number = tracker.get_slot("block_number")
        print(f"block_number: {block_number}")
        instruction_to_change_into = tracker.get_slot("instruction_to_change_into")
        print(f"instruction_to_change_into: {instruction_to_change_into}")

        if current_intent == "change":
            # Make sure the block number is valid especially the block number should not be for the END block
            dispatcher.utter_message(text=f"Let's change block {block_number} of {new_instruction}!")
            # preserve indent 
            indent, code = get_first_indent(splitted_prog[int(block_number)-1])

            splitted_prog[int(block_number)-1] = indent + instruction_to_change_into

            # if the changed code has different END block, then we need to change the END block
            code_head = code.strip().split(' ')[0]
            instruction_to_change_into_head = instruction_to_change_into.strip().split(' ')[0]
            # If the changed code has different END block, then we need to change the END block
            if code_head.lower() in ["repeat", "if", "while"]: # there is END block
                if instruction_to_change_into_head.lower() in ["repeat", "if", "while"]: # there is END block
                    # find the corresponding END block
                    end_block_number = None
                    for index, line in enumerate(splitted_prog[int(block_number):]):
                        _indent, _code = get_first_indent(line)
                        if _indent == indent and _code.strip().split(' ')[0].lower() == "end":
                            end_block_number = index + int(block_number)
                            splitted_prog[end_block_number] = indent + 'END ' + instruction_to_change_into_head
                            break
                    if end_block_number is None:
                        raise ValueError("Cannot find the corresponding END block.")
                else:   # there is no END block for the changed code
                    # find the corresponding END block
                    end_block_number = None
                    for index, line in enumerate(splitted_prog[int(block_number):]):
                        _indent, _code = get_first_indent(line)
                        if _indent == indent and _code.strip().split(' ')[0].lower() == "end":
                            end_block_number = index + int(block_number)
                            # splitted_prog[end_block_number] = indent + 'END ' + code_head
                            splitted_prog.pop(end_block_number)
                            break
                        else:
                            splitted_prog[index + int(block_number)] = _indent[:-4] + _code

                    if end_block_number is None:
                        raise ValueError("Cannot find the corresponding END block.")
            else:   # there is no END block
                if instruction_to_change_into_head.lower() in ["repeat", "if", "while"]: # there is END block
                    # add END block
                    splitted_prog.insert(int(block_number), indent + 'END ' + instruction_to_change_into_head)

            # splitted_prog[int(block_number)-1] = instruction_to_change_into
        elif current_intent == "add":
            dispatcher.utter_message(text=f"Let's add a block to {new_instruction}!")
            # preserve indent
            indent, code = get_first_indent(splitted_prog[int(block_number)-1])
            if code.startswith("END"):
                indent = indent + '    '
            splitted_prog.insert(int(block_number)-1, indent + instruction_to_change_into)
            if instruction_to_change_into.strip().split(' ')[0].lower() in ["repeat", "if", "while"]:
                splitted_prog.insert(int(block_number), indent + 'END ' + instruction_to_change_into.strip().split(' ')[0])
            # splitted_prog.insert(int(block_number)-1, instruction_to_change_into)
        elif current_intent == "delete":
            dispatcher.utter_message(text=f"Let's remove block {block_number} of {new_instruction}!")
            # preserve indent 
            indent, code = get_first_indent(splitted_prog[int(block_number)-1])
            if code.strip().split(' ')[0].lower() in ["repeat", "if", "while"]:
                # find the corresponding END block
                end_block_number = None
                for index, line in enumerate(splitted_prog[int(block_number):]):
                    _indent, _code = get_first_indent(line)
                    if _indent == indent and _code.strip().split(' ')[0].lower() == "end":
                        end_block_number = index + int(block_number)
                        break
                    else:
                        splitted_prog[index + int(block_number)] = _indent[:-4] + _code
                if end_block_number is None:
                    raise ValueError("Cannot find the corresponding END block.")

                splitted_prog.pop(end_block_number)
            splitted_prog.pop(int(block_number)-1)
        else:
            print(f"current_intent: {current_intent}")
            raise NotImplementedError(current_intent)

        numbered_splitted_prog = serialize_prog_with_block_number(splitted_prog)
        numbered_prog = '\n'.join(numbered_splitted_prog)

        dispatcher.utter_message(text=f'{new_instruction}\n'+numbered_prog)

        return [SlotSet("block_number", None), SlotSet("instruction_to_change_into", None)]

class ActionShowDecomposedActionsForChangeOrDelete(Action):
    def name(self) -> Text:
        return "action_show_decomposed_actions_for_change_or_delete"
    
    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        global splitted_prog
        global new_instruction
        global intent_to_revise_decomposed_actions

        current_intent = tracker.get_intent_of_latest_message()
        current_intent = "change" if current_intent == "revise_defined_new_instruction" else current_intent
        if current_intent not in ["change", "delete"]:
            print(f"In ActionShowDecomposedActionsForChangeOrDelete class, current_intent: {current_intent}")
            print("This should not happen.")
            current_intent = intent_to_revise_decomposed_actions
        else:
            intent_to_revise_decomposed_actions = current_intent
        
        dispatcher.utter_message(text=f"Let's {intent_to_revise_decomposed_actions} the block of {new_instruction}!")

        numbered_splitted_prog = serialize_prog_with_block_number_for_change_or_deletion(splitted_prog)
        numbered_prog = '\n'.join(numbered_splitted_prog)

        dispatcher.utter_message(text=f'{new_instruction}\n'+numbered_prog)

        return []   

class ActionShowDecomposedActionsForAddition(Action):
    def name(self) -> Text:
        return "action_show_decomposed_actions_for_addition"
    
    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        global splitted_prog
        global new_instruction
        global intent_to_revise_decomposed_actions
        global number_of_explanation_for_addition

        current_intent = tracker.get_intent_of_latest_message()
        if current_intent not in ["add"]:
            print(f"In ActionShowDecomposedActionsForAddition class, current_intent: {current_intent}")
            print("This should not happen.")
            current_intent = intent_to_revise_decomposed_actions
        else:
            intent_to_revise_decomposed_actions = current_intent

        dispatcher.utter_message(text=f"Let's add a block to {new_instruction}!")

        numbered_splitted_prog = serialize_prog_with_block_number_for_addition(splitted_prog)
        numbered_prog = '\n'.join(numbered_splitted_prog)

        dispatcher.utter_message(text=f'{new_instruction}\n'+numbered_prog)

        # if the number of explanation is more than 5, then we do not need to ask the user to explain again
        number_of_explanation_for_addition = number_of_explanation_for_addition + 1
        if number_of_explanation_for_addition <= 5:
            dispatcher.utter_message(text=f"If you want to add a block before the first block, please say 'before first' or 'before one'.")
            dispatcher.utter_message(text=f"If you want to add a block after the first block, please say 'after first' or 'after one'.")

        return []

class ActionRegisterNewInstruction(Action):
    def name(self) -> Text:
        return "action_register_new_instruction"
    
    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        global function_library
        global new_available_option_pairs
        global new_instruction_program_pairs
        global splitted_prog
        global new_instruction
        global new_instruction_user_input
        global new_instruction_to_decompose_list
        global new_instruction_user_input_list
        global splitted_prog_list
        global block_number_list
        global intent_to_revise_decomposed_actions
        global intent_to_revise_decomposed_actions_list

        dispatcher.utter_message(text="Let's save the new instruction!")

        # Get the instruction from the user
        print(f"new_instruction: {new_instruction}")
        function_library.append(new_instruction)
        new_function_library[new_instruction] = splitted_prog
        new_available_option_pairs += '\n' + new_available_option_pair.format(instruction=new_instruction, program='\n'.join(splitted_prog)+'\n') #+ '\n'
        new_instruction_program_pairs += '\n' + new_instruction_program_pair.format(instruction=new_instruction_user_input, program=new_instruction+'\n\n') #+ '\n'
        print(f"new_available_option_pairs: {new_available_option_pairs}")
        print(f"new_instruction_program_pairs: {new_instruction_program_pairs}")

        if DATABASE_ON:
            insert_new_function_library(user_id, new_instruction, '\n'.join(splitted_prog))

        splitted_prog = []

        dispatcher.utter_message(text="The new instruction has been saved successfully!")

        new_instruction_remaining_flag = tracker.get_slot("new_instruction_remaining")
        if new_instruction_remaining_flag:
            old_instruction = new_instruction 
            new_instruction = new_instruction_to_decompose_list.pop()
            new_instruction_user_input = new_instruction_user_input_list.pop()
            
            splitted_prog = splitted_prog_list.pop()
            
            block_number = block_number_list.pop()

            intent_to_revise_decomposed_actions = intent_to_revise_decomposed_actions_list.pop()

            dispatcher.utter_message(text=f"We are now defining the new instruction {new_instruction}.")
            
            return [SlotSet("complicated_instruction", True), SlotSet("block_number", block_number), SlotSet("instruction_to_change_into", old_instruction), SlotSet("new_instruction_remaining", len(block_number_list) > 0)]

        new_instruction_to_decompose_list = []
        new_instruction_user_input_list = []
        splitted_prog_list = []
        block_number_list = []
        intent_to_revise_decomposed_actions_list = [] 

        return [SlotSet("complicated_instruction", False)]

class ActionUtterLibraries(Action):
    def name(self) -> Text:
        return "action_utter_libraries"
    
    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        global basic_function_library
        global new_function_library

        dispatcher.utter_message(text=f"I can do the Pre-defined actions.")
        dispatcher.utter_message(text=f"I can also do what you want by doing many Pre-defined actions.")

        return []

class ActionUtterRecognizedObjects(Action):
    def name(self) -> Text:
        return "action_utter_recognized_objects"
    
    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]: 

        dispatcher.utter_message(text=f"I have seen the following objects: {', '.join(go1.get_recognized_objects())}.")

        return []

class ActionShowCurrentInstruction(Action):
    def name(self) -> Text:
        return "action_show_current_instruction"
    
    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        global new_instruction
        global splitted_prog

        dispatcher.utter_message(text=f'We are now defining the instruction {new_instruction}.')

        numbered_splitted_prog = serialize_prog_with_block_number(splitted_prog)
        numbered_prog = '\n'.join(numbered_splitted_prog)

        dispatcher.utter_message(text=f'{new_instruction}\n'+numbered_prog)

        return []

class ActionRemindCurrentInstructionToDefine(Action):
    def name(self) -> Text:
        return "action_remind_current_instruction_to_define"
    
    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        global new_instruction_to_decompose_list 
        global new_instruction
        new_instruction = new_instruction_to_decompose_list.pop()
        global new_instruction_user_input_list
        global new_instruction_user_input
        new_instruction_user_input = new_instruction_user_input_list.pop()
        global splitted_prog_list
        global splitted_prog
        splitted_prog = splitted_prog_list.pop()
        global block_number_list
        block_number = block_number_list.pop()
        global intent_to_revise_decomposed_actions_list
        global intent_to_revise_decomposed_actions
        intent_to_revise_decomposed_actions = intent_to_revise_decomposed_actions_list.pop()

        dispatcher.utter_message(text=f"We have returned to the new instruction {new_instruction}.")

        numbered_splitted_prog = serialize_prog_with_block_number(splitted_prog)
        numbered_prog = '\n'.join(numbered_splitted_prog)

        dispatcher.utter_message(text=f'{new_instruction}\n'+numbered_prog)

        return [] 

class ActionConfirmDecomposedActions(Action):
    def name(self) -> Text:
        return "action_confirm_decomposed_actions"
    
    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]: 

        global block_number_list

        dispatcher.utter_message(text="Do you want me to try?")

        return [SlotSet("new_instruction_remaining", len(block_number_list) > 0)] 

class ActionProcessAdditionalNewInstruction(Action):
    def name(self) -> Text:
        return "action_process_additional_new_instruction"
    
    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        global new_instruction
        global new_instruction_candidate
        global new_instruction_user_input
        global new_instruction_user_input_candidate
        global new_instruction_to_decompose_list
        global new_instruction_user_input_list
        global splitted_prog
        global splitted_prog_candidate
        global splitted_prog_list
        global block_number_list
        global intent_to_revise_decomposed_actions
        global intent_to_revise_decomposed_actions_list

        new_instruction_to_decompose_list.append(new_instruction)
        new_instruction = new_instruction_candidate
        new_instruction_candidate = ''

        new_instruction_user_input_list.append(new_instruction_user_input)
        new_instruction_user_input = new_instruction_user_input_candidate
        new_instruction_user_input_candidate = ''

        splitted_prog_list.append(splitted_prog)
        splitted_prog = splitted_prog_candidate
        splitted_prog_candidate = []

        block_number = tracker.get_slot("block_number")
        block_number_list.append(block_number)

        intent_to_revise_decomposed_actions_list.append(intent_to_revise_decomposed_actions)

        numbered_splitted_prog = serialize_prog_with_block_number(splitted_prog)
        numbered_prog = '\n'.join(numbered_splitted_prog)

        dispatcher.utter_message(text=f'{new_instruction}\n' + numbered_prog)

        return [SlotSet("new_instruction_remaining", True), SlotSet("complicated_instruction", True), SlotSet("instruction_to_change_into", None), SlotSet("new_instruction_while_defining", False), SlotSet("block_number", None)]
        
class ActionCancelAdditionalNewInstruction(Action):
    def name(self) -> Text:
        return "action_cancel_additional_new_instruction"
    
    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        global new_instruction_candidate
        global new_instruction_user_input_candidate
        global splitted_prog_candidate
        new_instruction_candidate = ''
        new_instruction_user_input_candidate = ''
        splitted_prog_candidate = []

        return [SlotSet("complicated_instruction", True), SlotSet("instruction_to_change_into", None), SlotSet("new_instruction_while_defining", False), SlotSet("block_number", None)]

if WEB_SERVER:
    import requests
    import json

    def send_message(sender, message, rasa_api_endpint=f"{RASA_SERVER_URL}/webhooks/rest/webhook"):
        data = {"sender":sender, "message":message}
        data = json.dumps(data)
        res = requests.post(url=rasa_api_endpint, data=data)

        _messages = [r['text'] for r in res.json() if r['recipient_id'] == sender]
        res_msg = '\n'.join(_messages)
        return res_msg
    
    if not RASA_TEST: 
        # https://blog.miguelgrinberg.com/post/video-streaming-with-flask 
        def video_streaming(resize=True, resized_resolution=(320, 240)):
            while True:
                if resize:
                    _, frame_bytes = cv2.imencode('.jpg', cv2.resize(go1.get_frame(), resized_resolution))
                else:
                    _, frame_bytes = cv2.imencode('.jpg', go1.get_frame())
                frame = frame_bytes.tobytes()
                yield (b'--frame\r\n'
                    b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

        @app.route('/video_feed')
        def video_feed():
            return Response(video_streaming(resize=False),
                            mimetype='multipart/x-mixed-replace; boundary=frame')
    else:
        def video_streaming():
            while True:
                # just for testing, so we do not need to get the frame from the camera
                # create a black image
                img = np.zeros((320,240,3), np.uint8)
                # Convert NumPy array to PIL Image
                pil_img = Image.fromarray(img)
                # Create an in-memory binary stream (BytesIO object)
                img_bytesio = BytesIO()
                # Save the PIL Image as a JPEG image to the binary stream
                pil_img.save(img_bytesio, format='JPEG')
                # Get the binary data from the stream
                frame = img_bytesio.getvalue()

                yield (b'--frame\r\n'
                    b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

        @app.route('/video_feed')
        def video_feed():
            return Response(video_streaming(),
                            mimetype='multipart/x-mixed-replace; boundary=frame')

    # Define this outside the route so that it is only defined once at startup.
    if TTS_ON:
        def add_to_tts(message):
            global message_for_tts 
            with lock:
                message_for_tts.append(message)
    else:
        def add_to_tts(message):
            pass  # If TTS is not on, do nothing.

    @app.route('/process_text_input', methods=['POST'])
    def process_text_input():
        data_from_webpage = request.form['text_input']
        print(f"data_from_webpage: {data_from_webpage}")
        response = send_message("user", data_from_webpage)
        # Use the conditionally defined function. This will either append the response
        # to the message_for_tts list or do nothing, depending on TTS_ON.
        add_to_tts(response) 
        return response 
    
    @app.route('/get_current_libraries', methods=['GET'])
    def get_current_libraries():
        global basic_function_library
        global new_function_library
        return jsonify({'basic_function_library': basic_function_library, 'new_function_library': list(new_function_library.keys())})
    
    @app.route('/get_current_instruction', methods=['GET'])
    def get_current_instruction():
        global new_instruction_user_input
        return jsonify({'instruction': new_instruction_user_input})
    
    @app.route('/get_high_level_task', methods=['GET'])
    def get_high_level_task():
        global high_level_task
        return jsonify({'high_level_task': high_level_task})

    @app.route('/get_natural_language_plans', methods=['GET'])
    def get_natural_language_plans():
        global natural_language_plans
        return jsonify({'natural_language_plans': natural_language_plans})
    
    @app.route('/get_logical_relations', methods=['GET'])
    def get_logical_relations():
        global logical_relations
        return jsonify({'logical_relations': logical_relations})
    
    @app.route('/get_components_for_pseudo_code', methods=['GET'])
    def get_components_for_pseudo_code():
        global components_for_pseudo_code
        return jsonify({'components_for_pseudo_code': components_for_pseudo_code})
    
    @app.route('/get_explanation', methods=['GET'])
    def get_explanation():
        global explanation
        return jsonify({'explanation': explanation})

    @app.route('/get_current_code', methods=['GET'])
    def get_current_code():
        global splitted_prog
        return jsonify({'code': '\n'.join(splitted_prog)})

    def flask_run():
        socketio.run(app, port=WEB_SERVER_PORT, debug=True, use_reloader=False)

    @app.route('/')
    def index():
        return render_template('index.html')

    threading.Thread(target=flask_run, daemon=True).start()

if __name__ == "__main__":
    # https://github.com/opencv/opencv/issues/22602 
    try:
        while True:
            frame = go1.get_frame()
            if frame is not None:
                cv2.imshow("video0", frame)
                if cv2.waitKey(2) & 0xFF == ord('q'):
                    break
    except KeyboardInterrupt:
        cv2.destroyAllWindows()
        exit()
