import time

# Mock servo for development
class MockServo:
    def __init__(self, port):
        self.port = port
        self.angle_value = 0
        print(f"[SERVOS] Mock servo created on {port}")
    
    def angle(self, value):
        self.angle_value = value
        print(f"[SERVOS] Mock {self.port} set to {value}°")

# Try to import real servo, fall back to mock
try:
    from robot_hat import Servo
    REAL_SERVOS = True
except ImportError:
    print("[SERVOS] Using mock servos for development")
    Servo = MockServo
    REAL_SERVOS = False


class Servos:
    def __init__(self, cfg):
        self.cfg = cfg
        self.pan_port = cfg.get("PAN_PORT", "P0")
        self.tilt_port = cfg.get("TILT_PORT", "P1")
        
        # Create servo instances directly like working script
        self.pan_servo = Servo(self.pan_port)
        self.tilt_servo = Servo(self.tilt_port)
        
        # Track state in memory
        self.state = {"pan": 0, "tilt": 0}
        
        # Center servos on startup
        self.center()
        time.sleep(0.3)  # Give time for servos to settle
        
        if not REAL_SERVOS:
            print("[SERVOS] Mock servos initialized")

    def clamp(self, val, lo, hi):
        """Clamp value between limits"""
        return max(lo, min(hi, val))

    def set_pan(self, angle):
        """Set pan angle directly like working script"""
        a = self.clamp(angle, self.cfg.get("PAN_MIN", -90), self.cfg.get("PAN_MAX", 90))
        self.pan_servo.angle(a)
        self.state["pan"] = a
        return a

    def set_tilt(self, angle):
        """Set tilt angle directly like working script"""
        a = self.clamp(angle, self.cfg.get("TILT_MIN", -60), self.cfg.get("TILT_MAX", 60))
        self.tilt_servo.angle(a)
        self.state["tilt"] = a
        return a

    def center(self):
        """Center both servos"""
        self.set_pan(0)
        self.set_tilt(0)