# GokuCam

A live pan-tilt camera platform for **Raspberry Pi + SunFounder Robot HAT**.

GokuCam lets you observe, record, and study pets or experiments directly from a browser.  
It supports MJPEG live streaming, servo control, snapshots, video recording, and a local gallery — ready for both social-media and research use.

---

## ✨ Features

- **Live MJPEG stream** served via Flask  
- **Web controls** for pan/tilt + arrow-key shortcuts  
- **Snapshot capture** with pan/tilt metadata (JSON sidecar)  
- **Video recording** through Picamera2 or fallback `rpicam-vid`  
- **Local gallery** with preview / download / delete  
- **Servo control** via SunFounder Robot HAT  
- **Configurable** quality / FPS / ports via environment variables  
- **Extensible** Python modules for logging or AI add-ons  

---

## 🧰 Hardware

| Component | Notes |
|------------|-------|
| Raspberry Pi 3 B + or newer | Pi 4 / 5 recommended for 1080 p |
| Pi Camera Module (OV5647 / V3) | CSI connector |
| SunFounder Robot HAT | controls servos via I²C (0x14) |
| 5 V ≥ 2 A power supply | avoid brown-outs on servo motion |
| Optional : pan-tilt kit / IR LEDs | for night vision |

---

## ⚙️ Installation

### 1️⃣ System setup (Raspberry Pi OS Trixie)

```bash
sudo apt update
sudo apt install -y python3-picamera2 python3-flask \
                    python3-gpiozero python3-pigpio \
                    python3-smbus2 v4l-utils ffmpeg git
```

Install the SunFounder Robot HAT library:

```bash
git clone https://github.com/sunfounder/robot-hat.git
cd robot-hat && sudo python3 install.py
```

### 2️⃣ Clone + set up virtual env

```bash
git clone https://github.com/youruser/gokucam.git
cd gokucam
python3 -m venv ~/venvs/gokucam --system-site-packages
source ~/venvs/gokucam/bin/activate
pip install -r requirements.txt
```

### 3️⃣ Set a portal password

Every page and API is behind a login. Generate a password hash (the
plaintext is never stored anywhere):

```bash
python scripts/set_portal_password.py
```

Export what it prints, along with a session secret key, before running for
real:

```bash
export GOKU_SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")
export GOKU_PORTAL_USERNAME="goku"
export GOKU_PORTAL_PASSWORD_HASH="pbkdf2:sha256:..."   # from the script above
```

The app refuses to start without these two unless `GOKU_MOCK_HARDWARE=1` —
in mock mode it falls back to a dev-only username/password and prints it to
the console on startup, so local iteration doesn't need a hash first.

| Variable | Default | Purpose |
|-----------|----------|----------|
| `GOKU_SECRET_KEY` | *(required)* | signs session cookies — changing it logs everyone out |
| `GOKU_PORTAL_USERNAME` | `goku` | portal login username |
| `GOKU_PORTAL_PASSWORD_HASH` | *(required)* | from `scripts/set_portal_password.py` — never the plaintext |
| `GOKU_SESSION_LIFETIME_MIN` | `720` (12h) | inactivity timeout before re-login is required |
| `GOKU_LOGIN_MAX_ATTEMPTS` | `5` | failed logins allowed per source IP per window |
| `GOKU_LOGIN_WINDOW_SEC` | `300` | window (seconds) the attempt limit above applies over |

### 4️⃣ Run the app

```bash
python run.py
```

Then open in your browser and log in:

```bash
http://<pi-ip>:8000
```


> ✅ Tip: Run only one instance at a time.
> Use systemd for persistence and auto-restart (see below).

## 🕹️ Usage

| Action | Method |
|--------|---------|
| Log in | `/login` — required for everything below |
| View live stream | open `/` |
| Arrow keys | move camera |
| **C** | center |
| Snapshot | saves JPEG + JSON in `captures/` |
| Record (10 s default) | saves MP4 + JSON in `captures/` |
| Gallery | `/gallery` → preview / download / delete |
| Log out | button in the nav bar (`POST /logout`) |
| Biomarkers dashboard | `/biomarkers` → feeding log + snapshot/measurement history |
| Log a feeding | form on `/biomarkers` |
| Measure growth from a photo | click "Measure" on any snapshot in `/biomarkers` |

`/health` is intentionally the one endpoint that stays open with no login —
that's what the systemd watchdog and any uptime monitor should poll.

Override storage paths — and for anything beyond casual testing, move both
off the boot SD card (a Pi writing hourly snapshots + a growth database to
the same SD card it boots from is asking for a corrupted card) onto a USB
SSD, and back up `gokucam.db` offsite periodically (e.g. a cron'd `rsync`)
since it's now the record of Goku's growth history, not just cache:

```bash
export GOKU_SNAP_DIR=/mnt/storage/gokucam/captures
export GOKU_DB_PATH=/mnt/storage/gokucam/gokucam.db
```

### 📈 Measuring growth

The measurement tool computes real-world distance from two clicked points
on a photo, using a pixel-per-cm calibration — it does not detect the shell
for you. For this to mean anything, place a small fixed reference marker
(a ruler, or anything of a known length) at a fixed distance from the
camera, ideally near the basking spot. The first time you use `/biomarkers
→ Measure` on a photo containing that marker, click its two ends and enter
its real length to establish calibration; every measurement afterward uses
the most recent calibration until you recalibrate (e.g. after moving the
camera).

### 🤖 AI insights

Set `ANTHROPIC_API_KEY` to turn on two background jobs, visible on the new
`/insights` page:

- A **health check** looks at the latest photo plus recent feeding/growth
  history and writes a short observation, flagging anything that seems
  worth a person looking into. It's an assistive note from limited data,
  not a diagnosis.
- **Caption drafting** runs on two cadences — a weekly-style roundup and a
  more frequent single-moment highlight — and writes a draft Instagram
  caption from a recent photo. **Nothing posts automatically, and nothing
  ever will automatically** — GokuCam doesn't integrate with Instagram at
  all. Instead, every draft is emailed to you the moment it's created (see
  below) with the photo and caption ready to paste in, for you to post by
  hand. Approve/Reject on `/insights` is just your own "did I post this"
  tracker — it doesn't gate anything.

Health checks use a cheaper/faster model by default (they run often and
nobody reads them unless flagged); captions use a stronger one (they run
rarely and represent Goku publicly). A hard daily call cap
(`GOKU_AI_MAX_CALLS_PER_DAY`) is a cost safety net independent of the
schedule intervals — it persists across restarts, so a scheduling bug
can't quietly turn into a surprise bill. `GOKU_AI_MOCK=1` returns a canned
response instead of calling the real API, for testing without spending
budget.

### 📧 Email delivery

Every draft caption (both cadences above) and every manual recording gets
emailed to you as soon as it's ready — this is the whole "posting"
mechanism for now, deliberately simpler than integrating with Instagram's
API. Set:

```bash
export GOKU_NOTIFY_EMAIL="you@example.com"
export GOKU_SMTP_USERNAME="your-gmail-or-workspace-address@gmail.com"
export GOKU_SMTP_PASSWORD="an app password, not your real password"
```

An **app password** (Google Account → Security → 2-Step Verification →
App passwords) is required — Gmail and Google Workspace both reject a
regular account password over SMTP. Treat it as a real credential: it can
send mail as that account, though it can't do anything else and is
revocable independently at any time. `GOKU_SMTP_HOST`/`GOKU_SMTP_PORT`
default to Gmail's; override for another provider. `GOKU_SMTP_FROM`
defaults to `GOKU_SMTP_USERNAME` if unset.

Scheduled/manual **photo snapshots are not individually emailed** — those
stay browsable in `/gallery` and `/biomarkers` — only curated drafts and
video recordings reach your inbox, to avoid an hourly flood. A failed or
unconfigured email never blocks the draft or recording it was for; it just
doesn't send. `GOKU_MAIL_MOCK=1` logs what would have been sent instead of
actually sending, for testing without real SMTP credentials.

## ⚡ Performance / Tuning

Default values balance quality & CPU load for Raspberry Pi 3–4:

| Variable | Default | Purpose |
|-----------|----------|----------|
| `CAM_SIZE` | `960,540` | capture resolution |
| `FPS` | 15 | internal camera frame rate |
| `JPEG_Q` | 75 | MJPEG compression quality |
| `GOKU_MJPEG_FPS` | 10 | frames sent to the browser |
| `GOKU_PAN_PORT` | `P0` | horizontal servo port |
| `GOKU_TILT_PORT` | `P1` | vertical servo port |
| `GOKU_PAN_DIR` / `GOKU_TILT_DIR` | `1` | flip axis with –1 if reversed |
| `GOKU_KEEPALIVE` | `2` seconds | refresh servo PWM |
| `GOKU_MOCK_HARDWARE` | `0` | `1` = synthetic camera/servos, no Pi hardware needed |
| `GOKU_CAM_WATCHDOG_SEC` | `5` | how often the camera health check runs |
| `GOKU_CAM_STALE_SEC` | `8` | frame age before the stream is considered hung |
| `GOKU_SNAPSHOT_INTERVAL_MIN` | `60` | how often the scheduler takes an automatic snapshot |
| `GOKU_DB_PATH` | `./gokucam.db` | biomarker datastore (snapshots index, feeding log, measurements) |
| `ANTHROPIC_API_KEY` | *(unset = AI insights off)* | enables health checks + caption drafting |
| `GOKU_AI_MOCK` | `0` | `1` = canned AI responses, no API calls or cost |
| `GOKU_AI_HEALTH_MODEL` | `claude-haiku-4-5-20251001` | model for frequent health checks |
| `GOKU_AI_CAPTION_MODEL` | `claude-sonnet-5` | model for infrequent, public-facing captions |
| `GOKU_AI_HEALTHCHECK_INTERVAL_HOURS` | `24` | how often the health check runs |
| `GOKU_AI_ROUNDUP_INTERVAL_DAYS` | `7` | weekly-style caption draft cadence |
| `GOKU_AI_HIGHLIGHT_INTERVAL_DAYS` | `3` | single-moment caption draft cadence |
| `GOKU_AI_MAX_CALLS_PER_DAY` | `10` | hard cap across all AI calls, resets at local midnight |
| `GOKU_AI_MAX_IMAGE_DIM` | `800` | photos are downscaled to this before upload, to control cost |
| `GOKU_NOTIFY_EMAIL` | *(unset = email off)* | recipient for draft captions + recordings |
| `GOKU_SMTP_USERNAME` / `GOKU_SMTP_PASSWORD` | *(required to send)* | sender account + app password |
| `GOKU_SMTP_HOST` / `GOKU_SMTP_PORT` | `smtp.gmail.com` / `587` | override for a non-Gmail provider |
| `GOKU_SMTP_FROM` | *(= `GOKU_SMTP_USERNAME`)* | override the From address |
| `GOKU_MAIL_MOCK` | `0` | `1` = log the would-be email, don't send |

> 💡 **Tip:** If CPU usage exceeds ~70% in Grafana, reduce `FPS` or `JPEG_Q`.  
> On Raspberry Pi 3, settings like `CAM_SIZE=(854,480)` and `FPS=10` still give smooth viewing with much less heat.

---

## 🧩 Research Mode

Each snapshot or recording generates a matching `.json` metadata file:

```json
{
  "file": "20251012_103334.mp4",
  "type": "recording",
  "ts": "2025-10-12T10:33:34",
  "pan": -20,
  "tilt": 15,
  "secs": 10
}
```

---

## 🖼️ Gallery Behavior

- Displays **images and videos inline**  
- Shows **JSON and other files as labeled icons** (“JSON” / “FILE”)  
- Filename is displayed **above** the buttons and truncates gracefully when long  

---

## 🧠 Known Issues

- MJPEG + recording currently use separate camera sessions (sequential)  
- Only one Flask process should run — systemd + the `flock` guard below prevent duplicates

---

## 🛟 Reliability

The camera and servo layers never crash the process anymore if hardware isn't
ready — a missing camera or an unreachable Robot HAT puts that subsystem into
a degraded state (visible on `/health` and as a placeholder frame on the
stream) instead of taking the whole app down. Background threads keep
retrying and reconnect automatically once hardware comes back.

- **`GOKU_MOCK_HARDWARE=1`** — run with a synthetic video feed and no-op
  servos, no Pi/camera/HAT required. Use this for portal/UI/pipeline work on
  a laptop.
- **`/health`** — reports `{"ok": bool, "camera": {...}, "servo": {...}}`,
  including backend (`picamera2`/`robot_hat` vs `mock`), availability, and
  how stale the last frame is. Point an uptime monitor at this, not just at
  the port being open.
- **Camera watchdog** — if the MJPEG stream stops producing frames for
  longer than `GOKU_CAM_STALE_SEC` (default 8s), the session is restarted
  automatically. Tune with `GOKU_CAM_WATCHDOG_SEC` / `GOKU_CAM_STALE_SEC`.
- **systemd watchdog** — the app pings systemd's watchdog (via `sd_notify`)
  only while camera + servo report healthy. If it hangs instead of crashing,
  systemd notices via `WatchdogSec` (see below) and restarts it anyway —
  something `Restart=on-failure` alone can't do.

---

## 🪄 Run as systemd service (Recommended)

The unit file lives at [`systemd/gokucam.service`](systemd/gokucam.service) —
that file is the source of truth; keep this README in sync with it rather
than maintaining a second copy.

```bash
sudo cp systemd/gokucam.service /etc/systemd/system/gokucam.service
sudo systemctl daemon-reload
sudo systemctl enable --now gokucam
sudo systemctl status gokucam
```

Key choices baked into that unit:

- `Restart=always` (not just `on-failure`) — restarts even after a clean
  exit or an OOM kill, not only a crash.
- `Type=notify` + `WatchdogSec=30` — pairs with the app's `sd_notify` calls
  above so a hung-but-alive process gets restarted too.
- `flock -n /run/gokucam/gokucam.lock` — guarantees only one instance ever
  holds the camera at once, even if you `systemctl start` it twice.

### 🔒 Remote Access with Tailscale

```bash
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up --ssh
tailscale ip -4
```

Then connect securely via:

```bash
http://<tailscale-ip>:8000
```

## 🧭 Roadmap

Shipped: a login-gated portal, scheduled snapshots + a feeding log + a
calibrated growth-measurement tool, Claude-based health checks and caption
drafting, and email delivery of drafts/recordings for manual posting.

Still open:

- Motion / ML tracking, WebSocket-based pan/tilt feedback
- Environmental sensors (temperature/humidity) feeding into health checks
- Alerting (email/push) when a health check flags a concern — today it's
  visible on `/insights` only
- Direct Instagram publishing — deliberately descoped in favor of email +
  manual posting; revisit if that becomes real friction

---

## 📄 License

MIT License — fork, modify, and cite freely.  
_Created by @randomprimate to study his sulcata tortoise Goku._
