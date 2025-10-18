import time
import platform

# Mock Servo class for development
class MockServo:
    def __init__(self, port):
        self.port = port
        self.angle_value = 0
        print(f"[MOCK SERVO] Created on {port}")

    def angle(self, value):
        self.angle_value = value
        print(f"[MOCK SERVO] {self.port} set to {value}°")

class Servos:
    def __init__(self, pan_port="P0", tilt_port="P1"):
        # Use mock implementations on non-Linux systems
        if platform.system() != "Linux":
            self.pan_servo = MockServo(pan_port)
            self.tilt_servo = MockServo(tilt_port)
            print("[MOCK] Using mock servos for development")
        else:
            try:
                from robot_hat import Servo
                self.pan_servo = Servo(pan_port)
                self.tilt_servo = Servo(tilt_port)
                print("[REAL] Using real servos")
            except ImportError:
                print("[MOCK] robot-hat not available, using mock servos")
                self.pan_servo = MockServo(pan_port)
                self.tilt_servo = MockServo(tilt_port)
        
        self.state = {"pan": 0, "tilt": 0}
        
        # Center servos on startup
        self.center()
        time.sleep(0.3)
    
    def clamp(self, val, lo, hi):
        return max(lo, min(hi, val))
    
    def set_pan(self, angle):
        a = self.clamp(angle, -90, 90)
        self.pan_servo.angle(a)
        self.state["pan"] = a
        return a
    
    def set_tilt(self, angle):
        a = self.clamp(angle, -60, 60)
        self.tilt_servo.angle(a)
        self.state["tilt"] = a
        return a
    
    def center(self):
        self.set_pan(0)
        self.set_tilt(0)
