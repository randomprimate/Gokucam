## Context

Phase 3 gave us a SQLite store (`snapshots`, `feeding_log`, `calibration`,
`measurements`) and a background-scheduler pattern (`gokucam/scheduler.py`)
that this phase reuses rather than introducing a second scheduling
mechanism. Phase 2's `auth.login_required` gates every new route the same
way. Budget is ~€50/month for the Anthropic API (user-provided). See
`proposal.md` for why; `specs/ai-insights/spec.md` for the contract.

## Goals / Non-Goals

**Goals:**
- Turn stored snapshots + history into Claude-generated health notes and
  draft captions, on a schedule, without a person initiating each call.
- Stay within budget by design (model choice, image size, a hard daily
  call cap), not by hoping usage stays low.
- Never let an AI-service outage or slowdown affect the camera/portal.
- Nothing posts anywhere in this phase — that's phase 5's job once a draft
  is `approved`.

**Non-Goals:**
- Actually publishing to Instagram — phase 5.
- Fine-tuning or training anything — the proposal is explicit this means
  calling an existing model (Claude) with images and a prompt, not building
  a model.
- Alerting (email/push) on a concerning health note — this phase makes
  concerning notes *visible* on the dashboard; wiring up a notification
  channel is a small, separate follow-on once there's a channel to use
  (the user hasn't said they want email/push yet).
- Automatic image selection sophistication (blur detection, face/shell
  detection to pick the "best" photo) — initially just the most recent
  snapshot for health checks, and the most recent snapshot at draft-time
  for captions. A smarter "pick the best of N" selector is a cheap later
  upgrade once there's a reason to believe recency isn't good enough.

## Decisions

**Transport: raw HTTPS calls to the Anthropic Messages API via `requests`,
not the `anthropic` SDK.** This app makes exactly one kind of call
(`POST /v1/messages` with an image block and a text prompt, no streaming,
no tool use). `requests` is already a dependency; the SDK would be a new
one for a single endpoint this app already knows how to call. If the
integration grows more complex later (streaming, retries with backoff
built in), revisit — but that's speculative today.

**Model split: Haiku for health checks, Sonnet for captions.** Health
checks run more often and are read by nobody unless something's flagged —
cheap and fast is what matters (`claude-haiku-4-5-20251001`). Captions are
public-facing, written words representing Goku's account, and run far less
often — worth spending more per call on a stronger model
(`claude-sonnet-5`). Both are env-configurable
(`GOKU_AI_HEALTH_MODEL`, `GOKU_AI_CAPTION_MODEL`) so this ratio can be
tuned against actual €/month spend once there's real usage data, without a
code change.

**Cost control has three independent layers, not just "pick a cheap
model":** (1) images are downscaled to a fixed max dimension (e.g. 800px)
before base64-encoding — vision token cost scales with image size, and
nothing here needs full sensor resolution for Claude to describe a turtle;
(2) history sent as a short structured text summary (last N feeding
entries, last measurement, not a full row dump) capped at a fixed size;
(3) a hard `GOKU_AI_MAX_CALLS_PER_DAY` counter (persisted in the store, not
just in-memory, so it survives a restart) that silently skips further
scheduled calls once hit — a safety governor against a scheduling bug or
an unexpectedly short interval turning into a runaway bill, independent of
whatever the two schedule intervals are configured to.

**Approval gate: drafts are `pending_review` until a person acts, no
auto-approve timer in this phase.** The proposal flags this as an
assumption because the user hasn't confirmed it, but building the
draft-queue UI either way is nearly the same amount of work, and shipping
the reversible/stricter default (nothing posts without a click) is safer
to launch with on a real public account than shipping auto-publish and
walking it back after an unwanted post already went out. An auto-approve
option (e.g. "approve automatically after 24h if untouched") is a one-line
follow-on if manual review turns out to be pure friction in practice.

**Scheduler: extend the phase-3 pattern (one thread per cadence), not a
generalized job runner.** Two more intervals (health-check, and two caption
cadences) is three sleep-loop threads total, following `scheduler.py`'s
existing shape. A real job-scheduling library becomes worth it if a fourth
or fifth cadence shows up (e.g. phase 5's own posting cadence) — not yet.

**Prompting: one fixed system prompt per job type, not a prompt-management
system.** Health-check prompt asks for a short JSON-ish structured reply
(summary text + a boolean concern flag) that gets parsed defensively — if
parsing fails, the raw text is stored as the summary and concern defaults
to false rather than the whole cycle failing. Caption prompt asks for plain
caption text, no parsing needed.

## Risks / Trade-offs

- **[Risk]** Claude's health assessment from a single photo has real limits
  (no thermometer, no scale, one angle) → **Mitigation**: framed to the
  user and, in the prompt itself, as an assistive observation from
  available data, not a veterinary diagnosis; concerning flags surface for
  a human to judge, they don't trigger any automated action.
- **[Risk]** A parsing failure on the structured health response could
  silently mask a real concern (defaults to "not concerning") →
  **Mitigation**: the raw response is always stored even on parse failure,
  so nothing is lost — a person looking at the dashboard sees the actual
  text; only the flag defaults conservatively-in-the-direction-of-not-
  alerting, which is why fixing the alerting Non-Goal later matters before
  leaning on the flag alone.
- **[Risk]** Daily call cap persisted in SQLite adds a small amount of
  contention on every scheduled call → **Mitigation**: negligible at this
  write volume (same store already handles phase 3's concurrent writes
  fine per its own verification).
- **[Risk]** Two new background threads plus phase 3's scheduler is three
  total, each independently timed — more moving parts to reason about →
  **Mitigation**: each is a plain, independently testable sleep-loop
  following an established pattern, not a new abstraction to learn.

## Migration Plan

1. New tables (`health_notes`, `post_drafts`, `ai_call_log` for the daily
   cap) created via `CREATE TABLE IF NOT EXISTS`, same as phase 3 — no
   migration step for existing data.
2. Ships disabled-by-default in the sense that it does nothing useful
   without `ANTHROPIC_API_KEY` set — missing key means the schedulers skip
   every cycle and log why, rather than failing to start (unlike phase 2's
   auth, this isn't a hard requirement to run the app at all).
3. `GOKU_AI_MOCK=1` returns a canned fake response instead of calling the
   real API, so this is fully testable offline/under
   `GOKU_MOCK_HARDWARE=1` without spending API budget.
4. Rollback: revert the commit; the new tables are additive and nothing
   else depends on them.
