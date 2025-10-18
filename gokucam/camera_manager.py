import io, threading, time
from datetime import datetime
from pathlib import Path
from typing import Optional

from picamera2 import Picamera2
from picamera2.encoders import JpegEncoder, H264Encoder
from picamera2.outputs import FileOutput

try:
    from picamera2.outputs import FfmpegOutput
except Exception:
    FfmpegOutput = None

from .config import CAM_SIZE, JPEG_Q, FPS, SNAP_DIR

class StreamingBuffer(io.BufferedIOBase):
    def __init__(self):
        super().__init__()
        self.frame: Optional[bytes] = None
        self.cv = threading.Condition()

    def write(self, b: bytes):
        with self.cv:
            self.frame = b
            self.cv.notify_all()

class CameraManager:
    """
    Owns the sensor. Provides:
      - start_mjpeg_stream() / stop_mjpeg_stream()
      - snapshot() from last MJPEG frame
      - record_mp4(seconds) with exclusive access (pauses MJPEG, records, resumes)
    """
    def __init__(self):
        self.picam = Picamera2()
        self.picam.configure(self.picam.create_video_configuration(main={"size": CAM_SIZE}))
        self.stream_buf = StreamingBuffer()
        self._streaming = False
        self._lock = threading.RLock()  # serialize ownership

    # --- MJPEG live stream ---
    def start_mjpeg_stream(self):
        with self._lock:
            if self._streaming:
                return
            self.picam.start_recording(JpegEncoder(q=JPEG_Q), FileOutput(self.stream_buf))
            self._streaming = True

    def stop_mjpeg_stream(self):
        with self._lock:
            if not self._streaming:
                return
            try:
                self.picam.stop_recording()
            finally:
                self._streaming = False

    def mjpeg_generator(self):
        boundary = b'--frame'
        while True:
            with self.stream_buf.cv:
                self.stream_buf.cv.wait()
                frame = self.stream_buf.frame
            if not frame:
                continue
            yield (boundary +
                   b'\r\nContent-Type: image/jpeg\r\nContent-Length: ' +
                   str(len(frame)).encode() + b'\r\n\r\n' + frame + b'\r\n')

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
        """
        name = datetime.now().strftime("%Y%m%d_%H%M%S") + ".mp4"
        path = out_dir / name

        with self._lock:
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
