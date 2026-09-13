## Why

Phase 5 was originally scoped as automated Instagram publishing via the
Meta Graph API, which needs a Business/Creator account link and Meta's app
review before it works for anyone but the account owner — an external
dependency with its own timeline. The user has decided to start simpler:
get the content to their own inbox and post it to `@goku.guita` by hand.
This replaces the Graph API integration with email delivery, and removes
the "approval gates publishing" framing from phase 4 since nothing
publishes automatically anymore.

## What Changes

- A new email module sends mail via SMTP (Gmail/Workspace + an app
  password, per the user's choice) — no new dependency, `smtplib` and
  `email` are stdlib.
- Every caption draft (roundup or highlight) created by phase 4's insights
  scheduler now triggers an email immediately — photo attached, Claude's
  caption in the body ready to copy into Instagram — instead of only
  becoming visible on `/insights`.
- Every manual video recording (`/api/record`) also triggers an email with
  the clip attached. Recordings never went through the AI captioning
  pipeline at all (Claude drafts captions from still photos, not video),
  so this is the only way "videos" from the user's request reach their
  inbox. **Assumption (flagged): scheduled/automatic snapshots and manual
  photo snapshots are NOT individually emailed** — only curated draft
  captions and recordings — to avoid an hourly flood of email for content
  already browsable in `/gallery` and `/biomarkers`.
- The existing Approve/Reject buttons on `/insights` stay, but change
  meaning: they're now the user's own "did I post this" tracker, not a
  gate on anything downstream (nothing was ever built to consume
  `approved` drafts, so this is a documentation-level change, not a code
  removal).
- Email failures (bad credentials, SMTP outage, no network) never block or
  fail the underlying action — draft creation and recordings still succeed
  and are still visible in the app even if the email couldn't be sent.

## Capabilities

### New Capabilities
- `email-delivery`: SMTP-based email notifications carrying draft
  captions and recordings to a configured recipient.

### Modified Capabilities
- `ai-insights`: the "Drafts require human approval before becoming
  postable" requirement is replaced — there is no publishing step for
  approval to gate anymore, so the requirement changes to describe
  Approve/Reject as a personal tracking status only.

## Impact

- New `gokucam/mailer.py`: SMTP client (`smtplib`/`email.mime`), a
  `GOKU_MAIL_MOCK` short-circuit for testing without real credentials,
  never raises out to callers (logs and returns a success/failure bool).
- `gokucam/config.py`: `GOKU_SMTP_HOST`, `GOKU_SMTP_PORT`,
  `GOKU_SMTP_USERNAME`, `GOKU_SMTP_PASSWORD`, `GOKU_SMTP_FROM`,
  `GOKU_NOTIFY_EMAIL`, `GOKU_MAIL_MOCK`.
- `gokucam/insights_scheduler.py`: calls the mailer right after
  `store.create_draft(...)` succeeds.
- `gokucam/web.py`: `api_record` calls the mailer right after a manual
  recording is saved.
- `gokucam/store.py`: no schema change — reuses existing `post_drafts`
  status field, just documents its meaning differently.
- No new runtime dependency.
