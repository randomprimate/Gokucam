## Why

Everything so far is live control (watch Goku, move the camera). None of it
produces the history that phases 4–5 need: to have Claude assess growth and
draft a caption, or to notice "no feeding logged in 3 days," there has to be
a durable record of snapshots, meals, and measurements over time — not just
loose files in `captures/`. Manual `/api/snapshot` clicks and a file listing
in `/gallery` don't add up to a growth record.

## What Changes

- A scheduled job takes a snapshot automatically on a fixed interval (not
  just on manual button press), and records it in a datastore instead of
  only as a loose file.
- Introduce a SQLite datastore (`gokucam/store.py`) as the system of record
  for snapshots, feeding-log entries, and measurements — loose files in
  `captures/` remain the actual image bytes, the database indexes and
  annotates them.
- A feeding-log form in the portal: food type, portion, optional note,
  timestamp — filled in by a person, not inferred from video (per the
  evaluation: far more reliable than trying to detect eating from footage).
- A photo-based measurement tool: click two points on any stored snapshot
  to get a length in centimeters, using a one-time pixel-per-cm calibration
  against a fixed physical reference marker in the enclosure. **Assumption
  (flagged, not yet confirmed by the user):** you've placed a small ruler or
  marked object at a fixed distance from the camera near the basking spot —
  automated shell detection/segmentation is out of scope here (see
  design.md `Non-Goals`); this phase measures whatever two points a person
  clicks.
- A simple biomarker dashboard page listing recent snapshots, feed-log
  entries, and measurements chronologically, so there's somewhere to look
  at the history phase 4 will later annotate.
- Move the datastore and `captures/` recommendation off the boot SD card is
  **documented**, not enforced in code — `GOKU_SNAP_DIR` and the new
  `GOKU_DB_PATH` are both already relocatable via env var from phase 1's
  and this phase's config.

## Capabilities

### New Capabilities
- `biomarkers`: scheduled snapshot capture, a durable datastore for
  snapshots/feeding/measurements, a feeding-log entry point, a
  calibrated photo-measurement tool, and a dashboard to view the history.

### Modified Capabilities
(none — the new dashboard/feeding-log/measurement routes are gated the same
way as every other route, expressed as a requirement within `biomarkers`
itself rather than editing `auth`'s existing route-by-route requirement
text)

## Impact

- New `gokucam/store.py`: SQLite schema + access functions for snapshots,
  feeding log, measurements, and calibration.
- New `gokucam/scheduler.py`: background thread taking snapshots on a
  configurable interval, writing them into the store (same threading style
  as the existing camera watchdog / servo keepalive — no new dependency).
- `gokucam/config.py`: `GOKU_DB_PATH`, `GOKU_SNAPSHOT_INTERVAL_MIN`.
- `gokucam/web.py`: new routes — feeding-log form + submit, measurement
  tool page + submit, biomarker dashboard — all `@auth.login_required`.
- New `gokucam/templates/biomarkers.html` (+ supporting partials/JS for the
  click-to-measure canvas tool).
- `run.py`: starts the scheduler alongside the existing camera/servo
  singletons.
- No new runtime dependency: Python's stdlib `sqlite3` covers the datastore.
