"""
Thin client for the Anthropic Messages API — raw HTTPS via `requests`
(already a dependency), not the `anthropic` SDK, since this app makes
exactly one kind of call: one image, one text prompt, no streaming.
"""
import base64
import io
import time

import requests
from PIL import Image

from . import config
from . import store

_API_URL = "https://api.anthropic.com/v1/messages"
_ANTHROPIC_VERSION = "2023-06-01"
_TIMEOUT_SEC = 30

_MOCK_HEALTH_RESPONSE = (
    "Goku looks alert and active in the photo, shell coloring looks normal. "
    "No signs of concern.\nCONCERN: no"
)
_MOCK_CAPTION_RESPONSE = "Just another sunny day being a very good tortoise. 🐢☀️"


class AICallError(Exception):
    pass


def downscale_image(path: str, max_dim: int = None) -> bytes:
    max_dim = max_dim or config.AI_MAX_IMAGE_DIM
    with Image.open(path) as img:
        img = img.convert("RGB")
        if max(img.size) > max_dim:
            img.thumbnail((max_dim, max_dim))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=80)
        return buf.getvalue()


def _under_daily_cap() -> bool:
    return store.calls_today() < config.AI_MAX_CALLS_PER_DAY


def call_claude(purpose: str, model: str, system_prompt: str, user_text: str, image_bytes: bytes = None) -> str:
    """
    Send one message to Claude, optionally with an image. Returns the
    text response. Raises AICallError on failure — callers are expected
    to catch this and skip the cycle, never let it propagate into a
    scheduler thread dying silently.
    """
    if config.AI_MOCK:
        store.log_ai_call(purpose, ok=True)
        return _MOCK_HEALTH_RESPONSE if purpose == "health_check" else _MOCK_CAPTION_RESPONSE

    if not config.ANTHROPIC_API_KEY:
        raise AICallError("ANTHROPIC_API_KEY is not set")

    if not _under_daily_cap():
        raise AICallError(f"daily AI call cap ({config.AI_MAX_CALLS_PER_DAY}) reached")

    content = []
    if image_bytes:
        content.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/jpeg",
                "data": base64.b64encode(image_bytes).decode("ascii"),
            },
        })
    content.append({"type": "text", "text": user_text})

    payload = {
        "model": model,
        "max_tokens": 512,
        "system": system_prompt,
        "messages": [{"role": "user", "content": content}],
    }
    headers = {
        "x-api-key": config.ANTHROPIC_API_KEY,
        "anthropic-version": _ANTHROPIC_VERSION,
        "content-type": "application/json",
    }

    ok = False
    try:
        resp = requests.post(_API_URL, json=payload, headers=headers, timeout=_TIMEOUT_SEC)
        resp.raise_for_status()
        data = resp.json()
        text = "".join(block.get("text", "") for block in data.get("content", []))
        ok = True
        return text
    except requests.RequestException as e:
        raise AICallError(f"Claude API call failed: {e}") from e
    finally:
        store.log_ai_call(purpose, ok=ok)


def build_history_summary() -> str:
    """Short text summary of recent feeding/measurements — capped, not a
    full row dump, to keep prompt size (and cost) predictable."""
    feeds = store.recent_feeding(limit=5)
    measures = store.recent_measurements(limit=3)

    lines = []
    if feeds:
        lines.append("Recent feeding log:")
        for f in feeds:
            when = time.strftime("%Y-%m-%d", time.localtime(f["logged_at"]))
            portion = f" ({f['portion']})" if f["portion"] else ""
            lines.append(f"- {when}: {f['food']}{portion}")
    else:
        lines.append("No feeding events logged yet.")

    if measures:
        lines.append("Recent measurements:")
        for m in measures:
            when = time.strftime("%Y-%m-%d", time.localtime(m["measured_at"]))
            lines.append(f"- {when}: {m['cm_distance']:.1f} cm")
    else:
        lines.append("No measurements recorded yet.")

    return "\n".join(lines)


_HEALTH_SYSTEM_PROMPT = (
    "You are looking at a photo of Goku, a pet sulcata tortoise, taken by an "
    "automated camera, alongside a summary of recent feeding and growth "
    "measurement records. Write a brief (2-3 sentence) observation of what "
    "you can see — activity level, apparent alertness, shell/skin appearance, "
    "anything unusual. This is an assistive observation from limited data, "
    "not a veterinary diagnosis, and should be phrased that way. End your "
    "reply with exactly one line, 'CONCERN: yes' or 'CONCERN: no', for "
    "whether anything in the photo or the recent history seems worth a "
    "person looking into."
)

_CAPTION_SYSTEM_PROMPTS = {
    "roundup": (
        "You write short, warm Instagram captions for a pet sulcata "
        "tortoise named Goku's account, from his point of view when it "
        "suits, otherwise a fond human narrator. You're given a recent "
        "photo and a summary of the past week's feeding and growth data. "
        "Write ONE caption (1-3 sentences, can include relevant emoji, no "
        "hashtags) summarizing Goku's week. Reply with only the caption "
        "text, nothing else."
    ),
    "highlight": (
        "You write short, warm Instagram captions for a pet sulcata "
        "tortoise named Goku's account. You're given a recent photo and a "
        "little recent history for context. Write ONE caption (1-2 "
        "sentences, can include relevant emoji, no hashtags) about this "
        "specific moment — what Goku appears to be doing in the photo "
        "(e.g. basking, eating, exploring). Reply with only the caption "
        "text, nothing else."
    ),
}


def build_caption_prompt(cadence: str) -> str:
    assert cadence in _CAPTION_SYSTEM_PROMPTS
    return _CAPTION_SYSTEM_PROMPTS[cadence]


def build_health_prompt() -> str:
    return _HEALTH_SYSTEM_PROMPT


def parse_concern_flag(text: str) -> bool:
    """Defensive parse of a trailing 'CONCERN: yes|no' line. Defaults to
    not-concerning on anything unexpected — the raw text is always stored
    regardless, so nothing is lost, only the flag degrades conservatively."""
    for line in reversed(text.strip().splitlines()):
        line = line.strip().lower()
        if line.startswith("concern:"):
            return "yes" in line
    return False
