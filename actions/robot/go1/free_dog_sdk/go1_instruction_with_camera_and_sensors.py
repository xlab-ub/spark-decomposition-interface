# from ucl.common import byte_print, decode_version, decode_sn, getVoltage, lib_version
from ucl.highCmd import highCmd
from ucl.highState import highState
# from ucl.lowCmd import lowCmd
from ucl.unitreeConnection import unitreeConnection, HIGH_WIFI_DEFAULTS, HIGH_WIRED_DEFAULTS
from ucl.enums import MotorModeHigh, GaitType #, SpeedLevel
# from ucl.complex import motorCmd

from go1_camera import go1_camera
from go1_ultrasound import go1_ultrasound

import cv2

import math 
import threading 
import time

ULTRASOUND_PORT = 12345

# print(f'Running lib version: {lib_version()}')

class go1_highcommand:
    BATTERY_STOP_TEMP = 50
    MCU_STOP_TEMP = 50
    SLEEP_TIME = 1 
    FACE_STOP_DISTANCE = 0.3
    LEFT_STOP_DISTANCE = 0.3
    RIGHT_STOP_DISTANCE = 0.3

    def __init__(self, connection_settings=HIGH_WIRED_DEFAULTS, camera_id=1, ultrasound_port=ULTRASOUND_PORT, debug=False):
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
        self.go1_camera_module = go1_camera(camera_id, WIFI=WIFI, IpLastSegment=int(local_ip[-1]), main_thread=False)
        self.available_classes = self.go1_camera_module.get_classes()
        print(self.available_classes)
        self.camera_data_generator = self.go1_camera_module.run()
        threading.Thread(target=self.get_camera_data).start()
        print('Camera loaded')

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
        while True:
            self.boxes, self.confidences, self.class_ids, self.centers, self.frame = next(self.camera_data_generator)
            # if self.frame is not None:
            #     cv2.imshow("video0", self.frame)
            #     if cv2.waitKey(1) & 0xFF == ord('q'):
            #         break
        # print(self.boxes, self.confidences, self.class_ids, self.centers)
    
    def get_frame(self):
        return self.frame

    def get_ultrasound_data(self):
        while True:
            self.distance_from_face, self.distance_from_left, self.distance_from_right = next(self.ultrasound_data_generator)
        # print(self.distance_from_face, self.distance_from_left, self.distance_from_right)

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
    
    def move_simple(self):
        self.set_hcmd(MotorModeHigh.STAND_UP, GaitType.TROT, [0, 0, 0], [0, 0], 0, 0, 0.1)
        self.send_hcmd()
        time.sleep(0.5)
        i = 0
        while i < 2:
            if (self.distance_from_face == 0 or self.distance_from_face > self.FACE_STOP_DISTANCE) and (self.distance_from_left == 0 or self.distance_from_left > self.LEFT_STOP_DISTANCE) and (self.distance_from_right == 0 or self.distance_from_right > self.RIGHT_STOP_DISTANCE): 
                self.set_hcmd(MotorModeHigh.VEL_WALK, GaitType.TROT, [0, 0, 0], [0.1, 0], 0, 0, 0.1)
                self.send_hcmd()
                time.sleep(self.SLEEP_TIME) 
                i += 1
            else:
                print('To avoid collision, stopping')
                return
    
    def stand_up_simple(self):
        if (self.distance_from_face == 0 or self.distance_from_face > self.FACE_STOP_DISTANCE) and (self.distance_from_left == 0 or self.distance_from_left > self.LEFT_STOP_DISTANCE) and (self.distance_from_right == 0 or self.distance_from_right > self.RIGHT_STOP_DISTANCE): 
            self.set_hcmd(MotorModeHigh.STAND_UP, GaitType.TROT, [0, 0, 0], [0, 0], 0, 0, 0.1)
            self.send_hcmd()
            time.sleep(self.SLEEP_TIME) 
        else:
            print('To avoid collision, stopping')
    
    def stand_down_simple(self):
        if (self.distance_from_face == 0 or self.distance_from_face > self.FACE_STOP_DISTANCE) and (self.distance_from_left == 0 or self.distance_from_left > self.LEFT_STOP_DISTANCE) and (self.distance_from_right == 0 or self.distance_from_right > self.RIGHT_STOP_DISTANCE): 
            self.set_hcmd(MotorModeHigh.STAND_DOWN, GaitType.TROT, [0, 0, 0], [0, 0], 0, 0, 0.1)
            self.send_hcmd()
            time.sleep(self.SLEEP_TIME)
        else:
            print('To avoid collision, stopping')
    
    def damping_simple(self):
        if (self.distance_from_face == 0 or self.distance_from_face > self.FACE_STOP_DISTANCE) and (self.distance_from_left == 0 or self.distance_from_left > self.LEFT_STOP_DISTANCE) and (self.distance_from_right == 0 or self.distance_from_right > self.RIGHT_STOP_DISTANCE): 
            self.set_hcmd(MotorModeHigh.DAMPING, GaitType.TROT, [0, 0, 0], [0, 0], 0, 0, 0.1)
            self.send_hcmd()
            time.sleep(self.SLEEP_TIME) 
        else:
            print('To avoid collision, stopping')
    
    def force_stand(self):
        self.set_hcmd(MotorModeHigh.FORCE_STAND, GaitType.TROT, [0, 0, 0], [0, 0], 0, 0, 0.1)
        self.send_hcmd()
        time.sleep(self.SLEEP_TIME)
    
    def idle(self):
        self.set_hcmd(MotorModeHigh.IDLE, GaitType.TROT, [0, 0, 0], [0, 0], 0, 0, 0.1)
        self.send_hcmd()
        time.sleep(self.SLEEP_TIME)
    
    def turn_intermediate(self, angle=90):
        yawSpeed = angle / 90 * 2 
        if yawSpeed > 0:
            self.set_hcmd(MotorModeHigh.VEL_WALK, GaitType.TROT, [0, 0, 0], [0.04, 0.1], yawSpeed, 0, 0.1)
        else:
            self.set_hcmd(MotorModeHigh.VEL_WALK, GaitType.TROT, [0, 0, 0], [0.1, 0.04], yawSpeed, 0, 0.1)
        
        if (self.distance_from_face == 0 or self.distance_from_face > self.FACE_STOP_DISTANCE) and (self.distance_from_left == 0 or self.distance_from_left > self.LEFT_STOP_DISTANCE) and (self.distance_from_right == 0 or self.distance_from_right > self.RIGHT_STOP_DISTANCE): 
            self.send_hcmd()
            time.sleep(self.SLEEP_TIME * yawSpeed)
        else:
            print('To avoid collision, stopping')

    def turn_simple(self, yawSpeed=2):
        if yawSpeed > 0:
            self.set_hcmd(MotorModeHigh.VEL_WALK, GaitType.TROT, [0, 0, 0], [0.04, 0.1], yawSpeed, 0, 0.1)
        else:
            self.set_hcmd(MotorModeHigh.VEL_WALK, GaitType.TROT, [0, 0, 0], [0.1, 0.04], yawSpeed, 0, 0.1)
        
        if (self.distance_from_face == 0 or self.distance_from_face > self.FACE_STOP_DISTANCE) and (self.distance_from_left == 0 or self.distance_from_left > self.LEFT_STOP_DISTANCE) and (self.distance_from_right == 0 or self.distance_from_right > self.RIGHT_STOP_DISTANCE): 
            self.send_hcmd()
        
            sleep_time = self.SLEEP_TIME * math.ceil(abs(yawSpeed)) 
            i = 0
            while i < sleep_time:
                if (self.distance_from_face == 0 or self.distance_from_face > self.FACE_STOP_DISTANCE) and (self.distance_from_left == 0 or self.distance_from_left > self.LEFT_STOP_DISTANCE) and (self.distance_from_right == 0 or self.distance_from_right > self.RIGHT_STOP_DISTANCE): 
                    time.sleep(1)
                    i += 1
                else:
                    self.set_hcmd(MotorModeHigh.IDLE, GaitType.TROT, [0, 0, 0], [0, 0], 0, 0, 0.1)
                    self.send_hcmd()
                    print('To avoid collision, stopping')
                    break
                # time.sleep(self.SLEEP_TIME * yawSpeed)
        else:
            print('To avoid collision, stopping')
    
    def turn_left_simple(self):
        self.turn_simple(2)
    
    def turn_right_simple(self):
        self.turn_simple(-2)
    
    # TODO: turn speed is too fast, need to slow down
    def find_object(self, object_to_find):
        yaw_speed = 0.25 
        if object_to_find in self.available_classes:
            self.set_hcmd(MotorModeHigh.VEL_WALK, GaitType.TROT, [0, 0, 0], [0.01, 0.025], yaw_speed, 0, 0.1)

            sleep_time = self.SLEEP_TIME * (8 // yaw_speed)
            i = 0
            while i < sleep_time:
                for class_id, center in zip(self.class_ids, self.centers):
                    if class_id == self.available_classes.index(object_to_find):
                        if center[0] > 0.4 and center[0] < 0.6:
                            self.set_hcmd(MotorModeHigh.IDLE, GaitType.TROT, [0, 0, 0], [0, 0], 0, 0, 0.1)
                            self.send_hcmd()
                            print(f"{object_to_find} found")
                            return True

                if (self.distance_from_face == 0 or self.distance_from_face > self.FACE_STOP_DISTANCE) and (self.distance_from_left == 0 or self.distance_from_left > self.LEFT_STOP_DISTANCE) and (self.distance_from_right == 0 or self.distance_from_right > self.RIGHT_STOP_DISTANCE): 
                    self.set_hcmd(MotorModeHigh.VEL_WALK, GaitType.TROT, [0, 0, 0], [0.01, 0.025], yaw_speed, 0, 0.1)
                    self.send_hcmd()
                    time.sleep(1)
                    i += 1
                else:
                    self.set_hcmd(MotorModeHigh.IDLE, GaitType.TROT, [0, 0, 0], [0, 0], 0, 0, 0.1)
                    self.send_hcmd()
                    print('To avoid collision, stopping')
                    break
            print(f"{object_to_find} cannot be found")
        else:
            print(f"I don't know what {object_to_find} is")
            print(f"I know these objects: {self.available_classes}")
        return False

    def execute_function_by_name(self, input_string):
        # Split the input string only once
        parts = input_string.split()
        function_name = parts[0]
        arguments = parts[1:]

        if hasattr(self, function_name):
            # Call the function and pass the arguments
            func = getattr(self, function_name)
            try:
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
            
class UserInputThread(threading.Thread):
    def __init__(self, go1):
        threading.Thread.__init__(self)
        self.go1 = go1

    def run(self):
        while True:
            user_input = input('Enter command: ')
            if user_input == 'exit':
                break
            self.go1.execute_function_by_name(user_input)


if __name__ == '__main__':
    go1 = go1_highcommand(connection_settings=HIGH_WIFI_DEFAULTS)
    user_input_thread = UserInputThread(go1)
    user_input_thread.start()

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
    # while True:
    #     user_input = input('Enter command: ')
    #     if user_input == 'exit':
    #         break
    #     go1.execute_function_by_name(user_input)
