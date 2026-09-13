## Why

Every GokuCam route is open to anyone who can reach the Pi — on the LAN today,
and on the Tailscale tailnet per the README. There's no login, so anyone with
network access can watch the stream, drive the servos, or delete captures.
The user wants a portal the household actually logs into to watch Goku, and
every later phase (biomarker dashboard, health notes, feeding log) needs an
authenticated session to attach data to and to keep private.

## What Changes

- Add a login page and session-based authentication in front of the existing
  Flask app.
- Gate the live view (`/`), gallery (`/gallery`), media downloads/deletes, and
  all control APIs (`/api/pan`, `/api/tilt`, `/api/center`, `/api/sweep`,
  `/api/snapshot`, `/api/record`) behind a logged-in session.
- Leave `/health` unauthenticated so the systemd watchdog and any uptime
  monitor set up in phase 1 keep working without credentials.
- **Assumption (flagged, not yet confirmed by the user):** one shared
  household credential rather than per-person accounts — simplest to run on
  a Pi with no user-management UI, and matches "family checks in on Goku."
  Credentials are configured via environment variables
  (`GOKU_PORTAL_USERNAME`, `GOKU_PORTAL_PASSWORD_HASH`), not hardcoded, so
  this can be swapped for per-user accounts later without changing how
  routes are gated.
- **Assumption:** deployment stays Tailscale-only for now (per the existing
  README), so plain-HTTP session cookies over the tailnet are acceptable;
  putting this behind a public domain is called out as a prerequisite (TLS)
  rather than solved here.
- Add a small CLI helper (`scripts/set_portal_password.py`) to generate the
  password hash, since there's no admin UI to do it from.
- Simple brute-force throttling on the login endpoint (in-memory, per-IP)
  since there's no external rate limiter in front of this app.

## Capabilities

### New Capabilities
- `auth`: session-based login gating the portal's routes, with login/logout
  endpoints, a login page, and a shared-credential store configured via
  environment variables.

### Modified Capabilities
(none — no existing specs yet; this is the first capability in the repo)

## Impact

- `gokucam/web.py`: every existing route except `/health` gets a
  `@login_required` decorator; new `/login` and `/logout` routes.
- `gokucam/config.py`: new env vars for credentials and session secret key.
- New `gokucam/auth.py`: session helper, `login_required` decorator,
  password verification, login-attempt throttling.
- New `gokucam/templates/login.html` + a login-form entry in
  `gokucam/static/style.css`.
- New `scripts/set_portal_password.py`: one-off CLI to hash a password into
  `GOKU_PORTAL_PASSWORD_HASH`.
- No new runtime dependency: uses Flask's built-in session (`itsdangerous`,
  already a Flask dependency) and `werkzeug.security` (already installed
  via Flask) for password hashing.
