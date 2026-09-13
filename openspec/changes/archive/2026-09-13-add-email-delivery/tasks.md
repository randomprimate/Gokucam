## 1. Config

- [x] 1.1 Add `GOKU_SMTP_HOST` (default `smtp.gmail.com`), `GOKU_SMTP_PORT` (default `587`), `GOKU_SMTP_USERNAME`, `GOKU_SMTP_PASSWORD`, `GOKU_SMTP_FROM` (default = username), `GOKU_NOTIFY_EMAIL`, `GOKU_MAIL_MOCK` to `gokucam/config.py`; verify importable with sane defaults

## 2. Mailer

- [x] 2.1 Create `gokucam/mailer.py`: `send(subject, body, attachments=[(filename, bytes, mimetype)]) -> bool` using `smtplib`/`email.mime.multipart`, STARTTLS, catching all exceptions internally and logging rather than raising; verify it returns `False` and logs (doesn't raise) on a deliberately bad host/port
- [x] 2.2 Return `False` immediately (no connection attempt) when `GOKU_NOTIFY_EMAIL` or SMTP credentials aren't configured, logging why once; verify no network call is attempted when unconfigured
- [x] 2.3 Add `GOKU_MAIL_MOCK=1` short-circuit that logs the subject/body/attachment names instead of sending; verify no network call happens in mock mode (patch `smtplib.SMTP` to raise if instantiated, confirm it isn't)
- [x] 2.4 Add `send_draft_email(draft_row, image_bytes)` and `send_recording_email(path)` helper wrappers that build the subject/body/attachment and call `send`; verify each produces a well-formed message (parse it back with `email.message_from_bytes` in a test and check attachment + body content)

## 3. Wire trigger points

- [x] 3.1 Call `mailer.send_draft_email(...)` in `gokucam/insights_scheduler.py` right after `store.create_draft(...)` succeeds in `_run_caption_draft`; verify a draft is still created (and the cycle doesn't fail) even if the mailer call raises unexpectedly (belt-and-suspenders try/except at the call site too, even though `mailer.send` shouldn't raise)
- [x] 3.2 Call `mailer.send_recording_email(...)` in `gokucam/web.py`'s `api_record` right after `camera.record_mp4(...)` succeeds; verify `/api/record` still returns its normal success response even when `GOKU_MAIL_MOCK`/email is unconfigured or the mailer call fails
- [x] 3.3 Verify scheduled and manual snapshot capture paths (`scheduler.py`, `api_snapshot`) are untouched — no email call added there, per the spec's "not individually emailed" requirement

## 4. Verification & docs

- [x] 4.1 End-to-end pass with `GOKU_MOCK_HARDWARE=1`, `GOKU_AI_MOCK=1`, `GOKU_MAIL_MOCK=1`: trigger a draft (short interval) and a manual recording, confirm mock-mode log lines show the would-be email for each, with the right attachment and caption/recording reference
- [x] 4.2 One pass with `GOKU_MAIL_MOCK=0` and real Gmail/Workspace SMTP app-password credentials (if available in this environment) sending an actual test email to `GOKU_NOTIFY_EMAIL`; if real credentials aren't available in this session, verify request/message construction against a local SMTP debug server (`python -m smtpd -c DebuggingServer` or `aiosmtpd`) instead, and note in the PR/commit that real-provider sending wasn't verified live
- [x] 4.3 Update `README.md`: new env vars, that this replaces the original Graph-API phase 5 plan, and the note that Approve/Reject on `/insights` is now just personal tracking
