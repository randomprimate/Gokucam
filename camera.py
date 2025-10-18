import io, threading, time
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

class Camera:
    def __init__(self, size=(1280, 720), quality=85):
        # Use mock implementations on non-Linux systems
        if platform.system() != "Linux":
            self.picam = MockPicamera2()
            self.buffer = StreamingBuffer()
            print("[MOCK] Using mock camera for development")
        else:
            try:
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
            except ImportError:
                print("[MOCK] picamera2 not available, using mock camera")
                self.picam = MockPicamera2()
                self.buffer = StreamingBuffer()
        
    def stop_recording(self):
        try:
            self.picam.stop_recording()
        except Exception:
            pass
