import time, subprocess, io
from pathlib import Path
from threading import Condition

from picamera2.encoders import JpegEncoder
from picamera2.outputs import FileOutput
from picamera2.encoders import H264Encoder
from picamera2.outputs import FfmpegOutput


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
        from picamera2 import Picamera2
        self.picam = Picamera2()
        w, h = tuple(self.cfg["CAM_SIZE"])
        self.video_cfg = self.picam.create_video_configuration(main={"size": (w, h)})
        self.picam.configure(self.video_cfg)
        
        # Start recording immediately
        encoder = JpegEncoder(q=self.cfg["JPEG_Q"])
        self.picam.start_recording(encoder, FileOutput(self.buffer))
        self.streaming = True

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

    def snapshot_bytes(self) -> bytes | None:
        """Get current frame from buffer"""
        with self.buffer.condition:
            return self.buffer.frame

    def record_clip(self, seconds, path):
        """Record a short clip using rpicam-vid (like working script)"""
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

