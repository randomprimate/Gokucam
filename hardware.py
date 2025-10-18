import io, threading, time, os
import platform

# Mock implementations for development
class MockPicamera2:
    def create_video_configuration(self, main):
        return {"mock": True}
    
    def configure(self, config):
        pass
    
    def start_recording(self, encoder, output):
        pass
    
    def stop_recording(self):
        pass

class MockJpegEncoder:
    def __init__(self, q=85):
        self.quality = q

class MockFileOutput:
    def __init__(self, buffer):
        self.buffer = buffer

class MockServo:
    def __init__(self, port):
        self.port = port
        self.angle_value = 0
        print(f"[MOCK SERVO] Created on {port}")

    def angle(self, value):
        self.angle_value = value
        print(f"[MOCK SERVO] {self.port} set to {value}°")

class StreamingBuffer(io.BufferedIOBase):
    def __init__(self):
        super().__init__()
        self.frame = None
        self.condition = threading.Condition()
        self._start_mock_stream()

    def write(self, b):
        with self.condition:
            self.frame = b
            self.condition.notify_all()
    
    def _start_mock_stream(self):
        """Generate a simple test pattern for development"""
        def mock_frame_writer():
            import time
            import io
            from PIL import Image, ImageDraw
            
            while True:
                # Create a simple test pattern
                img = Image.new('RGB', (1280, 720), color=(100, 150, 200))
                draw = ImageDraw.Draw(img)
                
                # Add some moving elements
                t = time.time()
                x = int(640 + 200 * (t % 10) / 10)
                y = int(360 + 100 * (t % 7) / 7)
                
                draw.ellipse([x-50, y-50, x+50, y+50], fill=(255, 0, 0))
                draw.text((50, 50), f"Mock Camera - {int(t)}", fill=(255, 255, 255))
                
                # Convert to JPEG
                img_bytes = io.BytesIO()
                img.save(img_bytes, format='JPEG', quality=85)
                frame_data = img_bytes.getvalue()
                
                with self.condition:
                    self.frame = frame_data
                    self.condition.notify_all()
                
                time.sleep(0.1)  # ~10 FPS
        
        # Start mock stream in background
        threading.Thread(target=mock_frame_writer, daemon=True).start()

class Hardware:
    """Unified hardware controller for camera and servos"""
    
    def __init__(self, size=(1280, 720), quality=85, pan_port="P0", tilt_port="P1"):
        self.state = {"pan": 0, "tilt": 0}
        
        # Force real hardware if GOKU_FORCE_CAMERA=1
        force_camera = os.getenv("GOKU_FORCE_CAMERA", "0") == "1"
        use_real = platform.system() == "Linux" or force_camera
        
        if use_real:
            self._init_real_hardware(size, quality, pan_port, tilt_port)
        else:
            self._init_mock_hardware(size, quality, pan_port, tilt_port)
        
        # Center servos on startup
        self.center()
        time.sleep(0.3)
    
    def _init_real_hardware(self, size, quality, pan_port, tilt_port):
        """Initialize real camera and servos"""
        try:
            # Real camera
            from picamera2 import Picamera2
            from picamera2.encoders import JpegEncoder
            from picamera2.outputs import FileOutput
            
            self.picam = Picamera2()
            self.buffer = StreamingBuffer()
            
            # Configure camera
            video_cfg = self.picam.create_video_configuration(main={"size": size})
            self.picam.configure(video_cfg)
            
            # Start recording
            encoder = JpegEncoder(q=quality)
            self.picam.start_recording(encoder, FileOutput(self.buffer))
            print("[REAL] Using real camera")
            
            # Real servos
            from robot_hat import Servo
            self.pan_servo = Servo(pan_port)
            self.tilt_servo = Servo(tilt_port)
            print("[REAL] Using real servos")
            
        except Exception as e:
            print(f"[FALLBACK] Real hardware failed ({e}), using mocks")
            self._init_mock_hardware(size, quality, pan_port, tilt_port)
    
    def _init_mock_hardware(self, size, quality, pan_port, tilt_port):
        """Initialize mock camera and servos"""
        self.picam = MockPicamera2()
        self.buffer = StreamingBuffer()
        self.pan_servo = MockServo(pan_port)
        self.tilt_servo = MockServo(tilt_port)
        print("[MOCK] Using mock camera and servos for development")
    
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
    
    def stop_recording(self):
        try:
            self.picam.stop_recording()
        except Exception:
            pass
