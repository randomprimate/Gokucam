## Context

GokuCam is a single Flask process (`gokucam/web.py`) with no auth layer today.
Phase 1 (already shipped) made the camera/servo layers degrade gracefully and
added `GOKU_MOCK_HARDWARE` for off-Pi development — this design builds on
that, and should keep working identically under mock hardware. See
`proposal.md` for why this is needed now; see `specs/auth/spec.md` for the
behavior contract.

## Goals / Non-Goals

**Goals:**
- Every route except `/health` requires a valid session.
- No new runtime dependency — Flask ships everything needed (signed session
  cookies via `itsdangerous`, `werkzeug.security` for password hashing).
- Credentials configured via environment variables, never committed.
- Works identically with `GOKU_MOCK_HARDWARE=1` so this is testable off-Pi.

**Non-Goals:**
- Per-user accounts, roles, or an admin UI for managing users — one shared
  household credential only (flagged as an assumption in the proposal).
- TLS termination — out of scope here; tracked as a prerequisite for ever
  exposing this beyond the Tailscale tailnet.
- CSRF tokens on every form — see Decisions for why this is deferred.

## Decisions

**Session mechanism: Flask's signed cookie session, not Flask-Login.**
A single shared credential doesn't need a `User` model, `user_loader`, or any
of what Flask-Login provides — it needs "is there a valid signed cookie
saying `authenticated=True` and not expired." Flask's built-in
`session` object (backed by `itsdangerous`, already a Flask dependency)
does exactly that with zero new dependencies. `PERMANENT_SESSION_LIFETIME`
gives us the inactivity-expiry requirement for free (Flask refreshes the
cookie's expiry on each request when `session.permanent = True` and
`SESSION_REFRESH_EACH_REQUEST` is left at its default). If per-user accounts
get added later, this is the seam where Flask-Login would slot in without
touching the route-gating decorator's call sites.

**Password storage: `GOKU_PORTAL_PASSWORD_HASH` (pre-hashed), not a plaintext
env var.** `werkzeug.security.generate_password_hash` /
`check_password_hash` (already installed via Flask/Werkzeug). Storing a
plaintext password in an env var means it leaks into `systemctl show`,
process listings, and shell history. A one-off script
(`scripts/set_portal_password.py`) prompts for a password and prints the
hash to paste into the systemd unit's environment — never stores the
plaintext anywhere.

**Route gating: a decorator, applied per-route, not a `before_request`
blanket.** A blanket `before_request` hook gating everything is simpler to
write, but silently starts protecting every *future* route too, including
`/health` if someone forgets to special-case it in one central place. An
explicit `@login_required` decorator on each protected route is a couple
more lines and makes what's protected greppable and impossible to get wrong
by omission for a future route — you'd have to positively add the decorator,
not remember to add an exclusion.

**Brute-force throttling: in-memory, per-IP, not a new dependency.** This
app has no reverse proxy or WAF in front of it (Tailscale only). A small
in-memory counter (attempts + window per source IP) in `gokucam/auth.py` is
enough to stop casual guessing without pulling in `flask-limiter`. It resets
on process restart, which is an acceptable trade-off for a household device
— it is not a substitute for a strong password, just friction.

**CSRF: rely on `SameSite=Lax` cookies, not per-form tokens.** All
state-changing endpoints here are already same-origin POSTs triggered by
this app's own JS (`fetch(...)`), not cross-site form posts, and the app
isn't handling payments or anything destructive-by-forgery beyond what an
authenticated household member could do anyway (pan the camera, delete a
capture). `SameSite=Lax` on the session cookie blocks the realistic CSRF
vector (a cross-site page auto-submitting a request using the browser's
cookie) for negligible complexity. Explicit CSRF tokens are the documented
upgrade path if routes ever accept cross-origin requests.

## Risks / Trade-offs

- **[Risk]** One shared password means no per-person audit trail (who
  panned the camera, who deleted a file) → **Mitigation**: acceptable for
  now per the proposal's stated scope; the session-based design doesn't
  block adding per-user accounts later.
- **[Risk]** In-memory rate limiting resets on restart, and phase 1's
  reliability work means restarts are more likely (self-healing), so a
  determined attacker could restart-and-retry → **Mitigation**: still only
  restarts on an actual process restart (not the camera/servo watchdogs,
  which don't touch the Flask process), and this is a household device
  behind Tailscale, not internet-facing; documented as a known limit, not
  silently assumed safe.
- **[Risk]** Losing `GOKU_SECRET_KEY` (e.g. rotating it) invalidates all
  sessions → **Mitigation**: expected and fine — everyone just logs in
  again; document that changing it logs everyone out.

## Migration Plan

1. Ship with auth code merged but require operators to set
   `GOKU_SECRET_KEY` and `GOKU_PORTAL_PASSWORD_HASH` before the app will
   start in non-mock mode (fail fast with a clear error instead of running
   wide open or with a guessable default).
2. In mock mode (`GOKU_MOCK_HARDWARE=1`), fall back to a dev-only default
   username/password (printed loudly to the console) so local iteration
   doesn't require generating a hash first.
3. No data migration — this is a new capability, not a change to existing
   stored data.
4. Rollback: revert the commit; nothing persisted depends on the new env
   vars existing.
