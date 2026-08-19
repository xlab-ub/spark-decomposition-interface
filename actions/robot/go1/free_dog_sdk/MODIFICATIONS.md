# Modifications to free-dog-sdk

This directory contains a vendored copy of [Bin4ry/free-dog-sdk](https://github.com/Bin4ry/free-dog-sdk) with Spark-specific extensions.

## Added files

- `go1_instruction_with_camera_and_sensors_and_sound.py` — high-level command interface with camera, ultrasound, and audio
- `go1_instruction_with_camera_and_sensors_and_sound_for_rasa_test.py` — no-hardware test stub
- `go1_camera.py`, `go1_ultrasound.py`, `go1_nano1_sound.py` — sensor and audio modules
- `human_friendly_python_syntax_converter.py` — human-friendly simplified syntax to Python converter
- Object-detection camera programs (`go1_image_receiving_program_*.py`)

## Configuration

Before connecting to a real Go1, edit `ucl/unitreeConnection.py` and set `local_ip_wifi` / `local_ip_eth` to match your machine's IP on the robot network. See `docs/SETUP_GO1.md`.
