"""
SMTP email delivery for draft captions and recordings — stdlib
smtplib/email only, no new dependency. Never raises: every failure mode
(unconfigured, bad credentials, network down) logs and returns False, so
a caller never needs its own try/except to stay safe.
"""
import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from . import config


def _configured() -> bool:
    return bool(config.NOTIFY_EMAIL and config.SMTP_USERNAME and config.SMTP_PASSWORD)


def send(subject: str, body: str, attachments=None) -> bool:
    """
    attachments: list of (filename, bytes, mime_subtype) tuples, e.g.
    [("photo.jpg", jpeg_bytes, "jpeg")] or [("clip.mp4", mp4_bytes, "mp4")].
    Returns True only on a confirmed send; False (logged) on anything else,
    including "not configured" and "mock mode".
    """
    attachments = attachments or []

    if config.MAIL_MOCK:
        names = [a[0] for a in attachments]
        print(f"[GokuCam][Mail][MOCK] would send {subject!r} to {config.NOTIFY_EMAIL} (attachments: {names})")
        return False

    if not _configured():
        print(f"[GokuCam][Mail] not configured (GOKU_NOTIFY_EMAIL / GOKU_SMTP_* unset) — skipping: {subject!r}")
        return False

    msg = MIMEMultipart()
    msg["Subject"] = subject
    msg["From"] = config.SMTP_FROM
    msg["To"] = config.NOTIFY_EMAIL
    msg.attach(MIMEText(body, "plain"))

    for filename, data, subtype in attachments:
        part = MIMEApplication(data, _subtype=subtype)
        part.add_header("Content-Disposition", "attachment", filename=filename)
        msg.attach(part)

    try:
        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=20) as smtp:
            smtp.starttls()
            smtp.login(config.SMTP_USERNAME, config.SMTP_PASSWORD)
            smtp.send_message(msg)
        return True
    except (smtplib.SMTPException, OSError) as e:
        print(f"[GokuCam][Mail] send failed: {e}")
        return False


def send_draft_email(draft_row, image_bytes: bytes) -> bool:
    cadence = draft_row["cadence"]
    caption = draft_row["caption"]
    subject = f"GokuCam: new {cadence} caption ready"
    body = (
        f"A new {cadence} draft is ready — copy this into Instagram:\n\n"
        f"{caption}\n\n"
        f"(Approve/Reject on /insights is just your own tracking now — "
        f"this email already has everything you need to post.)"
    )
    return send(subject, body, attachments=[("draft.jpg", image_bytes, "jpeg")])


def send_recording_email(path: str) -> bool:
    with open(path, "rb") as f:
        video_bytes = f.read()
    subject = "GokuCam: new recording"
    body = "A new manual recording of Goku is attached."
    filename = path.split("/")[-1]
    return send(subject, body, attachments=[(filename, video_bytes, "mp4")])
