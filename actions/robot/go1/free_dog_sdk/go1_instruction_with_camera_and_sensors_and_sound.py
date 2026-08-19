# from ucl.common import byte_print, decode_version, decode_sn, getVoltage, lib_version
from ucl.highCmd import highCmd
from ucl.highState import highState
# from ucl.lowCmd import lowCmd
from ucl.unitreeConnection import unitreeConnection, HIGH_WIFI_DEFAULTS, HIGH_WIRED_DEFAULTS
from ucl.enums import MotorModeHigh, GaitType #, SpeedLevel
# from ucl.complex import motorCmd

from go1_camera import go1_camera
from go1_ultrasound import go1_ultrasound
from go1_nano1_sound import Nano1Connection

from human_friendly_python_syntax_converter import HumanFriendlyPythonSyntaxConverter 

import os 
import sys 
sys.path.insert(1, os.path.join(sys.path[0], '../..'))
try:
    from ttsengine_with_coqui_tts_server import TTSEngine_with_Coqui_TTS_Server
except ModuleNotFoundError:
    print('TTS engine not available')
sys.path.pop(1)

import cv2

import math 
import threading 
import time
import re
import ast
import hashlib 

ULTRASOUND_PORT = 12345

# print(f'Running lib version: {lib_version()}')

class go1_highcommand:
    BATTERY_STOP_TEMP = 50
    MCU_STOP_TEMP = 50

    FACE_STOP_DISTANCE = 0.3
    LEFT_STOP_DISTANCE = 0.3
    RIGHT_STOP_DISTANCE = 0.3

    FACE_NEAR_DISTANCE = 0.5
    LEFT_NEAR_DISTANCE = 0.5
    RIGHT_NEAR_DISTANCE = 0.5

    SLEEP_TIME = 1 
    FORCE_STAND_SLEEP_TIME = 2 
    STAND_UP_SLEEP_TIME = 2 
    JUMP_YAW_SLEEP_TIME = 1
    STRAIGHT_HAND_SLEEP_TIME = 7
    DANCE1_SLEEP_TIME = 18
    DANCE2_SLEEP_TIME = 38
    TILT_SLEEP_TIME = 2 

    MOVING_REPETITIONS = 1
    READY_TO_MOVE_LIST = [MotorModeHigh.FORCE_STAND, MotorModeHigh.VEL_WALK, MotorModeHigh.JUMPYAW, MotorModeHigh.STRAIGHTHAND, MotorModeHigh.DANCE1, MotorModeHigh.DANCE2]
    UNABLE_TO_MOVE_LIST = [MotorModeHigh.STAND_DOWN, MotorModeHigh.DAMPING] 

    DEFAULT_FOOT_RAISE_HEIGHT = 0.00
    DEFAULT_BODY_HEIGHT = 0.0 
    DEFAULT_EULER = (0, 0, 0)
    DEFAULT_VELOCITY = 0.2
    
    DEFAULT_TILT_SHOULDER = 0.5 
    DEFAULT_TILT_HEAD_UPDOWN = 0.6
    DEFAULT_TILT_HEAD_LEFTRIGHT = 0.2
    
    def __init__(self, connection_settings=HIGH_WIRED_DEFAULTS, camera_id=1, get_brightness=True, ultrasound_port=ULTRASOUND_PORT, audio=False, debug=False):
        # self.lock = threading.Lock()
        self.condition = threading.Condition()

        self.conn = unitreeConnection(connection_settings)
        self.conn.startRecv()
        self.hcmd = highCmd()
        self.hstate = highState()
        # Send empty command to tell the dog the receive port and initialize the connectin
        cmd_bytes = self.hcmd.buildCmd(debug=debug)
        self.conn.send(cmd_bytes)
        time.sleep(0.5) # Some time to collect pakets ;)

        threading.Thread(target=self.monitor_temperature).start()

        local_ip = connection_settings[-1].split('.')
        WIFI = True if local_ip[2] == '12' else False 
        self.frame = None 
        self.boxes = [] 
        self.confidences = [] 
        self.class_ids = [] 
        self.centers = []
        self.get_brightness = get_brightness
        self.brightness = None 
        self.go1_camera_module = go1_camera(camera_id, WIFI=WIFI, IpLastSegment=int(local_ip[-1]), main_thread=False, get_brightness=get_brightness)
        self.available_classes = self.go1_camera_module.get_classes()
        print(self.available_classes)
        self.camera_data_generator = self.go1_camera_module.run()
        threading.Thread(target=self.get_camera_data).start()
        print('Camera loaded')
        self.found_after_find = {} 

        self.distance_from_face = -1 
        self.distance_from_left = -1  
        self.distance_from_right = -1  
        self.ultrasound = go1_ultrasound(ultrasound_port, debug=debug)
        self.ultrasound_data_generator = self.ultrasound.run()
        threading.Thread(target=self.get_ultrasound_data).start()

        print('Waiting for ultrasound sensors to be initialized')
        while True: 
            with self.condition:
                if self.distance_from_face != -1 and self.distance_from_left != -1 and self.distance_from_right != -1:
                    print('All sensors initialized')
                    break
        
        self.nano1_connection = None
        self.tts_engine = None
        if audio:
            self.nano1_connection = Nano1Connection('192.168.123.13', '~/.ssh/id_rsa', '/home/unitree/audio/files')
            self.tts_engine = TTSEngine_with_Coqui_TTS_Server()
            self.audio_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'audio')
            if not os.path.isdir(self.audio_dir):
                os.mkdir(self.audio_dir)

    def send_hcmd(self):
        cmd_bytes = self.hcmd.buildCmd(debug=False)
        self.conn.send(cmd_bytes)
    
    def set_hcmd(self, mode, gaitType, euler, velocity, yawSpeed, footRaiseHeight, bodyHeight):
        self.hcmd.mode = mode
        self.hcmd.gaitType = gaitType
        self.hcmd.euler = euler
        self.hcmd.velocity = velocity
        self.hcmd.yawSpeed = yawSpeed
        self.hcmd.footRaiseHeight = footRaiseHeight
        self.hcmd.bodyHeight = bodyHeight

    def get_data(self):
        data = self.conn.getData()
        for paket in data:
            self.hstate.parseData(paket)
        return self.hstate

    def get_camera_data(self):
        if self.get_brightness:
            while True:
                self.boxes, self.confidences, self.class_ids, self.centers, self.frame, self.brightness = next(self.camera_data_generator)
        else:
            while True:
                self.boxes, self.confidences, self.class_ids, self.centers, self.frame = next(self.camera_data_generator)
    
    def get_recognized_objects(self):
        return [self.available_classes[class_id] for class_id in self.class_ids] 

    def get_frame(self):
        return self.frame

    def get_ultrasound_data(self):
        while True:
            self.distance_from_face, self.distance_from_left, self.distance_from_right = next(self.ultrasound_data_generator)

    def play_soundfile(self, file_name):
        if self.nano1_connection is not None:
            if os.path.exists(file_name):
                self.nano1_connection.transfer_and_play_wav(file_name)
        else:
            print('Nano 1 connection not initialized')
    
    def tts(self, text):
        if self.tts_engine is not None:
            text_name = re.sub('\W+','', text.replace(' ', '_').lower())
            file_name = os.path.join(self.audio_dir, f'{text_name}.wav')
            if len(file_name) > 255:
                # Create a hash of the filename to ensure it's a valid length including the path
                hasher = hashlib.sha256()
                hasher.update(file_name.encode('utf-8'))
                file_name = os.path.join(self.audio_dir, f"{hasher.hexdigest()}.wav")
            if not os.path.exists(file_name):
                self.tts_engine.tts(text, filename=file_name, play=False)
            self.play_soundfile(file_name)
        else:
            print('TTS engine not initialized')

    def monitor_temperature(self):
        while True:
            data = self.conn.getData()
            for paket in data:
                self.hstate.parseData(paket)
                if self.hstate.bms.BQ_NTC[0] > self.BATTERY_STOP_TEMP or self.hstate.bms.BQ_NTC[1] > self.BATTERY_STOP_TEMP:
                    print('Battery temperature too high, stopping')
                    self.hcmd.mode = MotorModeHigh.DAMPING
                    cmd_bytes = self.hcmd.buildCmd(debug=False)
                    self.conn.send(cmd_bytes)
                    exit()
                if self.hstate.bms.MCU_NTC[0] > self.MCU_STOP_TEMP or self.hstate.bms.MCU_NTC[1] > self.MCU_STOP_TEMP:
                    print('MCU temperature too high, stopping')
                    self.hcmd.mode = MotorModeHigh.DAMPING
                    cmd_bytes = self.hcmd.buildCmd(debug=False)
                    self.conn.send(cmd_bytes)
                    exit()
            time.sleep(1)
    
    def collision_avoidance(self):
        if (self.distance_from_face == 0 or self.distance_from_face > self.FACE_STOP_DISTANCE) and (self.distance_from_left == 0 or self.distance_from_left > self.LEFT_STOP_DISTANCE) and (self.distance_from_right == 0 or self.distance_from_right > self.RIGHT_STOP_DISTANCE): 
            return True
        else:
            print('To avoid collision, stopping')
            return False
    
    def get_ready_to_move_when_standing(self):
        if self.hcmd.mode in self.UNABLE_TO_MOVE_LIST:
            return 
        if self.hcmd.mode not in self.READY_TO_MOVE_LIST:
            self._force_stand()  

    def far(self):
        return ((self.distance_from_face == 0) or (self.distance_from_face > self.FACE_NEAR_DISTANCE)) and ((self.distance_from_left == 0) or (self.distance_from_left > self.LEFT_NEAR_DISTANCE)) and ((self.distance_from_right == 0) or (self.distance_from_right > self.RIGHT_NEAR_DISTANCE))
        # return ((self.distance_from_face == 0) or (self.distance_from_face > self.FACE_NEAR_DISTANCE)) 
    
    def near(self):
        return ((self.distance_from_face != 0) and (self.distance_from_face <= self.FACE_NEAR_DISTANCE)) or ((self.distance_from_left != 0) and (self.distance_from_left <= self.LEFT_NEAR_DISTANCE)) or ((self.distance_from_right != 0) and (self.distance_from_right <= self.RIGHT_NEAR_DISTANCE))
        # return ((self.distance_from_face != 0) and (self.distance_from_face <= self.FACE_NEAR_DISTANCE))
    
    def light(self):
        return self.brightness 
    
    def dark(self):
        return not self.brightness
    
    def found(self, object_to_find):
        if object_to_find in self.found_after_find:
            return self.found_after_find[object_to_find]
        else:
            return False

    def _idle(self):
        self.set_hcmd(MotorModeHigh.IDLE, GaitType.TROT, self.DEFAULT_EULER, [0, 0], 0, 0, self.DEFAULT_BODY_HEIGHT)
        self.send_hcmd()
        time.sleep(self.SLEEP_TIME)

    def _force_stand(self):
        self.set_hcmd(MotorModeHigh.FORCE_STAND, GaitType.TROT, self.DEFAULT_EULER, [0, 0], 0, 0, self.DEFAULT_BODY_HEIGHT)
        self.send_hcmd()
        time.sleep(self.FORCE_STAND_SLEEP_TIME)
    
    def _stand_down(self):
        if self.collision_avoidance():
            self.set_hcmd(MotorModeHigh.STAND_DOWN, GaitType.TROT, self.DEFAULT_EULER, [0, 0], 0, 0, self.DEFAULT_BODY_HEIGHT)
            self.send_hcmd()
            time.sleep(self.SLEEP_TIME)
        else:
            print('To avoid collision, stopping')
    
    def _stand_up(self):
        if self.collision_avoidance():
            self.set_hcmd(MotorModeHigh.STAND_UP, GaitType.TROT, self.DEFAULT_EULER, [0, 0], 0, 0, self.DEFAULT_BODY_HEIGHT)
            self.send_hcmd()
            time.sleep(self.STAND_UP_SLEEP_TIME)
        else:
            print('To avoid collision, stopping')
        
    def _damping(self):
        if self.collision_avoidance():
            self.set_hcmd(MotorModeHigh.DAMPING, GaitType.TROT, self.DEFAULT_EULER, [0, 0], 0, 0, self.DEFAULT_BODY_HEIGHT)
            self.send_hcmd()
            time.sleep(self.SLEEP_TIME) 
        else:
            print('To avoid collision, stopping')
    
    def stand_down(self):
        self._stand_down()
        self._damping()
    
    def stand_up(self):
        if self.hcmd.mode in [MotorModeHigh.STAND_DOWN, MotorModeHigh.DAMPING]:
            self._stand_down()
        self._stand_up()

    def tilt_left_shoulder(self):
        self.get_ready_to_move_when_standing()
        if self.collision_avoidance():
            self.set_hcmd(MotorModeHigh.FORCE_STAND, GaitType.TROT, (-self.DEFAULT_TILT_SHOULDER, 0, 0), [0, 0], 0, 0, self.DEFAULT_BODY_HEIGHT)
            self.send_hcmd()
            time.sleep(self.SLEEP_TIME)
        else:
            print('To avoid collision, stopping')
    
    def tilt_right_shoulder(self):
        self.get_ready_to_move_when_standing()
        if self.collision_avoidance():
            self.set_hcmd(MotorModeHigh.FORCE_STAND, GaitType.TROT, (self.DEFAULT_TILT_SHOULDER, 0, 0), [0, 0], 0, 0, self.DEFAULT_BODY_HEIGHT)
            self.send_hcmd()
            time.sleep(self.SLEEP_TIME)
        else:
            print('To avoid collision, stopping')
    
    def tilt_head_up(self):
        self.get_ready_to_move_when_standing()
        if self.collision_avoidance():
            self.set_hcmd(MotorModeHigh.FORCE_STAND, GaitType.TROT, (0, -self.DEFAULT_TILT_HEAD_UPDOWN, 0), [0, 0], 0, 0, self.DEFAULT_BODY_HEIGHT)
            self.send_hcmd()
            time.sleep(self.SLEEP_TIME)
        else:
            print('To avoid collision, stopping')
    
    def tilt_head_down(self):
        self.get_ready_to_move_when_standing()
        if self.collision_avoidance():
            self.set_hcmd(MotorModeHigh.FORCE_STAND, GaitType.TROT, (0, self.DEFAULT_TILT_HEAD_UPDOWN, 0), [0, 0], 0, 0, self.DEFAULT_BODY_HEIGHT)
            self.send_hcmd()
            time.sleep(self.SLEEP_TIME)
        else:
            print('To avoid collision, stopping')
    
    def tilt_head_left(self):
        self.get_ready_to_move_when_standing()
        if self.collision_avoidance():
            self.set_hcmd(MotorModeHigh.FORCE_STAND, GaitType.TROT, (0, 0, self.DEFAULT_TILT_HEAD_LEFTRIGHT), [0, 0], 0, 0, self.DEFAULT_BODY_HEIGHT)
            self.send_hcmd()
            time.sleep(self.SLEEP_TIME)
        else:
            print('To avoid collision, stopping')
    
    def tilt_head_right(self):
        self.get_ready_to_move_when_standing()
        if self.collision_avoidance():
            self.set_hcmd(MotorModeHigh.FORCE_STAND, GaitType.TROT, (0, 0, -self.DEFAULT_TILT_HEAD_LEFTRIGHT), [0, 0], 0, 0, self.DEFAULT_BODY_HEIGHT)
            self.send_hcmd()
            time.sleep(self.SLEEP_TIME)
        else:
            print('To avoid collision, stopping')

    def move_forward(self):
        # Unlock walking 
        # mode 6 STAND_UP -> mode 1 FORCE_STAND -> mode 2 VEL_WALK 
        self.get_ready_to_move_when_standing()
        
        for _ in range(self.MOVING_REPETITIONS):
            if self.collision_avoidance():
                self.set_hcmd(MotorModeHigh.VEL_WALK, GaitType.TROT, self.DEFAULT_EULER, [self.DEFAULT_VELOCITY, 0], 0, self.DEFAULT_FOOT_RAISE_HEIGHT, self.DEFAULT_BODY_HEIGHT)
                self.send_hcmd()
                time.sleep(self.SLEEP_TIME) 
            else:
                print('To avoid collision, stopping')
                return
    
    def _move_backward(self):
        # Unlock walking 
        # mode 6 STAND_UP -> mode 1 FORCE_STAND -> mode 2 VEL_WALK 
        self.get_ready_to_move_when_standing()
        
        for _ in range(self.MOVING_REPETITIONS):
            if self.collision_avoidance():
                self.set_hcmd(MotorModeHigh.VEL_WALK, GaitType.TROT, self.DEFAULT_EULER, [-self.DEFAULT_VELOCITY, 0], 0, self.DEFAULT_FOOT_RAISE_HEIGHT, self.DEFAULT_BODY_HEIGHT)
                self.send_hcmd()
                time.sleep(self.SLEEP_TIME) 
            else:
                print('To avoid collision, stopping')
                return
    
    def move_left(self):
        # Unlock walking 
        # mode 6 STAND_UP -> mode 1 FORCE_STAND -> mode 2 VEL_WALK 
        self.get_ready_to_move_when_standing()
        
        for _ in range(self.MOVING_REPETITIONS):
            if self.collision_avoidance():
                self.set_hcmd(MotorModeHigh.VEL_WALK, GaitType.TROT, self.DEFAULT_EULER, [0, self.DEFAULT_VELOCITY], 0, self.DEFAULT_FOOT_RAISE_HEIGHT, self.DEFAULT_BODY_HEIGHT)
                self.send_hcmd()
                time.sleep(self.SLEEP_TIME) 
            else:
                print('To avoid collision, stopping')
                return
    
    def move_right(self):
        # Unlock walking 
        # mode 6 STAND_UP -> mode 1 FORCE_STAND -> mode 2 VEL_WALK 
        self.get_ready_to_move_when_standing()
        
        for _ in range(self.MOVING_REPETITIONS):
            if self.collision_avoidance():
                self.set_hcmd(MotorModeHigh.VEL_WALK, GaitType.TROT, self.DEFAULT_EULER, [0, -self.DEFAULT_VELOCITY], 0, self.DEFAULT_FOOT_RAISE_HEIGHT, self.DEFAULT_BODY_HEIGHT)
                self.send_hcmd()
                time.sleep(self.SLEEP_TIME) 
            else:
                print('To avoid collision, stopping')
                return

    def _turn_intermediate(self, angle=90):
        self.get_ready_to_move_when_standing()

        yawSpeed = angle / 90 * 2 
        if yawSpeed > 0:
            self.set_hcmd(MotorModeHigh.VEL_WALK, GaitType.TROT, self.DEFAULT_EULER, [0.04, 0.1], yawSpeed, self.DEFAULT_FOOT_RAISE_HEIGHT, self.DEFAULT_BODY_HEIGHT)
        else:
            self.set_hcmd(MotorModeHigh.VEL_WALK, GaitType.TROT, self.DEFAULT_EULER, [0.1, 0.04], yawSpeed, self.DEFAULT_FOOT_RAISE_HEIGHT, self.DEFAULT_BODY_HEIGHT)
        
        if self.collision_avoidance():
            self.send_hcmd()
            time.sleep(self.SLEEP_TIME * yawSpeed)
        else:
            print('To avoid collision, stopping')

    def turn_simple(self, yawSpeed=2):
        self.get_ready_to_move_when_standing()
        
        if yawSpeed > 0:
            self.set_hcmd(MotorModeHigh.VEL_WALK, GaitType.TROT, self.DEFAULT_EULER, [0.04, 0.1], yawSpeed, self.DEFAULT_FOOT_RAISE_HEIGHT, self.DEFAULT_BODY_HEIGHT)
        else:
            self.set_hcmd(MotorModeHigh.VEL_WALK, GaitType.TROT, self.DEFAULT_EULER, [0.1, 0.04], yawSpeed, self.DEFAULT_FOOT_RAISE_HEIGHT, self.DEFAULT_BODY_HEIGHT)
        
        if self.collision_avoidance():
            self.send_hcmd()
        
            sleep_time = self.SLEEP_TIME * math.ceil(abs(yawSpeed)) 
            i = 0
            while i < sleep_time:
                if self.collision_avoidance():
                    time.sleep(1)
                    i += 1
                else:
                    self.set_hcmd(MotorModeHigh.IDLE, GaitType.TROT, self.DEFAULT_EULER, [0, 0], 0, 0, self.DEFAULT_BODY_HEIGHT)
                    self.send_hcmd()
                    print('To avoid collision, stopping')
                    break
        else:
            print('To avoid collision, stopping')
    
    def turn_left(self):
        self.turn_simple(2)
    
    def turn_right(self):
        self.turn_simple(-2)
    
    def spin_jump(self):
        self._jump_yaw()

    # JUMPYAW = 10      # Jump yaw.     (should be after mode 1 FORCE_STAND 2s)
    def _jump_yaw(self):
        self.get_ready_to_move_when_standing()
        self.set_hcmd(MotorModeHigh.JUMPYAW, GaitType.TROT, self.DEFAULT_EULER, [0, 0], 0, 0, self.DEFAULT_BODY_HEIGHT)
        
        if self.collision_avoidance():
            self.send_hcmd()
            time.sleep(self.JUMP_YAW_SLEEP_TIME)
        else:
            print('To avoid collision, stopping')
    
    def lift(self):
        self._straight_hand() 

    # STRAIGHTHAND = 11 # StraightHand  (should be after mode 1 FORCE_STAND 2s)
    def _straight_hand(self):
        self.get_ready_to_move_when_standing()
        self.set_hcmd(MotorModeHigh.STRAIGHTHAND, GaitType.TROT, self.DEFAULT_EULER, [0, 0], 0, 0, self.DEFAULT_BODY_HEIGHT)
        
        if self.collision_avoidance():
            self.send_hcmd()
            time.sleep(self.STRAIGHT_HAND_SLEEP_TIME)
        else:
            print('To avoid collision, stopping')
    
    def first_dance(self):
        self._dance1()

    # DANCE1 = 12       # DANCE1        (should be after mode 1 FORCE_STAND 2s)
    def _dance1(self):
        self.get_ready_to_move_when_standing()
        self.set_hcmd(MotorModeHigh.DANCE1, GaitType.TROT, self.DEFAULT_EULER, [0, 0], 0, 0, self.DEFAULT_BODY_HEIGHT)
        
        if self.collision_avoidance():
            self.send_hcmd()
            time.sleep(self.DANCE1_SLEEP_TIME)
        else:
            print('To avoid collision, stopping')

    def second_dance(self):
        self._dance2()

    # DANCE2 = 13       # DANCE2        (should be after mode 1 FORCE_STAND 2s)
    def _dance2(self):
        self.get_ready_to_move_when_standing()
        self.set_hcmd(MotorModeHigh.DANCE2, GaitType.TROT, self.DEFAULT_EULER, [0, 0], 0, 0, self.DEFAULT_BODY_HEIGHT)
        
        if self.collision_avoidance():
            self.send_hcmd()
            time.sleep(self.DANCE2_SLEEP_TIME)
        else:
            print('To avoid collision, stopping')

    def find(self, object_to_find):
        self.get_ready_to_move_when_standing()
        yaw_speed = 0.25 
        if object_to_find in self.available_classes:
            sleep_time = self.SLEEP_TIME * (8 // yaw_speed)
            i = 0
            while i < sleep_time:
                for class_id, center in zip(self.class_ids, self.centers):
                    if class_id == self.available_classes.index(object_to_find):
                        if center[0] > 0.4 and center[0] < 0.6:
                            self.set_hcmd(MotorModeHigh.IDLE, GaitType.TROT, self.DEFAULT_EULER, [0, 0], 0, 0, self.DEFAULT_BODY_HEIGHT)
                            self.send_hcmd()
                            print(f"{object_to_find} found")
                            # return True
                            self.found_after_find = {object_to_find: True}
                            # self.found_after_find[object_to_find] = True
                            return 

                if self.collision_avoidance():
                    self.set_hcmd(MotorModeHigh.VEL_WALK, GaitType.TROT, self.DEFAULT_EULER, [0.01, 0.025], yaw_speed, self.DEFAULT_FOOT_RAISE_HEIGHT, self.DEFAULT_BODY_HEIGHT)
                    self.send_hcmd()
                    time.sleep(1)
                    i += 1
                else:
                    self.set_hcmd(MotorModeHigh.IDLE, GaitType.TROT, self.DEFAULT_EULER, [0, 0], 0, 0, self.DEFAULT_BODY_HEIGHT)
                    self.send_hcmd()
                    print('To avoid collision, stopping')
                    break
            print(f"{object_to_find} cannot be found")
        else:
            print(f"I don't know what {object_to_find} is")
            print(f"I know these objects: {self.available_classes}")
        # return False
        self.found_after_find = {object_to_find: False}
        # self.found_after_find[object_to_find] = False
        return  

    def execute_function_by_name(self, input_string):
        # Split the input string only once
        parts = input_string.split()
        function_name = parts[0]
        arguments = parts[1:]

        if hasattr(self, function_name):
            # Call the function and pass the arguments
            func = getattr(self, function_name)
            try:
                # self.tts(function_name)
                func(*arguments)
            except TypeError as e:
                print(f"Function {function_name} expects {func.__code__.co_argcount - 1} arguments, {len(arguments)} given")
        else:
            if '(' in function_name and function_name.endswith(')'):
                function_name, args_str = function_name.split('(')
                args = args_str.strip(')')

                if hasattr(self, function_name):
                    # Call the function and pass the arguments
                    func = getattr(self, function_name)
                    try:
                        # self.tts(function_name)
                        if args == '':
                            func()
                        else:
                            exec(f"self.{function_name}({args})")
                    except TypeError as e:
                        print(f"Function {function_name} expects {func.__code__.co_argcount - 1} arguments, {len(arguments)} given")
                else:
                    print(f"Function {function_name} not found")        
            else:
                print(f"Function {function_name} not found")
            
    def execute_statement(self, input_string):
        input_tokens = input_string.split()

        if input_tokens[0].lower() == 'repeat':
            if len(input_tokens) >= 3:
                try:
                    repetitions = int(input_tokens[1])
                    function_name_and_arguments = ' '.join(input_tokens[2:])
                    for _ in range(repetitions):
                        self.execute_function_by_name(function_name_and_arguments)
                except ValueError:
                    print(f"Invalid number of repetitions: {input_tokens[1]}") 
            else:
                print('Invalid number of arguments')
        else:
            self.execute_function_by_name(input_string)
    
    def check_simplified_syntax_validity(self, simplified_code):
        standard_code = HumanFriendlyPythonSyntaxConverter.to_standard_syntax(simplified_code, True) 
        
        try:
            parsed_code = ast.parse(standard_code)

            for node in ast.walk(parsed_code):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                    if isinstance(node.func.value, ast.Name) and node.func.value.id == 'self':
                        attr_name = node.func.attr
                        if not hasattr(self, attr_name):
                            print(f"Function {attr_name} not found")
                            return False
                    else:
                        print("Function call does not start with 'self.'")
                        return False
            return True
        except Exception as e:
            print(f"An error occurred: {e}")
            return False

    def execute_simplified_syntax(self, simplified_code):
        standard_code = HumanFriendlyPythonSyntaxConverter.to_standard_syntax(simplified_code, True) 

        try:
            exec(standard_code)
        except Exception as e:
            print(e)
            print(f"Invalid syntax: {simplified_code}")

class UserInputThread(threading.Thread):
    def __init__(self, go1):
        threading.Thread.__init__(self)
        self.go1 = go1

    def run(self):
        while True:
            user_input = input('Enter command: ')
            if user_input == 'exit':
                break
            # self.go1.execute_function_by_name(user_input)
            self.go1.execute_statement(user_input)

class UserSimpleInputThread(threading.Thread):
    def __init__(self, go1):
        threading.Thread.__init__(self)
        self.go1 = go1

    def run(self):
        while True:
            user_input = input('Enter command: ')
            if user_input == 'exit':
                break
            self.go1.execute_simplified_syntax(user_input)

if __name__ == '__main__':
    VIDEO_OUTPUT = True
    go1 = go1_highcommand(connection_settings=HIGH_WIFI_DEFAULTS)
    # user_input_thread = UserInputThread(go1)
    # user_input_thread.start()
    user_simple_input_thread = UserSimpleInputThread(go1)
    user_simple_input_thread.start()
#     simplified_code = """
# REPEAT 2 TIMES
#     MOVE_FORWARD
# IF FAR
#     MOVE_RIGHT
# IF LIGHT
#     TURN_RIGHT
# IF DARK
#     TURN_LEFT
# """.strip()
#     print("Simplified Python Code:")
#     print(simplified_code)
#     go1.execute_simplified_syntax(simplified_code)

    if VIDEO_OUTPUT:
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
