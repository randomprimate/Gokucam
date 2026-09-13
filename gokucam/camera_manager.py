import io, threading, time, subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw

from .config import CAM_SIZE, JPEG_Q, FPS, SNAP_DIR, MOCK_HARDWARE, CAM_WATCHDOG_SEC, CAM_STALE_SEC

if not MOCK_HARDWARE:
    from picamera2 import Picamera2
    from picamera2.encoders import JpegEncoder, H264Encoder
    from picamera2.outputs import FileOutput
    try:
        from picamera2.outputs import FfmpegOutput
    except Exception:
        FfmpegOutput = None


class StreamingBuffer(io.BufferedIOBase):
    def __init__(self):
        super().__init__()
        self.frame: Optional[bytes] = None
        self.last_ts: float = 0.0
        self.cv = threading.Condition()

    def write(self, b: bytes):
        with self.cv:
            self.frame = b
            self.last_ts = time.time()
            self.cv.notify_all()


def _placeholder_jpeg(text: str) -> bytes:
    img = Image.new("RGB", CAM_SIZE, (17, 20, 16))
    d = ImageDraw.Draw(img)
    d.text((CAM_SIZE[0] // 2 - 90, CAM_SIZE[1] // 2 - 8), text, fill=(160, 90, 40))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=JPEG_Q)
    return buf.getvalue()


def _mock_frame() -> bytes:
    img = Image.new("RGB", CAM_SIZE, (20, 30, 24))
    d = ImageDraw.Draw(img)
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # PIL's default bitmap font only covers latin-1 — keep this ASCII-only.
    d.text((10, 10), "GOKU (mock feed - GOKU_MOCK_HARDWARE=1)", fill=(224, 138, 70))
    d.text((10, 30), ts, fill=(200, 200, 190))
    cx, cy = CAM_SIZE[0] // 2, CAM_SIZE[1] // 2
    d.ellipse([cx - 70, cy - 45, cx + 70, cy + 45], outline=(127, 180, 145), width=3)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=JPEG_Q)
    return buf.getvalue()


class CameraManager:
    """
    Owns the sensor. Provides:
      - start_mjpeg_stream() / stop_mjpeg_stream()
      - snapshot() from last MJPEG frame
      - record_mp4(seconds) with exclusive access (pauses MJPEG, records, resumes)

    Never raises out of __init__: if the camera isn't there (unplugged,
    not yet detected, running off-Pi), the manager comes up in a
    degraded state instead of taking the whole process down with it.
    A background watchdog keeps retrying init and restarts the stream
    if frames stop arriving.
    """
    def __init__(self):
        self._lock = threading.RLock()
        self.stream_buf = StreamingBuffer()
        self._streaming = False
        self._mock_thread: Optional[threading.Thread] = None
        self.backend = "mock" if MOCK_HARDWARE else "picamera2"
        self.picam = None
        self.available = False
        self._placeholder_cache = {}

        if self.backend == "mock":
            self.available = True
        else:
            self._init_camera()

        threading.Thread(target=self._watchdog_loop, daemon=True).start()

    # --- init / re-init ---
    def _init_camera(self):
        try:
            self.picam = Picamera2()
            self.picam.configure(self.picam.create_video_configuration(main={"size": CAM_SIZE}))
            self.available = True
            print("[CameraManager] camera initialized.")
        except Exception as e:
            print("[CameraManager] init failed, will keep retrying:", e)
            self.picam = None
            self.available = False

    # --- MJPEG live stream ---
    def start_mjpeg_stream(self):
        with self._lock:
            if self._streaming:
                return
            if self.backend == "mock":
                self._streaming = True
                self._mock_thread = threading.Thread(target=self._mock_stream_loop, daemon=True)
                self._mock_thread.start()
                return
            if not self.available:
                raise RuntimeError("camera not available")
            self.picam.start_recording(JpegEncoder(q=JPEG_Q), FileOutput(self.stream_buf))
            self._streaming = True

    def stop_mjpeg_stream(self):
        with self._lock:
            if not self._streaming:
                return
            self._streaming = False
            if self.backend == "mock":
                return
            try:
                self.picam.stop_recording()
            except Exception as e:
                print("[CameraManager] stop_recording failed:", e)

    def _mock_stream_loop(self):
        while self._streaming and self.backend == "mock":
            try:
                self.stream_buf.write(_mock_frame())
            except Exception as e:
                print("[CameraManager] mock frame generation failed:", e)
            time.sleep(max(1.0 / max(FPS, 1), 0.05))

    def mjpeg_generator(self):
        boundary = b'--frame'
        while True:
            with self.stream_buf.cv:
                self.stream_buf.cv.wait(timeout=CAM_WATCHDOG_SEC)
                frame = self.stream_buf.frame
                last_ts = self.stream_buf.last_ts

            fresh = bool(frame) and last_ts and (time.time() - last_ts) < CAM_STALE_SEC
            if fresh:
                out = frame
            else:
                key = "offline" if not self.available else "reconnecting"
                if key not in self._placeholder_cache:
                    text = "Camera offline" if not self.available else "Reconnecting..."
                    self._placeholder_cache[key] = _placeholder_jpeg(text)
                out = self._placeholder_cache[key]
                time.sleep(1)  # don't spin the placeholder faster than useful

            yield (boundary +
                   b'\r\nContent-Type: image/jpeg\r\nContent-Length: ' +
                   str(len(out)).encode() + b'\r\n\r\n' + out + b'\r\n')

    # --- self-healing ---
    def _watchdog_loop(self):
        while True:
            time.sleep(CAM_WATCHDOG_SEC)
            if self.backend == "mock":
                continue
            with self._lock:
                if not self.available:
                    self._init_camera()
                    continue
                if not self._streaming:
                    continue
                age = time.time() - self.stream_buf.last_ts if self.stream_buf.last_ts else None
                if age is not None and age > CAM_STALE_SEC:
                    print(f"[CameraManager] stream stale ({age:.1f}s) — restarting session.")
                    try:
                        self.picam.stop_recording()
                    except Exception as e:
                        print("[CameraManager] stop during restart failed:", e)
                    self._streaming = False
                    try:
                        self.picam.start_recording(JpegEncoder(q=JPEG_Q), FileOutput(self.stream_buf))
                        self._streaming = True
                    except Exception as e:
                        print("[CameraManager] restart failed, marking unavailable:", e)
                        self.available = False

    def is_healthy(self) -> bool:
        if self.backend == "mock":
            return True
        if not self.available:
            return False
        if not self._streaming:
            return True
        age = time.time() - self.stream_buf.last_ts if self.stream_buf.last_ts else None
        return age is None or age < CAM_STALE_SEC

    def status(self) -> dict:
        age = None
        if self.stream_buf.last_ts:
            age = round(time.time() - self.stream_buf.last_ts, 1)
        return {
            "backend": self.backend,
            "available": self.available,
            "streaming": self._streaming,
            "last_frame_age_sec": age,
        }

    # --- Snapshots / Recording ---
    def snapshot(self, out_dir: Path = SNAP_DIR) -> Path:
        name = datetime.now().strftime("%Y%m%d_%H%M%S") + ".jpg"
        path = out_dir / name
        with self.stream_buf.cv:
            frame = self.stream_buf.frame
        if not frame:
            raise RuntimeError("No MJPEG frame available")
        path.write_bytes(frame)
        return path

    def record_mp4(self, seconds: int, out_dir: Path = SNAP_DIR) -> Path:
        """
        Pause MJPEG, record H.264→MP4 for `seconds`, resume MJPEG.
        Prefers Picamera2+FFmpeg; falls back to rpicam-vid if needed.
        In mock mode, just stubs out a placeholder file so the gallery
        and downstream pipeline can be exercised off the Pi.
        """
        name = datetime.now().strftime("%Y%m%d_%H%M%S") + ".mp4"
        path = out_dir / name

        if self.backend == "mock":
            time.sleep(min(seconds, 2))  # don't actually block dev iteration for 10s
            path.write_bytes(b"GOKUCAM_MOCK_RECORDING")
            return path

        with self._lock:
            if not self.available:
                raise RuntimeError("camera not available")

            was_streaming = self._streaming
            if was_streaming:
                self.stop_mjpeg_stream()
                time.sleep(0.1)

            try:
                if FfmpegOutput is None:
                    raise RuntimeError("FfmpegOutput not available")

                enc = H264Encoder(bitrate=8_000_000)

                # Some builds only accept the filename; some accept audio kw.
                try:
                    out = FfmpegOutput(str(path))
                except TypeError:
                    out = FfmpegOutput(str(path), audio=False)

                self.picam.start_recording(enc, out)
                time.sleep(seconds)
                self.picam.stop_recording()

            except Exception as e:
                # Fallback to rpicam-vid CLI
                print("[CameraManager] FFmpeg path failed, fallback to rpicam-vid:", e)
                subprocess.run(
                    [
                        "rpicam-vid",
                        "--nopreview",
                        "--width", str(CAM_SIZE[0]),
                        "--height", str(CAM_SIZE[1]),
                        "--framerate", str(FPS),
                        "-t", str(seconds * 1000),
                        "-o", str(path),
                    ],
                    check=False,
                )

            finally:
                if was_streaming:
                    try:
                        self.start_mjpeg_stream()
                    except Exception as e2:
                        print("[CameraManager] Failed to restart MJPEG:", e2)

        return path

# singleton used by web app
camera = CameraManager()
