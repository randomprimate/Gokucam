import threading, time
from .config import (
    PAN_MIN, PAN_MAX, TILT_MIN, TILT_MAX,
    PAN_PORT, TILT_PORT, SERVO_KEEPALIVE_SEC
)

try:
    from robot_hat import Servo
except Exception as e:
    raise SystemExit(
        f"robot-hat missing or not usable in this env: {e}\n"
        "Activate your venv or ensure SunFounder libs are installed."
    )

def clamp(v, lo, hi): return max(lo, min(hi, v))

class ServoController:
    def __init__(self):
        self.pan  = Servo(PAN_PORT)
        self.tilt = Servo(TILT_PORT)
        self._state = {"pan": 0, "tilt": 0}
        self._lock = threading.RLock()
        # center on start
        self._apply(0, 0)
        # keepalive thread
        if SERVO_KEEPALIVE_SEC > 0:
            t = threading.Thread(target=self._keepalive, daemon=True)
            t.start()

    def _apply(self, pan_angle, tilt_angle):
        self.pan.angle(clamp(pan_angle, PAN_MIN, PAN_MAX))
        self.tilt.angle(clamp(tilt_angle, TILT_MIN, TILT_MAX))
        self._state["pan"]  = clamp(pan_angle, PAN_MIN, PAN_MAX)
        self._state["tilt"] = clamp(tilt_angle, TILT_MIN, TILT_MAX)

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

    def _keepalive(self):
        while True:
            try:
                with self._lock:
                    self.pan.angle(self._state["pan"])
                    self.tilt.angle(self._state["tilt"])
            except Exception as e:
                print("[servo keepalive]", e)
            time.sleep(SERVO_KEEPALIVE_SEC)

# singleton used by web app
servos = ServoController()
