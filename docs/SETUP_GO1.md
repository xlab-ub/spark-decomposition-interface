# Unitree Go1 Robot Setup

The default configuration uses a **noop** robot backend that requires no hardware. This guide covers connecting a real Unitree Go1 Edu.

## Prerequisites

- Unitree Go1 Edu robot
- Network connection to the robot (Wi-Fi hotspot or wired LAN)
- Python environment with Spark dependencies installed

## Vendored SDK

The modified [free-dog-sdk](https://github.com/Bin4ry/free-dog-sdk) is included at `actions/robot/go1/free_dog_sdk/`. See `MODIFICATIONS.md` in that directory for Spark-specific changes.

Install SDK dependencies:

```bash
pip install -r actions/robot/go1/free_dog_sdk/requirements.txt
```

## Network configuration

Edit `actions/robot/go1/free_dog_sdk/ucl/unitreeConnection.py` and set your machine's IP addresses:

```python
local_ip_wifi = '<your-ip-on-robot-wifi>'   # e.g. when connected to Unitree hotspot
local_ip_eth = '<your-ip-on-wired-lan>'      # e.g. when connected via LAN cable
```

The robot uses standard Unitree network addresses (`addr_high`, `addr_low`, etc.). Refer to the [Unitree Go1 documentation](https://www.docs.quadruped.de/projects/go1/html/quick_start.html) for your connection method.

## Enable real robot

In `.env`:

```
SPARK_ROBOT_BACKEND=go1
SPARK_RASA_TEST=false
```

Restart `rasa run actions`.

## Optional peripherals

When using a real Go1, you may also enable:

| Feature | Config | Module |
|---------|--------|--------|
| Camera / object detection | Requires OpenCV + GStreamer | `optional/vision/` |
| Ultrasound sensors | Built into go1 backend | `actions/robot/go1/free_dog_sdk/go1_ultrasound.py` |
| Text-to-speech | `SPARK_TTS_ON=true` | `optional/tts/` |

These are not required for basic movement commands.

## Safety

- Always test new instructions with the noop backend first (`SPARK_ROBOT_BACKEND=noop`).
- Ensure adequate space around the robot before executing programs.
- The SDK includes temperature monitoring and collision avoidance when hardware sensors are available.
