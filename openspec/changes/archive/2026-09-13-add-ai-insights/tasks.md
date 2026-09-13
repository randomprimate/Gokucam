## 1. Config & datastore

- [x] 1.1 Add `ANTHROPIC_API_KEY`, `GOKU_AI_MOCK`, `GOKU_AI_HEALTH_MODEL` (default `claude-haiku-4-5-20251001`), `GOKU_AI_CAPTION_MODEL` (default `claude-sonnet-5`), `GOKU_AI_HEALTHCHECK_INTERVAL_HOURS`, `GOKU_AI_ROUNDUP_INTERVAL_DAYS`, `GOKU_AI_HIGHLIGHT_INTERVAL_DAYS`, `GOKU_AI_MAX_CALLS_PER_DAY`, `GOKU_AI_MAX_IMAGE_DIM` to `gokucam/config.py`; verify sane defaults documented and importable
- [x] 1.2 Add `health_notes`, `post_drafts`, `ai_call_log` tables to `gokucam/store.py` schema plus accessor functions (`record_health_note`, `recent_health_notes`, `create_draft`, `set_draft_status`, `pending_drafts`, `approved_drafts`, `log_ai_call`, `calls_today`); verify each function against a temp DB
- [x] 1.3 Verify `calls_today()` correctly resets across a day boundary (test with an explicit past-day row inserted directly, confirming it isn't counted) and correctly counts same-day calls

## 2. Anthropic client

- [x] 2.1 Create `gokucam/ai.py`: `downscale_image(path, max_dim) -> bytes`, `call_claude(model, system_prompt, user_text, image_bytes) -> str` posting to the Anthropic Messages API via `requests` with the API key from config, a timeout, and raising on non-2xx; verify with a real key against a real snapshot (or, absent one, verify request construction/headers against a mocked `requests.post`)
- [x] 2.2 Add `GOKU_AI_MOCK=1` short-circuit in `call_claude` returning a canned fixed response without making a network call; verify no network call is attempted (e.g. patch `requests.post` to raise if called, confirm it isn't) when mock mode is on
- [x] 2.3 Add a daily-cap guard wrapping `call_claude` (checks `store.calls_today()` against `GOKU_AI_MAX_CALLS_PER_DAY` before calling, logs and calls `store.log_ai_call()` after every attempted call whether it succeeds or fails); verify calls stop once the cap is reached within a single day

## 3. Health-check job

- [x] 3.1 Build the health-check prompt: fixed system prompt asking for a short assessment plus an explicit concern flag in a parseable form (e.g. a trailing `CONCERN: yes|no` line), plus a text summary of the last N feeding/measurement rows from `store`; verify the summary renders sensibly with an empty store (no feeding/measurements yet) and with populated data
- [x] 3.2 Implement the health-check cycle in `gokucam/insights_scheduler.py`: pick the most recent snapshot, build the prompt, call Claude (health model), parse the concern flag defensively (default to not-concerning on parse failure, always store the raw text), call `store.record_health_note`; verify end to end under `GOKU_AI_MOCK=1` with `GOKU_MOCK_HARDWARE=1`
- [x] 3.3 Skip the cycle without error when no snapshot exists yet; verify against an empty store

## 4. Caption-draft jobs

- [x] 4.1 Build the caption prompt(s): a "roundup" variant (recent history summary, asks for a weekly-style caption) and a "highlight" variant (asks for a caption about one recent moment); verify both produce non-empty text under mock mode
- [x] 4.2 Implement both cadences in `insights_scheduler.py` as independent sleep-loop timers (matching `scheduler.py`'s style), each selecting the most recent snapshot, calling Claude (caption model), and storing the result via `store.create_draft(..., status="pending_review", cadence=...)`; verify both fire independently at their configured intervals under mock mode and produce distinct `pending_review` rows
- [x] 4.3 Wire all three new background jobs (health-check, roundup, highlight) to start in `run.py` alongside the phase-3 scheduler; verify startup log lines for each and clean shutdown

## 5. Dashboard: health notes & draft queue

- [x] 5.1 Add a health-notes section to `/biomarkers` (or a new `/insights` page — pick one and be consistent with existing nav) showing recent notes, visually distinguishing concerning ones (e.g. a colored badge); verify a concerning note is visually distinct from a routine one
- [x] 5.2 Add a draft-queue section listing `pending_review` drafts (photo + caption text) with Approve / Reject buttons; verify each button updates status via a `@auth.login_required` POST route and the draft leaves the pending list afterward
- [x] 5.3 Verify an approved draft is retrievable via `store.approved_drafts()` and a rejected one is excluded, and that no draft is ever returned as eligible-to-publish while still `pending_review`
- [x] 5.4 Verify all new routes redirect/401 when logged out, same as existing protected routes

## 6. Verification & docs

- [x] 6.1 End-to-end manual pass with `GOKU_MOCK_HARDWARE=1` and `GOKU_AI_MOCK=1`: health-check and both caption cadences produce rows on short test intervals, dashboard shows them, approve/reject transitions work, daily cap stops further calls once reached; existing phase 1–3 behavior unaffected
- [x] 6.2 Update `README.md`: new env vars, the model-split rationale in one line, the daily call cap as a cost safety net, and that nothing posts to Instagram yet — drafts wait for phase 5
