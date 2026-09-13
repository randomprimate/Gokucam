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

### 3️⃣ Run the app

```bash
python run.py
```

Then open in your browser:

```bash
http://<pi-ip>:8000
```


> ✅ Tip: Run only one instance at a time.
> Use systemd for persistence and auto-restart (see below).

## 🕹️ Usage

| Action | Method |
|--------|---------|
| View live stream | open `/` |
| Arrow keys | move camera |
| **C** | center |
| Snapshot | saves JPEG + JSON in `captures/` |
| Record (10 s default) | saves MP4 + JSON in `captures/` |
| Gallery | `/gallery` → preview / download / delete |

Override storage path:

```bash
export GOKU_SNAP_DIR=/mnt/storage/gokucam
```

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

- Unified Picamera2 stream + recording pipeline  
- Motion / ML tracking  
- WebSocket-based pan/tilt feedback  
- Cloud or Tailscale sharing  
- Data export for ethology / behavioral research  
- Modular AI extensions (object detection, pet tracking, etc.)

---

## 📄 License

MIT License — fork, modify, and cite freely.  
_Created by @randomprimate to study his sulcata tortoise Goku._
