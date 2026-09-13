import threading, time
from .config import (
    PAN_MIN, PAN_MAX, TILT_MIN, TILT_MAX,
    PAN_PORT, TILT_PORT, SERVO_KEEPALIVE_SEC, MOCK_HARDWARE
)

try:
    from robot_hat import Servo as _RealServo
    _HARDWARE_IMPORT_OK = True
    _import_error = None
except Exception as e:
    _RealServo = None
    _HARDWARE_IMPORT_OK = False
    _import_error = e


class _MockServo:
    """Stand-in for robot_hat.Servo — accepts angle() calls, does nothing."""
    def __init__(self, port):
        self.port = port

    def angle(self, a):
        pass


def clamp(v, lo, hi): return max(lo, min(hi, v))


class ServoController:
    """
    Owns the pan/tilt servos. Never raises out of __init__: if the Robot
    HAT isn't reachable (not wired up, I2C hiccup, running off-Pi), we
    fall back to no-op mock servos instead of taking the whole process
    down with SystemExit. A background thread keeps retrying the real
    hardware and re-applies the last known angles once it's back.
    """
    def __init__(self):
        self._lock = threading.RLock()
        self._state = {"pan": 0, "tilt": 0}
        self.available = False
        self.backend = "mock" if (MOCK_HARDWARE or not _HARDWARE_IMPORT_OK) else "robot_hat"
        self.pan = None
        self.tilt = None

        if not _HARDWARE_IMPORT_OK and not MOCK_HARDWARE:
            print(f"[GokuCam][Servos][WARNING] robot_hat unavailable ({_import_error}); "
                  "running in degraded mock mode until hardware is reachable. "
                  "Set GOKU_MOCK_HARDWARE=1 to silence this on non-Pi dev machines.")

        self._init_hardware()
        print(f"[GokuCam][Servos] backend={self.backend} PAN_PORT={PAN_PORT}, TILT_PORT={TILT_PORT}")
        if PAN_PORT == TILT_PORT:
            print("[GokuCam][Servos][WARNING] PAN and TILT are using the SAME port! Set GOKU_PAN_PORT and GOKU_TILT_PORT differently.")

        self._apply(0, 0)
        if SERVO_KEEPALIVE_SEC > 0:
            t = threading.Thread(target=self._keepalive, daemon=True)
            t.start()

    def _init_hardware(self):
        try:
            servo_cls = _MockServo if self.backend == "mock" else _RealServo
            self.pan = servo_cls(PAN_PORT)
            self.tilt = servo_cls(TILT_PORT)
            self.available = True
        except Exception as e:
            print("[GokuCam][Servos] hardware init failed, will keep retrying:", e)
            self.pan = self.tilt = None
            self.available = False

    def _apply(self, pan_angle, tilt_angle):
        p = clamp(pan_angle, PAN_MIN, PAN_MAX)
        t = clamp(tilt_angle, TILT_MIN, TILT_MAX)
        if self.available:
            try:
                self.pan.angle(p)
                self.tilt.angle(t)
            except Exception as e:
                print("[GokuCam][Servos] apply failed, marking unavailable:", e)
                self.available = False
        self._state["pan"] = p
        self._state["tilt"] = t

    def set_pan(self, a):
        with self._lock:
            self._apply(a, self._state["tilt"])
            return dict(self._state)

    def set_tilt(self, a):
        with self._lock:
            self._apply(self._state["pan"], a)
            return dict(self._state)

    def step_pan(self, delta):
        with self._lock:
            return self.set_pan(self._state["pan"] + clamp(delta, -15, 15))

    def step_tilt(self, delta):
        with self._lock:
            return self.set_tilt(self._state["tilt"] + clamp(delta, -15, 15))

    def center(self):
        with self._lock:
            self._apply(0, 0)
            return dict(self._state)

    def sweep_demo(self):
        with self._lock:
            seq_pan  = [0, -45, -90, -45, 0, 45, 90, 45, 0]
            seq_tilt = [0, -20, -40, -20, 0, 20, 40, 20, 0]
        for a in seq_pan:
            self.set_pan(a); time.sleep(0.25)
        for a in seq_tilt:
            self.set_tilt(a); time.sleep(0.25)
        return dict(self._state)

    def state(self):
        with self._lock:
            return dict(self._state)

    def is_healthy(self) -> bool:
        return self.backend == "mock" or self.available

    def status(self) -> dict:
        with self._lock:
            return {"backend": self.backend, "available": self.available, **self._state}

    def _keepalive(self):
        while True:
            try:
                if self.backend != "mock" and not self.available:
                    self._init_hardware()
                    if self.available:
                        print("[GokuCam][Servos] hardware reconnected.")
                        with self._lock:
                            self._apply(self._state["pan"], self._state["tilt"])
                else:
                    with self._lock:
                        self.pan.angle(self._state["pan"])
                        self.tilt.angle(self._state["tilt"])
            except Exception as e:
                print("[servo keepalive]", e)
                self.available = False
            time.sleep(SERVO_KEEPALIVE_SEC)

# singleton used by web app
servos = ServoController()
