## Context

Phase 4 built a draft queue assuming a future phase would consume
`approved` drafts to publish them via the Instagram Graph API. The user
decided against that path — no Meta Business account linking, no app
review wait — in favor of emailing content to themselves and posting by
hand. This phase replaces "phase 5" as originally scoped. See `proposal.md`
for why; `specs/email-delivery/spec.md` and the `ai-insights` delta for the
behavior contract.

## Goals / Non-Goals

**Goals:**
- Get draft captions (with photo) and video recordings into the user's
  inbox with no manual step in the app required to trigger it.
- No new runtime dependency — SMTP over stdlib `smtplib`/`email`.
- Never let an email failure affect the feature that triggered it (draft
  creation, recording save) — same degrade-without-disrupting principle
  as every prior phase's background jobs.

**Non-Goals:**
- Actually posting to Instagram — explicitly descoped by the user in favor
  of manual posting.
- A transactional email service (SendGrid/Mailgun) — the user chose
  SMTP + app password for simplicity; revisit only if deliverability
  becomes a real problem.
- Emailing every snapshot — scheduled and manual still-photo snapshots
  stay browsable in `/gallery`/`/biomarkers` only, not pushed to email,
  to avoid an hourly flood (see spec's "not individually emailed"
  requirement).
- Rich HTML email templates — plain text body with the caption, one
  attachment. Nothing here needs to look polished; it's a personal
  notification, not the actual post.

## Decisions

**Transport: `smtplib` + `email.mime`, not a library.** Same reasoning as
phase 4's Anthropic client — this app sends one shape of message (a
subject, a short body, one attachment) to one fixed recipient. Stdlib
covers that completely; a library would be solving a problem this app
doesn't have (templating, bulk sending, tracking).

**Provider: Gmail/Workspace SMTP with an app password (`smtp.gmail.com:587`,
STARTTLS), per the user's choice.** Works identically for a Google
Workspace domain (like `primate.ventures`) as for consumer Gmail — same
app-password mechanism. `GOKU_SMTP_HOST`/`PORT` stay configurable so a
different provider is a config change, not a code change, if that's ever
needed.

**Trigger point: inline, right after the triggering action succeeds — not
a separate queue/worker.** Both call sites (`insights_scheduler.py` after
`store.create_draft`, `web.py`'s `api_record` after a successful recording)
already run off the request/scheduler thread that just did the real work;
adding one more synchronous call (wrapped in try/except, logging on
failure) is simpler than introducing a delivery queue for what is, at
this scale, a handful of emails a week.

**Failure handling: catch everything in the mailer, return a bool, never
raise to the caller.** `mailer.send(...)` swallows `smtplib` exceptions
(auth failure, connection refused, timeout) internally and logs them;
callers don't need their own try/except around every call site, and a
misconfigured SMTP password can never turn into a failed snapshot/draft
save. This mirrors phase 4's `ai.call_claude` raising `AICallError` for
its callers to catch — the difference here is the mailer is even more
"fire and forget" since nothing downstream depends on the email having
sent, so there isn't a caller-side retry/skip decision to make either.

**`GOKU_MAIL_MOCK`: logs the would-be email instead of sending.** Same
pattern as `GOKU_AI_MOCK` — lets this be exercised in the demo/test flow
without real SMTP credentials.

## Risks / Trade-offs

- **[Risk]** An app password in an env var on the Pi is a real credential
  living in plaintext (same category as the Anthropic key already there)
  → **Mitigation**: scoped to send-only on one Google account, revocable
  independently of the account's main password; documented in the README
  alongside the same caution already given for the Anthropic key.
- **[Risk]** Gmail SMTP has sending-rate limits (generous for personal
  volume, but real) → **Mitigation**: at this app's cadence (a few drafts
  a week, recordings on-demand) nowhere close to relevant; would only
  matter if intervals were misconfigured to something extreme, which the
  daily AI call cap already guards against on the drafting side.
- **[Risk]** Recording attachments (H.264 MP4, ~10s) could be large enough
  to bounce against a provider's attachment size cap on a longer manual
  recording → **Mitigation**: not solved here — out of scope for a first
  cut; worth revisiting only if someone actually starts recording longer
  clips and hits a bounce.

## Migration Plan

1. No schema change. `post_drafts.status` is reinterpreted, not restructured.
2. Ships inert without `GOKU_NOTIFY_EMAIL` + SMTP credentials configured —
   logs that email isn't configured and continues normally, same pattern
   as phase 4 shipping inert without `ANTHROPIC_API_KEY`.
3. Rollback: revert the commit; nothing else depends on the mailer having
   run.
