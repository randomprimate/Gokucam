import time, subprocess, io
from pathlib import Path
from threading import Lock, Condition

from picamera2 import Picamera2
from picamera2.encoders import MJPEGEncoder, JpegEncoder
from picamera2.outputs import FileOutput
# add to imports at the top
from picamera2.encoders import H264Encoder
from picamera2.outputs import FfmpegOutput


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
        self.buffer = _Buffer()
        self.lock = Lock()
        self.streaming = False

        # create & configure the camera object
        self._create_picam()
        self.start_stream()

    def _create_picam(self):
        """Create a new Picamera2 instance and configure it."""
        from picamera2 import Picamera2  # local import to allow full close/recreate
        self.picam = Picamera2()
        w, h = tuple(self.cfg["CAM_SIZE"])
        self.video_cfg = self.picam.create_video_configuration(
            main={"size": (w, h), "format": "YUV420"}
        )
        self.picam.configure(self.video_cfg)

    def _close_picam(self):
        """Close Picamera2 completely to release the /dev/video node."""
        try:
            # stop recording if needed
            try:
                self.picam.stop_recording()
            except Exception:
                pass
            try:
                self.picam.stop()
            except Exception:
                pass
            # fully close the device
            self.picam.close()
        except Exception as e:
            print(f"[!] picam.close warn: {e}")

    # ---------- encoder helper (handles API differences) ----------
    def _make_mjpeg_encoder(self):
        q = int(self.cfg["JPEG_Q"])
        # Try quality=, then q=, then attribute/setter, finally fall back to JpegEncoder
        try:
            return MJPEGEncoder(quality=q)
        except TypeError:
            try:
                return MJPEGEncoder(q=q)
            except TypeError:
                try:
                    enc = MJPEGEncoder()
                    try:
                        enc.quality = q
                    except Exception:
                        try:
                            enc.set_quality(q)
                        except Exception:
                            pass
                    return enc
                except Exception:
                    # ultimate fallback: single-frame JPEG encoder also works for streaming
                    return JpegEncoder(q=q)

    # ---------- streaming control ----------
    def start_stream(self):
        if self.streaming:
            return
        encoder = self._make_mjpeg_encoder()
        self.picam.start_recording(encoder, FileOutput(self.buffer))
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

    def ensure_streaming(self):
        if not self.streaming:
            self.picam.configure(self.video_cfg)
            self.start_stream()

    # ---------- producers ----------
    def mjpeg_frames(self):
        self.ensure_streaming()
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
        self.ensure_streaming()
        with self.buffer.cv:
            self.buffer.cv.wait(timeout=1.0)
            return self.buffer.frame

    # ---------- recording ----------
    def record_clip(self, secs: int, out_path: Path):
        """Record H.264 → MP4 in-process, without stopping MJPEG."""
        bitrate = int(self.cfg.get("BITRATE", 8_000_000))
        fps = int(self.cfg.get("FPS", 25))

        encoder = H264Encoder(bitrate=bitrate)
        output = FfmpegOutput(str(out_path), framerate=fps)

        self.picam.start_encoder(encoder, output)
        try:
            time.sleep(secs)
        finally:
            self.picam.stop_encoder(encoder)

