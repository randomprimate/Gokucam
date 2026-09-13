## Context

Phase 1 made camera/servo lifecycle resilient and added `GOKU_MOCK_HARDWARE`
for off-Pi dev; phase 2 put a login session in front of every route. This
phase is the first to introduce persistent state beyond loose files —
everything from here (phase 4's Claude analysis, phase 5's Instagram posts)
reads and writes the same store. See `proposal.md` for why; `specs/
biomarkers/spec.md` for the behavior contract.

## Goals / Non-Goals

**Goals:**
- A durable, queryable record of snapshots/feeding/measurements that
  survives process restarts and works identically under
  `GOKU_MOCK_HARDWARE=1`.
- No new runtime dependency.
- Keep the existing manual snapshot/gallery flow working unchanged.

**Non-Goals:**
- Automated shell detection or segmentation from images — measurement is a
  person clicking two points on a photo they're already looking at, not
  computer vision. If accuracy or effort here becomes a problem later,
  that's a follow-on change, not blocking this one.
- Environmental sensors (temperature/humidity) — the original roadmap
  flagged these as optional; skipped until there's a concrete need for them
  (e.g. Claude's analysis in phase 4 asking for temperature it can't infer
  from images).
- A charting library or fancy dashboard — a chronological list is enough to
  ship; visual trend charts are a cheap follow-on once there's enough data
  to chart.

## Decisions

**Datastore: SQLite via stdlib `sqlite3`, one file, `gokucam/store.py`.**
This is a single-writer, single-household device — SQLite's concurrency
model is a non-issue at this scale, and it's zero-install (stdlib) versus
adding Postgres or even a small ORM. `store.py` exposes plain functions
(`record_snapshot`, `log_feeding`, `record_measurement`, `get_calibration`,
`set_calibration`, `recent_history`) rather than an ORM layer — this app has
five simple tables, not a domain model that benefits from one.

**Schema (four tables):**
- `snapshots(id, path, captured_at, reason)` — `reason` is `'scheduled'` or
  `'manual'`.
- `feeding_log(id, food, portion, note, logged_at)`.
- `calibration(id, px_per_cm, established_at, snapshot_id)` — kept as a
  history, not a single overwritten value, so a camera repositioning
  doesn't silently corrupt old measurements: each measurement stores which
  calibration it used (see below).
- `measurements(id, snapshot_id, calibration_id, px_distance, cm_distance,
  measured_at)`.

**Scheduler: a background thread, same pattern as the phase-1 camera
watchdog — not APScheduler.** One interval, one job (take a snapshot,
record it). A sleep-loop thread matches the codebase's existing style
(`camera_manager.py`'s watchdog, `servo_controller.py`'s keepalive) and adds
no dependency. If phase 5 later needs cron-like multi-schedule behavior
(weekly + every-few-days posting jobs), that's the point to introduce a real
scheduler — one interval doesn't justify it yet.

**Calibration model: store `px_per_cm` per calibration event, reference it
from each measurement, don't drift-correct automatically.** Anyone can
recalibrate (re-run the two-point-plus-known-distance flow) whenever the
camera moves; measurements taken before that keep referencing the old
calibration they actually used, so historical growth numbers don't silently
change retroactively when you recalibrate.

**Scheduled capture failure handling: skip and retry next interval, mirror
phase 1's camera degradation model.** `camera.is_healthy()` (from phase 1)
already tells us if the camera is usable; the scheduler checks it before
attempting a capture and just skips a cycle if not, consistent with "never
crash, degrade and retry" from phase 1.

## Risks / Trade-offs

- **[Risk]** Manual two-point measurement is only as accurate as the
  person clicking, and as the calibration marker's placement →
  **Mitigation**: accepted per Non-Goals; still strictly better than no
  growth data, and the calibration-history design means bad measurements
  are traceable to a specific calibration event, not silently blended.
- **[Risk]** SQLite file on the boot SD card is a single point of data loss
  → **Mitigation**: `GOKU_DB_PATH` is relocatable like `GOKU_SNAP_DIR`;
  moving both off the SD card and adding an offsite backup is documented in
  the README as an operational step (out of scope for this change's code).
- **[Risk]** A too-frequent snapshot interval fills storage fast (same
  concern phase 1 raised for recordings) → **Mitigation**: default interval
  is conservative (60 min), configurable, and documented alongside the
  existing storage-wear guidance.

## Migration Plan

1. `store.py` creates its schema on first run if the DB file doesn't exist
   (`CREATE TABLE IF NOT EXISTS`) — no separate migration step for this
   initial schema.
2. Existing files already in `captures/` are not retroactively indexed —
   the datastore only records what's captured from this change forward.
   Backfilling historical files is possible later but isn't needed for the
   pipeline to start working.
3. Rollback: revert the commit; the SQLite file is additive and doesn't
   change anything the existing manual snapshot/gallery flow depends on.
