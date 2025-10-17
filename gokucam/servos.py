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
        self.last_error = None

        # center on start
        self._safe_angle(self.pan,  0.0, key="pan")
        self._safe_angle(self.tilt, 0.0, key="tilt")
        time.sleep(0.2)

        keep = cfg["SERVO_KEEPALIVE_SEC"]
        print(f"[SERVOS] Keepalive period: {keep}s")
        if keep > 0:
            threading.Thread(target=self._keepalive, args=(keep,), daemon=True).start()
        else:
            print("[SERVOS] Keepalive disabled")

    def _safe_angle(self, servo, val, key):
        import traceback
        print("-------------------------")
        print("servo: ", servo)
        print("val: ", val)
        print("key: ", key)
        print("current state:", self.state)
        print("Call stack:")
        traceback.print_stack()
        try:
            self.state[key] = val  # Update state BEFORE calling servo
            servo.angle(val)
            self.last_error = None
            print(f"[SERVOS] Successfully set {key}={val}")
            return val
        except Exception as e:
            self.last_error = f"{key}: {e}"
            print(f"[SERVOS] Error setting {key}={val}: {e}")
            return self.state[key]

    def set_pan(self, angle: float) -> float:
        a = clamp(angle, self.cfg["PAN_MIN"], self.cfg["PAN_MAX"])
        return self._safe_angle(self.pan, a, "pan")

    def set_tilt(self, angle: float) -> float:
        a = clamp(angle, self.cfg["TILT_MIN"], self.cfg["TILT_MAX"])
        return self._safe_angle(self.tilt, a, "tilt")

    def center(self):
        self.set_pan(0); self.set_tilt(0)

    def _keepalive(self, period: int):
        print(f"[KEEPALIVE] Starting keepalive thread with {period}s period")
        while True:
            time.sleep(period)
            print(f"[KEEPALIVE] Running keepalive - current state: {self.state}")
            self._safe_angle(self.pan,  self.state["pan"],  "pan")
            self._safe_angle(self.tilt, self.state["tilt"], "tilt")
