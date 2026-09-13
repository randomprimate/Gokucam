import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Storage
SNAP_DIR = Path(os.getenv("GOKU_SNAP_DIR", str(BASE_DIR / "captures")))
SNAP_DIR.mkdir(parents=True, exist_ok=True)

# Camera
CAM_SIZE = tuple(map(int, os.getenv("GOKU_CAM_SIZE", "960,540").split(",")))
JPEG_Q   = int(os.getenv("GOKU_JPEG_Q", "75"))
FPS      = int(os.getenv("GOKU_FPS", "10"))

# Servo ports on SunFounder HAT
PAN_PORT  = os.getenv("GOKU_PAN_PORT", "P0")
TILT_PORT = os.getenv("GOKU_TILT_PORT", "P1")

# Angle limits
PAN_MIN, PAN_MAX   = map(int, os.getenv("GOKU_PAN_RANGE", "-90,90").split(","))
TILT_MIN, TILT_MAX = map(int, os.getenv("GOKU_TILT_RANGE", "-60,60").split(","))

# UI step & keepalive
STEP_DEG = int(os.getenv("GOKU_STEP", "8"))
SERVO_KEEPALIVE_SEC = int(os.getenv("GOKU_KEEPALIVE", "2"))  # 0 = disable

# Reliability / dev mode
# Set GOKU_MOCK_HARDWARE=1 to run without a real camera or Robot HAT
# (synthetic stream, no-op servos) — for developing off the Pi.
MOCK_HARDWARE = os.getenv("GOKU_MOCK_HARDWARE", "0").lower() in ("1", "true", "yes", "on")

# Camera self-healing: how often to check the stream, and how stale a
# frame has to be before we consider it hung and restart the session.
CAM_WATCHDOG_SEC = int(os.getenv("GOKU_CAM_WATCHDOG_SEC", "5"))
CAM_STALE_SEC    = int(os.getenv("GOKU_CAM_STALE_SEC", "8"))

# Server
HOST = os.getenv("GOKU_HOST", "0.0.0.0")
PORT = int(os.getenv("GOKU_PORT", "8000"))

# Auth (login portal)
SECRET_KEY = os.getenv("GOKU_SECRET_KEY")
PORTAL_USERNAME = os.getenv("GOKU_PORTAL_USERNAME", "goku")
PORTAL_PASSWORD_HASH = os.getenv("GOKU_PORTAL_PASSWORD_HASH")
SESSION_LIFETIME_MIN = int(os.getenv("GOKU_SESSION_LIFETIME_MIN", "720"))  # 12h
LOGIN_MAX_ATTEMPTS = int(os.getenv("GOKU_LOGIN_MAX_ATTEMPTS", "5"))
LOGIN_WINDOW_SEC = int(os.getenv("GOKU_LOGIN_WINDOW_SEC", "300"))  # 5 min

# Dev-only fallback credentials, used solely when MOCK_HARDWARE=1 and no
# real credentials are configured — never used outside mock mode.
DEV_DEFAULT_USERNAME = "goku"
DEV_DEFAULT_PASSWORD = "shellyeah"

# Biomarker datastore + scheduled capture
DB_PATH = Path(os.getenv("GOKU_DB_PATH", str(BASE_DIR / "gokucam.db")))
# float (not int) so tests/dev can use fractional minutes (e.g. "0.1") for a fast interval
SNAPSHOT_INTERVAL_MIN = float(os.getenv("GOKU_SNAPSHOT_INTERVAL_MIN", "60"))

# AI insights (Claude health checks + caption drafting)
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
AI_MOCK = os.getenv("GOKU_AI_MOCK", "0").lower() in ("1", "true", "yes", "on")
AI_HEALTH_MODEL = os.getenv("GOKU_AI_HEALTH_MODEL", "claude-haiku-4-5-20251001")
AI_CAPTION_MODEL = os.getenv("GOKU_AI_CAPTION_MODEL", "claude-sonnet-5")
# All intervals as floats (hours/days) so tests can use fractional values for fast cycles
AI_HEALTHCHECK_INTERVAL_HOURS = float(os.getenv("GOKU_AI_HEALTHCHECK_INTERVAL_HOURS", "24"))
AI_ROUNDUP_INTERVAL_DAYS = float(os.getenv("GOKU_AI_ROUNDUP_INTERVAL_DAYS", "7"))
AI_HIGHLIGHT_INTERVAL_DAYS = float(os.getenv("GOKU_AI_HIGHLIGHT_INTERVAL_DAYS", "3"))
AI_MAX_CALLS_PER_DAY = int(os.getenv("GOKU_AI_MAX_CALLS_PER_DAY", "10"))
AI_MAX_IMAGE_DIM = int(os.getenv("GOKU_AI_MAX_IMAGE_DIM", "800"))
