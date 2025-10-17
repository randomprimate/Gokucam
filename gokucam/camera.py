import time, subprocess, io
from pathlib import Path
from threading import Lock, Condition

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
        self.last_frame_time = time.time()
        self.frame_count = 0

        # create & configure the camera object
        self._create_picam()
        self.start_stream()

    def _make_h264_encoder(self, bitrate: int):
        try:
            return H264Encoder(bitrate=bitrate)
        except TypeError:
            enc = H264Encoder()
            try:
                enc.bitrate = bitrate
            except Exception:
                pass
            return enc

    def _make_ffmpeg_output(self, path, fps: int):
        try:
            return FfmpegOutput(str(path), framerate=fps)
        except TypeError:
            try:
                return FfmpegOutput(str(path), audio=False)
            except TypeError:
                return FfmpegOutput(str(path))


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
            if hasattr(self, 'picam') and self.picam is not None:
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
                self.picam = None
                self.streaming = False
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
    
    def restart_stream(self):
        """Force restart the camera stream - useful for recovery"""
        print("[CAMERA] Restarting stream...")
        self.stop_stream()
        self._close_picam()  # Properly close the camera device
        time.sleep(0.5)  # Give more time for device to be released
        self._create_picam()
        self.start_stream()
    
    def _restart_stream_safe(self):
        """Safely restart stream with error handling for automatic recovery"""
        try:
            self.stop_stream()
            self._close_picam()
            time.sleep(0.5)
            self._create_picam()
            self.start_stream()
            print("[CAMERA] Stream restarted successfully")
        except Exception as e:
            print(f"[CAMERA] Stream restart failed: {e}")
            # Try a more aggressive restart
            try:
                time.sleep(1.0)
                self._create_picam()
                self.start_stream()
                print("[CAMERA] Stream restarted on second attempt")
            except Exception as e2:
                print(f"[CAMERA] Second restart attempt failed: {e2}")
                # Last resort: just try to ensure streaming
                self.ensure_streaming()

    # ---------- producers ----------
    def mjpeg_frames(self):
        self.ensure_streaming()
        boundary = b'--frame'
        consecutive_none_frames = 0
        max_none_frames = 30  # Much higher threshold - only restart if truly broken
        consecutive_timeouts = 0
        max_timeouts = 10  # Much higher threshold
        
        while True:
            try:
                with self.buffer.cv:
                    # Longer timeout to avoid false positives
                    if not self.buffer.cv.wait(timeout=3.0):
                        consecutive_timeouts += 1
                        if consecutive_timeouts >= max_timeouts:
                            print("[CAMERA] Stream appears completely frozen, restarting...")
                            self._restart_stream_safe()
                            consecutive_timeouts = 0
                        continue
                    frame = self.buffer.frame
                
                if frame is None:
                    consecutive_none_frames += 1
                    if consecutive_none_frames >= max_none_frames:
                        print("[CAMERA] Stream producing no frames, restarting...")
                        self._restart_stream_safe()
                        consecutive_none_frames = 0
                    continue
                
                # Reset counters on successful frame
                consecutive_none_frames = 0
                consecutive_timeouts = 0
                self.last_frame_time = time.time()
                self.frame_count += 1
                
                yield (boundary + b'\r\nContent-Type: image/jpeg\r\nContent-Length: ' +
                       str(len(frame)).encode() + b'\r\n\r\n' + frame + b'\r\n')
                       
            except Exception as e:
                print(f"[CAMERA] Critical error in stream loop: {e}")
                # Only restart on critical errors, not minor hiccups
                self._restart_stream_safe()
                time.sleep(0.5)

    def snapshot_bytes(self) -> bytes | None:
        self.ensure_streaming()
        with self.buffer.cv:
            self.buffer.cv.wait(timeout=1.0)
            return self.buffer.frame

    # ---------- recording ----------
    def record_clip(self, secs: int, out_path: Path):
        """Record H.264 → MP4 in-process, without stopping MJPEG."""
        bitrate = int(self.cfg.get("BITRATE", 8_000_000))
        fps     = int(self.cfg.get("FPS", 25))

        encoder = self._make_h264_encoder(bitrate)
        output  = self._make_ffmpeg_output(out_path, fps)

        self.picam.start_encoder(encoder, output)
        try:
            time.sleep(secs)
        finally:
            self.picam.stop_encoder(encoder)

