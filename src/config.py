import os
from pathlib import Path

class Config:
    BASE_DIR = Path(__file__).resolve().parent.parent
    SNAP_DIR = Path(os.getenv("GOKU_SNAP_DIR", BASE_DIR / "captures"))
    SNAP_DIR.mkdir(parents=True, exist_ok=True)

    # Servo
    PAN_PORT  = os.getenv("GOKU_PAN_PORT",  "P0")
    TILT_PORT = os.getenv("GOKU_TILT_PORT", "P1")
    PAN_MIN, PAN_MAX   = -90, 90
    TILT_MIN, TILT_MAX = -60, 60
    STEP_DEG = 10
    SERVO_KEEPALIVE_SEC = int(os.getenv("GOKU_KEEPALIVE", "3"))  # 0 to disable

    # Camera
    CAM_SIZE = (1280, 720)  # (960,540) for RPi 3 if needed
    JPEG_Q   = 85

    # Recording presets
    SOCIAL   = dict(size=(1080, 1920), fps=30, bitrate=8_000_000, rotation=90)
    ARCHIVAL = dict(size=(1920, 1080), fps=25, bitrate=10_000_000, rotation=0)
