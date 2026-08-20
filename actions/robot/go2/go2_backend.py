# Unitree Go2 backend, same command set as the verified test menus in
# ~/taegyu/Robot/Go2/go2_run.py (wired) and go2_run_wifi.py (Wi-Fi).
# SPARK_GO2_CONN selects the transport: "wired" = Ethernet DDS via the official
# unitree_sdk2py SportClient (+ VideoClient front camera), "wifi" = WebRTC via
# unitree_webrtc_connect (same api ids; camera not wired up yet).
# Tunables (SPARK_GO2_*) are read from the environment, see .env.example.

import ast
import json
import os
import threading
import time

import numpy as np

from robot.interface import RobotBackend
from robot.syntax import HumanFriendlyPythonSyntaxConverter
from robot.go2.function_library import function_library, condition_library


def detect_nic(subnet="192.168.123."):
    # Find the network interface holding an address on the robot subnet (wired).
    import socket, fcntl, struct
    for _, name in socket.if_nameindex():
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            ip = socket.inet_ntoa(fcntl.ioctl(s.fileno(), 0x8915, struct.pack("256s", name[:15].encode()))[20:24])
        except OSError:
            continue
        finally:
            s.close()
        if ip.startswith(subnet):
            return name
    raise RuntimeError(f"No interface with a {subnet}x address (check cable and PC IP 192.168.123.222, "
                       f"or set SPARK_GO2_IFACE; for Wi-Fi use SPARK_GO2_CONN=wifi)")


def find_robot():
    # Return the robot IP: wired main board if reachable, else the first host on
    # any PC subnet with port 9991 open, else None (AP mode). Same as go2_run_wifi.py.
    import socket, fcntl, struct
    from concurrent.futures import ThreadPoolExecutor

    def has_9991(ip):
        try:
            with socket.create_connection((ip, 9991), timeout=0.4):
                return ip
        except OSError:
            return None

    if has_9991("192.168.123.161"):
        return "192.168.123.161"
    my_ips = []
    for _, name in socket.if_nameindex():
        sk = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            ip = socket.inet_ntoa(fcntl.ioctl(sk.fileno(), 0x8915, struct.pack("256s", name[:15].encode()))[20:24])
        except OSError:
            continue
        finally:
            sk.close()
        if not ip.startswith(("127.", "169.254.", "172.17.", "100.")):
            my_ips.append(ip)
    with ThreadPoolExecutor(128) as ex:
        for my_ip in my_ips:
            base = my_ip.rsplit(".", 1)[0]
            for ip in ex.map(has_9991, [f"{base}.{i}" for i in range(1, 255)]):
                if ip and ip != my_ip:
                    return ip
    return None


class WebRTCSportClient:
    # SportClient-like wrapper over WebRTC so go2_highcommand below is identical
    # for both transports (from go2_run_wifi.py; only the commands used here).
    def __init__(self, ip=None):
        import asyncio
        self._asyncio = asyncio
        self.ip = ip
        self.loop = asyncio.new_event_loop()
        threading.Thread(target=self.loop.run_forever, daemon=True).start()
        self.timeout = 10.0

    def SetTimeout(self, t):
        self.timeout = t

    def _run(self, coro):
        return self._asyncio.run_coroutine_threadsafe(coro, self.loop).result(self.timeout)

    def Init(self):
        from unitree_webrtc_connect import UnitreeWebRTCConnection, WebRTCConnectionMethod, RTC_TOPIC

        async def _connect():
            key = os.environ.get("SPARK_GO2_AES_KEY") or os.environ.get("UNITREE_AES_128_KEY") or None  # firmware >= 1.1.15
            if self.ip:
                self.conn = UnitreeWebRTCConnection(WebRTCConnectionMethod.LocalSTA, ip=self.ip, aes_128_key=key)
            else:
                self.conn = UnitreeWebRTCConnection(WebRTCConnectionMethod.LocalAP, aes_128_key=key)
            await self.conn.connect()
            # sport commands need "normal" (or "mcf") motion mode, not "ai"
            r = await self.conn.datachannel.pub_sub.publish_request_new(RTC_TOPIC["MOTION_SWITCHER"], {"api_id": 1001})
            if r["data"]["header"]["status"]["code"] == 0 and json.loads(r["data"]["data"])["name"] not in ("normal", "mcf"):
                await self.conn.datachannel.pub_sub.publish_request_new(
                    RTC_TOPIC["MOTION_SWITCHER"], {"api_id": 1002, "parameter": {"name": "normal"}})
                await self._asyncio.sleep(5)

        self._run(_connect())

    def _call(self, name, parameter=None):
        # One-shot command: wait only briefly for the response. Some commands
        # (BalanceStand/RecoveryStand in mcf mode) send no response, so time out
        # cleanly instead of hanging the action thread (same as go2_run_wifi.py).
        from concurrent.futures import TimeoutError as FuturesTimeout
        from unitree_webrtc_connect import RTC_TOPIC, SPORT_CMD, SPORT_CMD_MCF
        cmd = {**SPORT_CMD, **SPORT_CMD_MCF}

        async def _req():
            req = {"api_id": cmd[name]}
            if parameter is not None:
                req["parameter"] = parameter
            r = await self._asyncio.wait_for(
                self.conn.datachannel.pub_sub.publish_request_new(RTC_TOPIC["SPORT_MOD"], req), 2.0)
            return r["data"]["header"]["status"]["code"]

        try:
            return self._asyncio.run_coroutine_threadsafe(_req(), self.loop).result(3.0)
        except (FuturesTimeout, self._asyncio.TimeoutError):
            return 0   # message was sent; response just didn't arrive

    def Move(self, vx, vy, vyaw): return self._call("Move", {"x": vx, "y": vy, "z": vyaw})
    def StopMove(self): return self._call("StopMove")
    def BalanceStand(self): return self._call("BalanceStand")
    def StandDown(self): return self._call("StandDown")
    def RecoveryStand(self): return self._call("RecoveryStand")
    def Sit(self): return self._call("Sit")
    def RiseSit(self): return self._call("RiseSit")
    def Hello(self): return self._call("Hello")
    def Stretch(self): return self._call("Stretch")
    def Dance1(self): return self._call("Dance1")


class go2_highcommand(RobotBackend):
    DEFAULT_VELOCITY = 0.3            # m/s, forward/backward
    DEFAULT_LATERAL_VELOCITY = 0.3    # m/s, left/right
    DEFAULT_YAW_SPEED = 0.5           # rad/s, turns

    MOVE_SLEEP_TIME = 2.0             # one MOVE_* step duration (firmware holds a Move ~1 s -> resend)
    TURN_SLEEP_TIME = 2.0             # one TURN_* step duration (~57 deg at 0.5 rad/s)
    MOVE_RESEND_TIME = 0.4

    BALANCE_STAND_SLEEP_TIME = 1
    STAND_DOWN_SLEEP_TIME = 2
    RECOVERY_STAND_SLEEP_TIME = 2
    HELLO_SLEEP_TIME = 4
    SIT_SLEEP_TIME = 3
    RISE_SIT_SLEEP_TIME = 3
    STRETCH_SLEEP_TIME = 8
    DANCE1_SLEEP_TIME = 20

    CAMERA_SLEEP_TIME = 0.1

    def __init__(self, connection_settings=None, audio=False):
        # Transport: wired (DDS SportClient) or wifi (WebRTC wrapper above).
        self.conn_mode = os.environ.get("SPARK_GO2_CONN", "wired").lower()
        if self.conn_mode == "wired":
            from unitree_sdk2py.core.channel import ChannelFactoryInitialize
            from unitree_sdk2py.go2.sport.sport_client import SportClient
            subnet = os.environ.get("SPARK_GO2_SUBNET", "192.168.123.")
            iface = connection_settings or os.environ.get("SPARK_GO2_IFACE") or detect_nic(subnet)
            print(f"[go2] wired: DDS on interface {iface}")
            ChannelFactoryInitialize(0, iface)
            self.sport_client = SportClient()
        elif self.conn_mode == "wifi":
            ip = connection_settings or os.environ.get("SPARK_GO2_IP") or find_robot()
            print(f"[go2] wifi: WebRTC to {ip or 'AP mode 192.168.12.1'}")
            self.sport_client = WebRTCSportClient(ip)
        else:
            raise RuntimeError(f"Unknown SPARK_GO2_CONN={self.conn_mode!r} (use 'wired' or 'wifi')")
        self.sport_client.SetTimeout(10.0)
        self.sport_client.Init()

        # Speed/duration overrides from .env (defaults = class constants above).
        self.velocity = float(os.environ.get("SPARK_GO2_VX", self.DEFAULT_VELOCITY))
        self.lateral_velocity = float(os.environ.get("SPARK_GO2_VY", self.DEFAULT_LATERAL_VELOCITY))
        self.yaw_speed = float(os.environ.get("SPARK_GO2_VYAW", self.DEFAULT_YAW_SPEED))
        self.move_seconds = float(os.environ.get("SPARK_GO2_MOVE_SECONDS", self.MOVE_SLEEP_TIME))
        self.turn_seconds = float(os.environ.get("SPARK_GO2_TURN_SECONDS", self.TURN_SLEEP_TIME))

        self.ready_to_move = False    # balanced standing, Move() accepted
        self.found_after_find = {}
        self.allowed_calls = {name.lower() for name in function_library} | {name.lower() for name in condition_library}

        self.frame = None
        self.frame_lock = threading.Lock()
        if os.environ.get("SPARK_GO2_CAMERA", "true").lower() in ("1", "true", "yes"):
            if self.conn_mode == "wired":
                threading.Thread(target=self.get_camera_data, daemon=True).start()
                print('Camera loaded')
            else:
                print('[go2] camera over wifi is not wired up yet (web stream shows a black frame)')

    def get_camera_data(self):
        # Front camera via DDS VideoClient (wired only), decoded to BGR.
        try:
            import cv2
            from unitree_sdk2py.go2.video.video_client import VideoClient
            video_client = VideoClient()
            video_client.SetTimeout(3.0)
            video_client.Init()
        except Exception as e:
            print(f"[go2] camera unavailable: {e}")
            return
        while True:
            code, data = video_client.GetImageSample()
            if code == 0:
                image = cv2.imdecode(np.frombuffer(bytes(data), dtype=np.uint8), cv2.IMREAD_COLOR)
                if image is not None:
                    with self.frame_lock:
                        self.frame = image
            time.sleep(self.CAMERA_SLEEP_TIME)

    def get_recognized_objects(self):
        return []

    def get_frame(self):
        # Never None: the web stream encodes this directly (black frame when no camera).
        with self.frame_lock:
            if self.frame is not None:
                return self.frame.copy()
        return np.zeros((360, 640, 3), np.uint8)

    def tts(self, text):
        return

    def get_ready_to_move_when_standing(self):
        # StandUp() locks the joints and Move() is ignored there, so balanced
        # standing (id 9 in the test menu) is required before any Move().
        if not self.ready_to_move:
            self.sport_client.BalanceStand()
            time.sleep(0.5)
            self.ready_to_move = True

    def _move(self, vx, vy, vyaw, seconds):
        # The firmware holds one Move() for ~1 s: resend until the step ends, then stop.
        self.get_ready_to_move_when_standing()
        t_end = time.monotonic() + seconds
        while time.monotonic() < t_end:
            ret = self.sport_client.Move(vx, vy, vyaw)
            if ret != 0:
                print(f"[go2] Move ret={ret} (need balanced standing?)")
                break
            time.sleep(self.MOVE_RESEND_TIME)
        self.sport_client.StopMove()

    def _trick(self, name, call, sleep_time):
        # Trick RPCs return before the motion ends: sleep so the next command does not interrupt it.
        self.get_ready_to_move_when_standing()
        ret = call()
        if ret not in (0, None):
            print(f"[go2] {name} ret={ret}")
        time.sleep(sleep_time)

    # Conditions for IF / WHILE. No perception is wired up yet on the real Go2,
    # so these stay False (a WHILE FAR loop then simply never runs).
    def far(self):
        return False

    def near(self):
        return False

    def found(self, object_to_find=None):
        if object_to_find in self.found_after_find:
            return self.found_after_find[object_to_find]
        return False

    def stand_down(self):
        self.sport_client.StandDown()
        time.sleep(self.STAND_DOWN_SLEEP_TIME)
        self.ready_to_move = False

    def stand_up(self):
        self.sport_client.BalanceStand()
        time.sleep(self.BALANCE_STAND_SLEEP_TIME)
        self.ready_to_move = True

    def recovery_stand(self):
        self.sport_client.RecoveryStand()
        time.sleep(self.RECOVERY_STAND_SLEEP_TIME)
        self.ready_to_move = True

    def stop(self):
        self.sport_client.StopMove()

    def move_forward(self):
        self._move(self.velocity, 0, 0, self.move_seconds)

    def move_backward(self):
        self._move(-self.velocity, 0, 0, self.move_seconds)

    def move_left(self):
        self._move(0, self.lateral_velocity, 0, self.move_seconds)

    def move_right(self):
        self._move(0, -self.lateral_velocity, 0, self.move_seconds)

    def turn_left(self):
        self._move(0, 0, self.yaw_speed, self.turn_seconds)

    def turn_right(self):
        self._move(0, 0, -self.yaw_speed, self.turn_seconds)

    def hello(self):
        self._trick('hello', self.sport_client.Hello, self.HELLO_SLEEP_TIME)

    def sit(self):
        self._trick('sit', self.sport_client.Sit, self.SIT_SLEEP_TIME)
        self.ready_to_move = False

    def rise_sit(self):
        self._trick('rise_sit', self.sport_client.RiseSit, self.RISE_SIT_SLEEP_TIME)
        self.ready_to_move = True

    def stretch(self):
        self._trick('stretch', self.sport_client.Stretch, self.STRETCH_SLEEP_TIME)

    def dance(self):
        self._trick('dance', self.sport_client.Dance1, self.DANCE1_SLEEP_TIME)

    def find(self, object_to_find=None):
        # Perception is not wired up yet: remember the target, found() stays False.
        self.found_after_find[object_to_find] = False
        print(f"[go2] FIND {object_to_find}: perception not wired yet")

    def check_simplified_syntax_validity(self, simplified_code):
        standard_code = HumanFriendlyPythonSyntaxConverter.to_standard_syntax(simplified_code, True)

        try:
            parsed_code = ast.parse(standard_code)

            for node in ast.walk(parsed_code):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                    if isinstance(node.func.value, ast.Name) and node.func.value.id == 'self':
                        attr_name = node.func.attr
                        # Vocabulary check instead of go1's hasattr: only actions from
                        # function_library (+ conditions) are callable commands.
                        if attr_name not in self.allowed_calls:
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


def create_go2_backend(connection_settings=None, audio=False):
    return go2_highcommand(connection_settings=connection_settings, audio=audio)


__all__ = ["create_go2_backend", "go2_highcommand", "WebRTCSportClient"]
