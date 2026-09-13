## 1. Datastore

- [x] 1.1 Add `GOKU_DB_PATH` (default `<BASE_DIR>/gokucam.db`) and `GOKU_SNAPSHOT_INTERVAL_MIN` (default `60`) to `gokucam/config.py`; verify defaults resolve to a path next to `captures/`
- [x] 1.2 Create `gokucam/store.py`: schema creation (`snapshots`, `feeding_log`, `calibration`, `measurements`) run on first connection, plus `record_snapshot`, `log_feeding`, `set_calibration`, `get_latest_calibration`, `record_measurement`, `recent_history(limit)`; verify by exercising each function from a throwaway script against a temp DB file
- [x] 1.3 Verify concurrent access from the scheduler thread and Flask's request threads doesn't corrupt the DB (use a short stress script hitting `log_feeding` and `record_snapshot` concurrently) — use `sqlite3.connect(..., check_same_thread=False)` with a module-level lock if needed

## 2. Scheduler

- [x] 2.1 Create `gokucam/scheduler.py`: background thread sleeping in `GOKU_SNAPSHOT_INTERVAL_MIN`-sized steps, checking `camera.is_healthy()` before each capture, calling `camera.snapshot()` and `store.record_snapshot(..., reason="scheduled")`; verify by setting a short interval (e.g. via an env override) under `GOKU_MOCK_HARDWARE=1` and observing rows accumulate
- [x] 2.2 Skip (not crash) a cycle when the camera is unavailable, logging why; verify by forcing `camera.available = False` in a manual test and confirming the loop continues on the next interval
- [x] 2.3 Wire the scheduler to start in `run.py` alongside the existing camera/servo singletons; verify it starts on `python run.py` (log line) and stops cleanly on process exit
- [x] 2.4 Record manual snapshots (existing `/api/snapshot`) into the same store with `reason="manual"`; verify a manual snapshot appears in `store.recent_history()`

## 3. Feeding log

- [x] 3.1 Add `POST /api/feeding` (food, portion, note, optional timestamp) behind `@auth.login_required`, validating food is non-empty, calling `store.log_feeding`; verify a valid submission persists and an empty-food submission is rejected with an error, no row created
- [x] 3.2 Add a feeding-log form section to the biomarker dashboard template; verify submitting it from the browser creates a visible entry without a page-breaking reload (simple form POST + redirect is fine, no JS required)

## 4. Measurement tool

- [x] 4.1 Add `POST /api/calibration` (snapshot id, two pixel points, real-world distance in cm) behind `@auth.login_required`, computing and storing `px_per_cm` via `store.set_calibration`; verify a calibration round-trips (store then read back the same ratio)
- [x] 4.2 Add `POST /api/measurement` (snapshot id, two pixel points) behind `@auth.login_required` that uses `store.get_latest_calibration()` to compute a cm distance and calls `store.record_measurement`; verify it rejects with a clear error when no calibration exists yet, and computes correctly when one does
- [x] 4.3 Add a click-to-measure canvas UI on a snapshot detail view (plain JS, no new frontend dependency): click two points, show pixel distance, submit either as a calibration (with an entered real-world distance) or a measurement (once calibrated); verify by calibrating against a snapshot, then measuring a second pair of points and seeing a sane cm value

## 5. Dashboard & wiring

- [x] 5.1 Add `GET /biomarkers` behind `@auth.login_required` rendering `gokucam/templates/biomarkers.html` with `store.recent_history()` (snapshots, feeding entries, measurements merged/sorted by timestamp); verify it renders with seeded mock data and with an empty store
- [x] 5.2 Add a nav link to `/biomarkers` from `index.html` and `gallery.html`; verify navigation works end to end while logged in, and that `/biomarkers` redirects to `/login` when logged out

## 6. Verification & docs

- [x] 6.1 End-to-end manual pass with `GOKU_MOCK_HARDWARE=1`: scheduled snapshots accumulate in the store, a feeding entry can be logged and appears on the dashboard, a calibration can be set and a subsequent measurement computed and shown; `/health` and existing phase 1/2 behavior remain unaffected
- [x] 6.2 Update `README.md`: new env vars, the physical reference-marker prerequisite for measurement, and the recommendation to relocate `GOKU_DB_PATH`/`GOKU_SNAP_DIR` off the SD card with a periodic offsite backup
