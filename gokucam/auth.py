import time
import threading
from functools import wraps

from flask import session, request, redirect, url_for, jsonify
from werkzeug.security import generate_password_hash, check_password_hash

from . import config

# Resolved once at import time: real credentials if configured, otherwise
# (mock mode only) a loud dev-only fallback so local iteration doesn't
# require generating a hash first.
if config.PORTAL_PASSWORD_HASH:
    _USERNAME = config.PORTAL_USERNAME
    _PASSWORD_HASH = config.PORTAL_PASSWORD_HASH
elif config.MOCK_HARDWARE:
    _USERNAME = config.DEV_DEFAULT_USERNAME
    _PASSWORD_HASH = generate_password_hash(config.DEV_DEFAULT_PASSWORD)
    print(f"[GokuCam][Auth][DEV MODE] No GOKU_PORTAL_PASSWORD_HASH set — "
          f"using dev-only credentials: username={_USERNAME!r} password={config.DEV_DEFAULT_PASSWORD!r}")
else:
    raise SystemExit(
        "[GokuCam][Auth] GOKU_SECRET_KEY and GOKU_PORTAL_PASSWORD_HASH must be set "
        "before running against real hardware. Generate a hash with "
        "`python scripts/set_portal_password.py`, or set GOKU_MOCK_HARDWARE=1 for local dev."
    )

if not config.SECRET_KEY and not config.MOCK_HARDWARE:
    raise SystemExit("[GokuCam][Auth] GOKU_SECRET_KEY must be set before running against real hardware.")


# --- brute-force throttling: in-memory, per source IP ---
_attempts_lock = threading.Lock()
_attempts: dict[str, list[float]] = {}


def _client_key() -> str:
    return request.remote_addr or "unknown"


def _is_throttled(key: str) -> bool:
    now = time.time()
    with _attempts_lock:
        window_start = now - config.LOGIN_WINDOW_SEC
        recent = [t for t in _attempts.get(key, []) if t >= window_start]
        _attempts[key] = recent
        return len(recent) >= config.LOGIN_MAX_ATTEMPTS


def _record_failed_attempt(key: str) -> None:
    with _attempts_lock:
        _attempts.setdefault(key, []).append(time.time())


def _clear_attempts(key: str) -> None:
    with _attempts_lock:
        _attempts.pop(key, None)


# --- session helpers ---
def login(username: str, password: str) -> bool:
    """Attempt to authenticate; starts a session on success. Throttled per source IP."""
    key = _client_key()
    if _is_throttled(key):
        return False

    ok = username == _USERNAME and check_password_hash(_PASSWORD_HASH, password)
    if not ok:
        _record_failed_attempt(key)
        return False

    _clear_attempts(key)
    session.clear()
    session["authenticated"] = True
    session.permanent = True
    return True


def logout() -> None:
    session.clear()


def is_authenticated() -> bool:
    return bool(session.get("authenticated"))


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if is_authenticated():
            return view(*args, **kwargs)
        # Routes under /api/ are called by this app's own JS via fetch() and
        # expect JSON; everything else is a browser navigation and should
        # land on the login page. (Not Accept-header sniffing: curl's and
        # fetch()'s default `Accept: */*` makes content negotiation here
        # ambiguous, so the URL structure is the reliable signal.)
        if request.path.startswith("/api/"):
            return jsonify({"error": "authentication required"}), 401
        return redirect(url_for("login_page", next=request.path))
    return wrapped
