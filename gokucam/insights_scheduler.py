"""
Three background jobs, same sleep-loop-thread pattern as
gokucam/scheduler.py: a health check, and two caption-drafting cadences
(roundup, highlight). Each is independently timed; none of them ever
crashes the process — a failed Claude call just means skipping that
cycle and trying again next time.
"""
import threading
import time

from . import ai
from . import config
from . import store


def _sleep_loop(interval_sec: float, stop_event: threading.Event, job):
    step = max(0.5, min(interval_sec / 5, 5))
    elapsed = interval_sec  # run once shortly after startup
    while not stop_event.is_set():
        if elapsed >= interval_sec:
            try:
                job()
            except Exception as e:
                print(f"[GokuCam][Insights] job failed, will retry next interval: {e}")
            elapsed = 0
        time.sleep(step)
        elapsed += step


def _run_health_check():
    snap = store.latest_snapshot()
    if not snap:
        return  # nothing to assess yet — try again next interval
    try:
        image_bytes = ai.downscale_image(snap["path"])
        history = ai.build_history_summary()
        text = ai.call_claude(
            purpose="health_check",
            model=config.AI_HEALTH_MODEL,
            system_prompt=ai.build_health_prompt(),
            user_text=f"Recent history:\n{history}",
            image_bytes=image_bytes,
        )
    except (ai.AICallError, OSError) as e:
        print(f"[GokuCam][Insights] health check skipped: {e}")
        return
    concerning = ai.parse_concern_flag(text)
    store.record_health_note(snap["id"], summary=text, concerning=concerning, raw_response=text)
    if concerning:
        print("[GokuCam][Insights] health check flagged something concerning — see /biomarkers")


def _run_caption_draft(cadence: str):
    snap = store.latest_snapshot()
    if not snap:
        return
    try:
        image_bytes = ai.downscale_image(snap["path"])
        history = ai.build_history_summary()
        caption = ai.call_claude(
            purpose=f"caption_{cadence}",
            model=config.AI_CAPTION_MODEL,
            system_prompt=ai.build_caption_prompt(cadence),
            user_text=f"Recent history:\n{history}",
            image_bytes=image_bytes,
        )
    except (ai.AICallError, OSError) as e:
        print(f"[GokuCam][Insights] {cadence} draft skipped: {e}")
        return
    store.create_draft(snap["id"], cadence=cadence, caption=caption.strip())


class InsightsScheduler:
    def __init__(self):
        self._stop = threading.Event()
        self._threads = []

    def start(self):
        if self._threads:
            return
        jobs = [
            ("health check", config.AI_HEALTHCHECK_INTERVAL_HOURS * 3600, _run_health_check),
            ("roundup draft", config.AI_ROUNDUP_INTERVAL_DAYS * 86400, lambda: _run_caption_draft("roundup")),
            ("highlight draft", config.AI_HIGHLIGHT_INTERVAL_DAYS * 86400, lambda: _run_caption_draft("highlight")),
        ]
        for name, interval_sec, job in jobs:
            t = threading.Thread(target=_sleep_loop, args=(interval_sec, self._stop, job), daemon=True)
            t.start()
            self._threads.append(t)
            print(f"[GokuCam][Insights] {name} every {interval_sec / 3600:.2f}h")

    def stop(self):
        self._stop.set()


insights_scheduler = InsightsScheduler()
