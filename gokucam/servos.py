import time, threading
from .utils import clamp

try:
    from robot_hat import Servo
except Exception as e:
    raise SystemExit(f"robot-hat missing: {e}")

class Servos:
    def __init__(self, cfg):
        self.cfg = cfg
        self.pan  = Servo(cfg["PAN_PORT"])
        self.tilt = Servo(cfg["TILT_PORT"])
        self.state = {"pan": 0.0, "tilt": 0.0}
        self.set_pan(0); self.set_tilt(0); time.sleep(0.2)

        keep = cfg["SERVO_KEEPALIVE_SEC"]
        if keep > 0:
            t = threading.Thread(target=self._keepalive, args=(keep,), daemon=True)
            t.start()

    def set_pan(self, angle: float) -> float:
        a = clamp(angle, self.cfg["PAN_MIN"], self.cfg["PAN_MAX"])
        self.pan.angle(a); self.state["pan"] = a; return a

    def set_tilt(self, angle: float) -> float:
        a = clamp(angle, self.cfg["TILT_MIN"], self.cfg["TILT_MAX"])
        self.tilt.angle(a); self.state["tilt"] = a; return a

    def center(self):
        self.set_pan(0); self.set_tilt(0)

    def _keepalive(self, period: int):
        while True:
            time.sleep(period)
            self.pan.angle(self.state["pan"])
            self.tilt.angle(self.state["tilt"])
