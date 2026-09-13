## 1. Config & credentials

- [x] 1.1 Add `GOKU_SECRET_KEY`, `GOKU_PORTAL_USERNAME`, `GOKU_PORTAL_PASSWORD_HASH`, `GOKU_SESSION_LIFETIME_MIN`, `GOKU_LOGIN_MAX_ATTEMPTS`, `GOKU_LOGIN_WINDOW_SEC` to `gokucam/config.py`; verify the app raises a clear startup error if `GOKU_SECRET_KEY` or `GOKU_PORTAL_PASSWORD_HASH` is missing while `MOCK_HARDWARE` is false
- [x] 1.2 In mock mode (`MOCK_HARDWARE=1`) with no password hash configured, fall back to a dev-only default username/password and print it loudly on startup; verify by running `GOKU_MOCK_HARDWARE=1 python run.py` and seeing the credentials in the log
- [x] 1.3 Write `scripts/set_portal_password.py`: prompts for a password (hidden input via `getpass`), prints the `GOKU_PORTAL_PASSWORD_HASH` value to export; verify by running it and confirming `werkzeug.security.check_password_hash` validates the printed hash against the entered password

## 2. Auth module

- [x] 2.1 Create `gokucam/auth.py` with a `login(username, password) -> bool` that checks against configured credentials via `check_password_hash`, and marks the session authenticated + permanent on success; verify with a unit-style manual check (correct vs incorrect credentials)
- [x] 2.2 Add per-IP login attempt throttling (in-memory counter, configurable max attempts / window) inside `auth.py`; verify by exceeding the limit in a quick script/curl loop and confirming subsequent attempts are rejected even with correct credentials until the window passes
- [x] 2.3 Add `login_required` decorator in `auth.py` that checks `session` for a valid, non-expired authenticated flag, and either redirects (HTML requests) or returns 401 JSON (requests expecting JSON / under `/api/`); verify by hitting a decorated dummy route with and without a session
- [x] 2.4 Add `logout()` helper that clears the session; verify the session is empty after calling it

## 3. Wire routes

- [x] 3.1 Add `@login_required` to `/`, `/gallery`, `/media/<name>`, `/api/media/<name>` (DELETE), and every `/api/pan|tilt|center|sweep|snapshot|record` route in `gokucam/web.py`; verify `/health` has no decorator and every other route does (grep for the decorator vs the route list)
- [x] 3.2 Add `GET /login` (renders login form) and `POST /login` (calls `auth.login`, redirects to `/` on success, re-renders form with an error on failure) routes; verify manually with correct and incorrect credentials
- [x] 3.3 Add `POST /logout` route wired to a "log out" control in the UI; verify a logged-in session is cleared and the next request to `/` redirects to `/login`
- [x] 3.4 Set `SESSION_COOKIE_SAMESITE="Lax"`, `SESSION_COOKIE_HTTPONLY=True`, and `PERMANENT_SESSION_LIFETIME` from config on the Flask app; verify via response headers (`Set-Cookie` attributes) after login

## 4. UI

- [x] 4.1 Create `gokucam/templates/login.html` (username/password form, error message slot, matches existing dark theme in `style.css`); verify it renders at `/login` and is reachable without a session
- [x] 4.2 Add a "Log out" link/button to `index.html` and `gallery.html` nav, calling `POST /logout`; verify it appears only when logged in is assumed (these pages are only reachable authenticated anyway) and successfully logs out

## 5. Verification

- [x] 5.1 End-to-end manual pass with `GOKU_MOCK_HARDWARE=1`: fresh session hitting `/` redirects to `/login`; logging in with the dev-mode credentials reaches the live view; pan/snapshot/gallery/logout all behave as specced; `/health` works with no session throughout
- [x] 5.2 Update `README.md` with the new env vars, the `scripts/set_portal_password.py` step, and a note that `/health` stays open by design
