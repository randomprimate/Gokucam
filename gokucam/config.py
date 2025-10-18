import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Storage
SNAP_DIR = Path(os.getenv("GOKU_SNAP_DIR", str(BASE_DIR / "captures")))
SNAP_DIR.mkdir(parents=True, exist_ok=True)

# Camera
CAM_SIZE = tuple(map(int, os.getenv("GOKU_CAM_SIZE", "1280,720").split(",")))
JPEG_Q   = int(os.getenv("GOKU_JPEG_Q", "85"))
FPS      = int(os.getenv("GOKU_FPS", "25"))

# Servo ports on SunFounder HAT
PAN_PORT  = os.getenv("GOKU_PAN_PORT", "P0")
TILT_PORT = os.getenv("GOKU_TILT_PORT", "P1")

# Angle limits
PAN_MIN, PAN_MAX   = map(int, os.getenv("GOKU_PAN_RANGE", "-90,90").split(","))
TILT_MIN, TILT_MAX = map(int, os.getenv("GOKU_TILT_RANGE", "-60,60").split(","))

# UI step & keepalive
STEP_DEG = int(os.getenv("GOKU_STEP", "8"))
SERVO_KEEPALIVE_SEC = int(os.getenv("GOKU_KEEPALIVE", "2"))  # 0 = disable

# Server
HOST = os.getenv("GOKU_HOST", "0.0.0.0")
PORT = int(os.getenv("GOKU_PORT", "8000"))
