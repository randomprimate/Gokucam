# GokuCam

A live pan-tilt camera platform built for Raspberry Pi + SunFounder Robot HAT.

GokuCam lets you observe, record, and study your pets or experiments directly from a browser.  
It supports MJPEG live streaming, servo control, snapshots, and video recording for both social-media and research use.

## Features

- **Live MJPEG stream** served via Flask
- **Web controls** for pan/tilt + arrow-key shortcuts
- **Snapshot capture** with pan/tilt metadata (JSON sidecar)
- **Video recording** in two presets:
  - `social` — 1080×1920 @ 30 fps (vertical)
  - `archival` — 1920×1080 @ 25 fps (research/stable)
- **Local gallery** for browsing images & videos
- **Servo control** through the SunFounder Robot HAT
- **Extensible** Python architecture for data logging or AI modules


## Hardware Requirements

- Raspberry Pi 3 B+ or newer  
- Official Pi Camera Module (e.g. OV5647 or V3)
- SunFounder Robot HAT or similar (for pan/tilt)
- 5 V ≥ 2 A power supply (servos draw bursts)
- Optional: micro-servo pan/tilt kit, IR LEDs for night vision


## Installation

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

### 2️⃣ Clone this repository

```bash
git clone https://github.com/youruser/gokucam.git
cd gokucam
```

(Optional) Create a virtual environment that can still access Pi system packages:

```bash
python3 -m venv ~/venvs/gokucam --system-site-packages
source ~/venvs/gokucam/bin/activate
pip install -r requirements.txt
```

### 3️⃣ Run the app

```bash
python3 gokucam_live.py
```

Visit your Pi’s IP:

```
http://<pi-ip>:8000
```

## Usage

| Action   |      Method      |
|----------|:-------------:|
| View live stream |  Open `/` in browser |
| Arrow keys |  Move camera   |
| C key | Center |
| Snapshot | Saves a JPEG + JSON metadata in `captures/` |
| Record (Social / Archival) | Saves MP4 + JSON metadata in `captures/` |
| Gallery	 | `/gallery` to browse photos/videos |

All captures are saved in `captures/` next to the script.

You can override the path with:

```bash
export GOKU_SNAP_DIR=/mnt/storage/gokucam
```

## Research Mode

Each snapshot or recording is accompanied by a JSON file, e.g.:
```json

{
  "file": "20251012_103334_archival.mp4",
  "type": "recording",
  "ts": "2025-10-12T10:33:34",
  "pan": -20,
  "tilt": 15,
  "mode": "archival",
  "secs": 10
}
```

This makes it easy to correlate behavior with orientation, time, or conditions.

## Known Issues

- Recording may fail if the MJPEG stream still owns the camera.
  - (Work in progress: integrate recording and streaming into one Picamera2 pipeline.)
- Gallery thumbnails might 404 on some paths (fixed in next patch).
  - Workaround: open files directly under /captures/filename.

## Roadmap
- Unified Picamera2 stream + recording
- Motion detection / event tagging
- Cloud or Tailscale integration for private access
- Data export for ethology / behavioral research
- WebSocket-based controls (real-time pan/tilt feedback)
- ML-based tracking (face/animal follow)

## Remote Access with Tailscale
```bash
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up --ssh
tailscale ip -4
```
Then reach your cam securely via:
```
http://<tailscale-ip>:8000
```

## License

MIT License — feel free to fork, modify, and cite the project. (Lic file available in this repo)

--- 

__Created by @randomprimate, originally to study his sulcata tortoise Goku.__