## Why

Phase 3 gives GokuCam a real history — snapshots, feeding events, growth
measurements — but nothing looks at it. The user wants "an existing model,
like Claude" to look at Goku's recent photos and data, the same way you'd
manually send Claude a photo and ask it to assess or caption it, and to do
that on a schedule instead of by hand. This is the brains half of "the
model should post to Instagram" (phase 5 is the actual posting mechanics);
this phase produces the health notes and draft captions, it does not
publish anything.

## What Changes

- A scheduled health-check job periodically sends Claude the latest
  snapshot plus a text summary of recent feeding/measurement history, and
  asks for a short structured assessment (what's observed, anything
  concerning). Result is stored, and flagged entries are visible on the
  biomarker dashboard.
- A scheduled caption-drafting job runs on two cadences — roughly weekly
  (a roundup of the week) and every few days (one specific moment) — matching
  phase 5's intended posting cadence, and asks Claude to draft an
  Instagram-style caption from a chosen recent photo and the same recent
  history.
- Draft captions are stored with a `pending_review` status and shown on the
  dashboard with Approve / Reject controls — **assumption (flagged, not yet
  confirmed by the user): a human approves before anything is eligible to
  post.** Phase 5 will only ever publish `approved` drafts, never
  `pending_review` ones directly. This is a one-line policy to relax later
  (auto-approve after N hours) if it turns out to be unnecessary friction,
  but starting stricter on a public-facing account is the safer default.
- Uses the Anthropic Messages API directly over HTTP (via `requests`,
  already a dependency) rather than adding the `anthropic` Python SDK as a
  new dependency, since this app only ever makes one kind of call.
- Both jobs degrade the same way phase 1/3 background jobs do: skip and
  retry next interval on failure (network down, API error, rate limit),
  never crash the process, and stay within a configurable daily call cap
  as a cost safety governor.

## Capabilities

### New Capabilities
- `ai-insights`: scheduled Claude-based health assessment and Instagram
  caption drafting from recent snapshots and biomarker history, with a
  human-reviewed draft queue.

### Modified Capabilities
(none — the new dashboard sections/routes follow the same
`@auth.login_required` pattern already established, expressed within
`ai-insights` itself, same as `biomarkers` did for `auth`)

## Impact

- New `gokucam/ai.py`: thin client for the Anthropic Messages API
  (`requests`-based), prompt construction from recent `store` data, image
  encoding/downscaling before upload.
- New `gokucam/insights_scheduler.py`: two background jobs (health-check
  interval, caption-draft interval), same sleep-loop style as
  `scheduler.py`.
- `gokucam/store.py`: new tables — `health_notes`, `post_drafts`.
- `gokucam/config.py`: `ANTHROPIC_API_KEY`, model names, cadence intervals,
  daily call cap, `GOKU_AI_MOCK` for offline development.
- `gokucam/web.py`: dashboard additions for health notes and the draft
  queue (approve/reject), all `@auth.login_required`.
- `run.py`: starts the new scheduler alongside the existing ones.
- New dependency: none beyond `requests`, already installed.
