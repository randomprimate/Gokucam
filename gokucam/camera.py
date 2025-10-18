import time, subprocess, io
from pathlib import Path
from threading import Condition

# Mock implementations for development
class MockPicamera2:
    def __init__(self):
        self.configured = False
        self.recording = False
    
    def create_video_configuration(self, main):
        return {"main": main}
    
    def configure(self, config):
        self.configured = True
    
    def start_recording(self, encoder, output):
        self.recording = True
        # Simulate writing frames to the output
        import threading
        def mock_frame_writer():
            while self.recording:
                time.sleep(0.1)  # ~10 FPS
                # Create a simple test pattern frame
                import io
                test_frame = b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c\x1c $.\' ",#\x1c\x1c(7),01444\x1f\'9=82<.342\xff\xc0\x00\x11\x08\x00\x10\x00\x10\x01\x01\x11\x00\x02\x11\x01\x03\x11\x01\xff\xc4\x00\x14\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x08\xff\xc4\x00\x14\x10\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xff\xda\x00\x0c\x03\x01\x00\x02\x11\x03\x11\x00\x3f\x00\xaa\xff\xd9'
                output.write(test_frame)
        threading.Thread(target=mock_frame_writer, daemon=True).start()
    
    def stop_recording(self):
        self.recording = False

class MockJpegEncoder:
    def __init__(self, q=85):
        self.q = q

class MockFileOutput:
    def __init__(self, buffer):
        self.buffer = buffer
    
    def write(self, data):
        self.buffer.write(data)

# Try to import real modules, fall back to mocks
try:
    from picamera2.encoders import JpegEncoder
    from picamera2.outputs import FileOutput
    from picamera2 import Picamera2
    REAL_CAMERA = True
except ImportError:
    print("[CAMERA] Using mock camera for development")
    JpegEncoder = MockJpegEncoder
    FileOutput = MockFileOutput
    Picamera2 = MockPicamera2
    REAL_CAMERA = False

try:
    from picamera2.encoders import H264Encoder
    from picamera2.outputs import FfmpegOutput
except ImportError:
    H264Encoder = None
    FfmpegOutput = None


class StreamingBuffer(io.BufferedIOBase):
    def __init__(self):
        super().__init__()
        self.frame = None
        self.condition = Condition()

    def write(self, b):
        with self.condition:
            self.frame = b
            self.condition.notify_all()

class Camera:
    def __init__(self, cfg):
        self.cfg = cfg
        self.buffer = StreamingBuffer()
        self.streaming = False

        # Simple camera setup like the working script
        self.picam = Picamera2()
        w, h = tuple(self.cfg["CAM_SIZE"])
        self.video_cfg = self.picam.create_video_configuration(main={"size": (w, h)})
        self.picam.configure(self.video_cfg)
        
        # Start recording immediately
        encoder = JpegEncoder(q=self.cfg["JPEG_Q"])
        self.picam.start_recording(encoder, FileOutput(self.buffer))
        self.streaming = True
        
        if not REAL_CAMERA:
            print("[CAMERA] Mock camera initialized - you'll see a test pattern")

    def stop_stream(self):
        """Stop the camera stream"""
        try:
            self.picam.stop_recording()
            self.streaming = False
        except Exception:
            pass

    def mjpeg_frames(self):
        """Generate MJPEG stream frames - simplified like working script"""
        boundary = b'--frame'
        while True:
            with self.buffer.condition:
                self.buffer.condition.wait()
                frame = self.buffer.frame
            if frame is None:
                continue
            yield (boundary + b'\r\nContent-Type: image/jpeg\r\nContent-Length: ' +
                   str(len(frame)).encode() + b'\r\n\r\n' + frame + b'\r\n')

    def snapshot_bytes(self):
        """Get current frame from buffer"""
        with self.buffer.condition:
            return self.buffer.frame

    def record_clip(self, seconds, path):
        """Record a short clip using rpicam-vid (like working script)"""
        if not REAL_CAMERA:
            print(f"[CAMERA] Mock recording {seconds}s to {path}")
            # Create a dummy file for testing
            Path(path).write_bytes(b"Mock video file")
            return
            
        print(f"[CAMERA] Recording {seconds}s to {path}")
        subprocess.run([
            "rpicam-vid",
            "--nopreview",
            "--width", str(self.cfg["CAM_SIZE"][0]),
            "--height", str(self.cfg["CAM_SIZE"][1]),
            "--framerate", str(self.cfg["FPS"]),
            "-t", str(seconds * 1000),
            "-o", str(path),
        ], check=False)
        print(f"[CAMERA] Recording saved to {path}")