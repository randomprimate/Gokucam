import time, subprocess
from pathlib import Path
from threading import Lock, Condition
import io

from picamera2 import Picamera2
from picamera2.encoders import JpegEncoder
from picamera2.outputs import FileOutput

class _Buffer(io.BufferedIOBase):
    def __init__(self):
        super().__init__()
        self.frame = None
        self.cv = Condition()
    def write(self, b):
        with self.cv:
            self.frame = b
            self.cv.notify_all()

class Camera:
    def __init__(self, cfg):
        self.cfg = cfg
        self.picam = Picamera2()
        self.video_cfg = self.picam.create_video_configuration(
            main={"size": tuple(cfg["CAM_SIZE"])}
        )
        self.picam.configure(self.video_cfg)
        self.buffer = _Buffer()
        self.lock = Lock()
        self.streaming = False
        self.start_stream()

    def start_stream(self):
        if self.streaming: return
        self.picam.start_recording(JpegEncoder(q=self.cfg["JPEG_Q"]), FileOutput(self.buffer))
        self.streaming = True

    def stop_stream(self):
        if not self.streaming: 
            try: self.picam.stop()
            except Exception: pass
            return
        try:
            self.picam.stop_recording()
        except Exception:
            pass
        try:
            self.picam.stop()
        except Exception:
            pass
        self.streaming = False

    def mjpeg_frames(self):
        boundary = b'--frame'
        while True:
            with self.buffer.cv:
                self.buffer.cv.wait()
                frame = self.buffer.frame
            if frame is None: 
                continue
            yield (boundary + b'\r\nContent-Type: image/jpeg\r\nContent-Length: ' +
                   str(len(frame)).encode() + b'\r\n\r\n' + frame + b'\r\n')

    def snapshot_bytes(self) -> bytes | None:
        with self.buffer.cv:
            self.buffer.cv.wait(timeout=1.0)
            return self.buffer.frame

    def record_clip(self, mode: str, secs: int, out_path: Path):
        """Pause MJPEG → rpicam-vid → resume."""
        presets = dict(social=self.cfg["SOCIAL"], archival=self.cfg["ARCHIVAL"])
        preset = presets.get(mode, self.cfg["ARCHIVAL"])
        w, h = preset["size"]
        fps  = preset["fps"]
        br   = preset["bitrate"]
        rot  = preset["rotation"]

        with self.lock:
            # fully release camera
            self.stop_stream()
            time.sleep(0.35)

            cmd = ["rpicam-vid","--nopreview",
                   "--width", str(w), "--height", str(h),
                   "--framerate", str(fps), "--bitrate", str(br),
                   "-t", str(secs*1000), "-o", str(out_path)]
            if rot:
                cmd[1:1] = ["--rotation", str(rot)]
            try:
                subprocess.run(cmd, check=True)
            finally:
                # reconfigure & resume stream
                self.picam.configure(self.video_cfg)
                self.start_stream()
