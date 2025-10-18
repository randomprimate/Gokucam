import os

# Servo Configuration
PAN_PORT = os.getenv("GOKU_PAN_PORT", "P0")
TILT_PORT = os.getenv("GOKU_TILT_PORT", "P1")

# Angle limits (robot_hat.Servo uses -90..90 by default)
PAN_MIN, PAN_MAX = -90, 90
TILT_MIN, TILT_MAX = -60, 60  # protect the ribbon: narrower tilt range is safer

# Step size for keyboard/arrow controls
STEP_DEG = 10

# Camera Configuration
CAMERA_SIZE = (1280, 720)
JPEG_QUALITY = 85
FPS = 25

# File paths
SNAP_DIR = "./captures"
os.makedirs(SNAP_DIR, exist_ok=True)
