"""
Background snapshot scheduler — same sleep-loop-thread style as the
camera watchdog and servo keepalive, not a new scheduling dependency.
One job today (periodic snapshot); if a second cadence is ever needed
(e.g. phase 5's weekly/every-few-days posting jobs), that's the point to
reach for a real scheduler instead of growing this one ad hoc.
"""
import threading
import time

from .camera_manager import camera
from .config import SNAPSHOT_INTERVAL_MIN
from . import store


class SnapshotScheduler:
    def __init__(self):
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self):
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        print(f"[GokuCam][Scheduler] snapshot interval = {SNAPSHOT_INTERVAL_MIN} min")

    def stop(self):
        self._stop.set()

    def _loop(self):
        interval_sec = max(SNAPSHOT_INTERVAL_MIN, 0.01) * 60
        # Sleep in short steps so `stop()` is responsive and a short test
        # interval doesn't oversleep past its due time.
        step = max(0.5, min(interval_sec / 5, 5))
        elapsed = interval_sec  # capture immediately on startup
        while not self._stop.is_set():
            if elapsed >= interval_sec:
                self._capture_once()
                elapsed = 0
            time.sleep(step)
            elapsed += step

    def _capture_once(self):
        if not camera.is_healthy():
            print("[GokuCam][Scheduler] camera unavailable, skipping scheduled capture.")
            return
        try:
            path = camera.snapshot()
            store.record_snapshot(str(path), reason="scheduled")
        except Exception as e:
            print("[GokuCam][Scheduler] scheduled capture failed, will retry next interval:", e)


scheduler = SnapshotScheduler()
