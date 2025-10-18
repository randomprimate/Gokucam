#!/usr/bin/env python3
import io, os, threading, time, subprocess
from datetime import datetime
from flask import Flask, Response, request, jsonify
from picamera2 import Picamera2
from picamera2.encoders import JpegEncoder
from picamera2.outputs import FileOutput

# --- Servo control (SunFounder HAT MCU @ 0x14) ---
try:
    from robot_hat import Servo
except Exception as e:
    raise SystemExit(f"robot-hat missing in this Python env: {e}\n"
                     "Activate your venv and install robot-hat.")

# ==== CONFIG ====
# Change these to the labels printed on your HAT if different.
PAN_PORT  = os.getenv("GOKU_PAN_PORT",  "P0")
TILT_PORT = os.getenv("GOKU_TILT_PORT", "P1")
SNAP_DIR = "/home/goku/gokucam/captures"
os.makedirs(SNAP_DIR, exist_ok=True)

# Angle limits (robot_hat.Servo uses -90..90 by default)
PAN_MIN, PAN_MAX   = -90, 90
TILT_MIN, TILT_MAX = -60, 60   # protect the ribbon: narrower tilt range is safer

STEP_DEG = 10  # keyboard/arrow step
# =================

app = Flask(__name__)

# Camera setup
picam = Picamera2()
video_cfg = picam.create_video_configuration(main={"size": (1280, 720)})
picam.configure(video_cfg)

class StreamingBuffer(io.BufferedIOBase):
    def __init__(self):
        super().__init__()
        self.frame = None
        self.condition = threading.Condition()

    def write(self, b):
        with self.condition:
            self.frame = b
            self.condition.notify_all()

buffer = StreamingBuffer()
picam.start_recording(JpegEncoder(q=85), FileOutput(buffer))

# Servo setup
pan_servo  = Servo(PAN_PORT)
tilt_servo = Servo(TILT_PORT)

# Track current angles in memory
state = {"pan": 0, "tilt": 0}
def clamp(val, lo, hi): return max(lo, min(hi, val))

def set_pan(angle):
    a = clamp(angle, PAN_MIN, PAN_MAX)
    pan_servo.angle(a)
    state["pan"] = a
    return a

def set_tilt(angle):
    a = clamp(angle, TILT_MIN, TILT_MAX)
    tilt_servo.angle(a)
    state["tilt"] = a
    return a

# Center on start
set_pan(0); set_tilt(0); time.sleep(0.3)

def mjpeg_generator():
    boundary = b'--frame'
    while True:
        with buffer.condition:
            buffer.condition.wait()
            frame = buffer.frame
        if frame is None:
            continue
        yield boundary + b'\r\nContent-Type: image/jpeg\r\nContent-Length: ' \
              + str(len(frame)).encode() + b'\r\n\r\n' + frame + b'\r\n'

@app.route("/api/snapshot", methods=["POST"])
def api_snapshot():
    """Save current frame from the MJPEG buffer as a JPEG file."""
    name = datetime.now().strftime("%Y%m%d_%H%M%S") + ".jpg"
    path = os.path.join(SNAP_DIR, name)
    with buffer.condition:
        frame = buffer.frame
    if frame:
        open(path, "wb").write(frame)
        print(f"[+] Snapshot saved: {path}")
        return jsonify({"saved": path})
    return jsonify({"error": "no frame"}), 500


@app.route("/api/record", methods=["POST"])
def api_record():
    """Record a short clip (default 10 s) using rpicam-vid."""
    secs = int(request.args.get("secs", 10))
    name = datetime.now().strftime("%Y%m%d_%H%M%S") + ".mp4"
    path = os.path.join(SNAP_DIR, name)
    print(f"[+] Recording {secs}s → {path}")
    subprocess.run(
        [
            "rpicam-vid",
            "--nopreview",
            "--width", "1280",
            "--height", "720",
            "--framerate", "25",
            "-t", str(secs * 1000),
            "-o", path,
        ],
        check=False,
    )
    return jsonify({"saved": path})

# ---- Routes ----
@app.route("/")
def index():
    # Simple UI with controls and keyboard support (arrow keys + C to center)
    return f"""
<!doctype html>
<html>
<head>
  <meta charset="utf-8"/>
  <title>GokuCam Live</title>
  <style>
    body {{ background:#111; color:#eee; font-family: system-ui, Arial; margin:0; }}
    .wrap {{ max-width: 960px; margin: 0 auto; padding: 16px; text-align:center; }}
    img {{ width: 100%; max-width: 960px; border-radius: 12px; background:#000; }}
    .controls {{ margin-top: 12px; display: grid; gap: 8px; grid-template-columns: repeat(5, minmax(0,1fr)); }}
    button {{ padding:10px 12px; border-radius:10px; border:1px solid #333; background:#222; color:#eee; cursor:pointer; }}
    button:hover {{ background:#2c2c2c; }}
    .wide {{ grid-column: span 5; }}
    .row {{ display:flex; gap:8px; justify-content:center; }}
    .pill {{ padding:6px 10px; border:1px solid #333; border-radius:999px; font-size:12px; color:#bbb; }}
    .stat {{ margin-top:8px; color:#aaa; font-size:13px; }}
    a {{ color:#6cf; }}
  </style>
</head>
<body>
  <div class="wrap">
    <h2>GokuCam Live</h2>
    <img src="/stream.mjpg" alt="Live stream" />
    <div class="stat">Pan: <span id="pan">0</span>° &nbsp; Tilt: <span id="tilt">0</span>°</div>

    <div class="controls">
      <button onclick="tilt(-1)">Tilt ↑</button>
      <div></div>
      <button onclick="center()">Center</button>
      <div></div>
      <button onclick="tilt(1)">Tilt ↓</button>

      <button onclick="pan(-1)">Pan ←</button>
      <div></div>
      <div></div>
      <div></div>
      <button onclick="pan(1)">Pan →</button>

      <button class="wide" onclick="sweep()">Sweep demo</button>
      <button class="wide" onclick="snapshot()">📸 Snapshot</button>
      <button class="wide" onclick="record()">🎥 Record 10 s</button>
    </div>

    <div class="row" style="margin-top:8px;">
      <span class="pill">Arrow keys: move</span>
      <span class="pill">C: center</span>
      <span class="pill">Shift: bigger step</span>
    </div>

    <p style="margin-top:14px;color:#888;font-size:13px;">Tip: keep servos on a stable 5V supply; share GND with the Pi.</p>
  </div>

<script>
let STEP = {STEP_DEG};
function updateState(s) {{
  if ('pan' in s)  document.getElementById('pan').innerText  = s.pan;
  if ('tilt' in s) document.getElementById('tilt').innerText = s.tilt;
}}
async function pan(dir) {{
  const r = await fetch(`/api/pan?step=${{dir*STEP}}`, {{method:'POST'}});
  updateState(await r.json());
}}
async function tilt(dir) {{
  const r = await fetch(`/api/tilt?step=${{dir*STEP}}`, {{method:'POST'}});
  updateState(await r.json());
}}
async function center() {{
  const r = await fetch('/api/center', {{method:'POST'}});
  updateState(await r.json());
}}
async function sweep() {{
  const r = await fetch('/api/sweep', {{method:'POST'}});
  updateState(await r.json());
}}
document.addEventListener('keydown', async (e) => {{
  if (e.key === 'ArrowLeft')  return pan(- (e.shiftKey?2:1));
  if (e.key === 'ArrowRight') return pan(  (e.shiftKey?2:1));
  if (e.key === 'ArrowUp')    return tilt(- (e.shiftKey?2:1));
  if (e.key === 'ArrowDown')  return tilt(  (e.shiftKey?2:1));
  if (e.key.toLowerCase() === 'c') return center();
}});
async function snapshot() {{
  const r = await fetch('/api/snapshot', {{method:'POST'}});
  const j = await r.json();
  alert(j.saved ? `Saved snapshot:\n${{j.saved}}` : 'Snapshot failed.');
}}

async function record() {{
  const r = await fetch('/api/record?secs=10', {{method:'POST'}});
  const j = await r.json();
  alert(j.saved ? `Saved clip:\n${{j.saved}}` : 'Recording failed.');
}}
</script>
</body>
</html>
"""

@app.route("/stream.mjpg")
def stream():
    return Response(mjpeg_generator(),
                    mimetype="multipart/x-mixed-replace; boundary=frame")

@app.route("/api/pan", methods=["POST"])
def api_pan():
    # pan by relative step (?step=+/-deg) or to absolute (?to=deg)
    step = request.args.get("step", type=float)
    to   = request.args.get("to",   type=float)
    if to is not None:
        a = set_pan(to)
    else:
        a = set_pan(state["pan"] + (step if step is not None else 0))
    return jsonify({"pan": a, "tilt": state["tilt"]})

@app.route("/api/tilt", methods=["POST"])
def api_tilt():
    step = request.args.get("step", type=float)
    to   = request.args.get("to",   type=float)
    if to is not None:
        a = set_tilt(to)
    else:
        a = set_tilt(state["tilt"] + (step if step is not None else 0))
    return jsonify({"pan": state["pan"], "tilt": a})

@app.route("/api/center", methods=["POST"])
def api_center():
    set_pan(0); set_tilt(0)
    return jsonify(state)

@app.route("/api/sweep", methods=["POST"])
def api_sweep():
    # gentle demo sweep; non-blocking would need threading, but short is fine
    seq_pan  = [0, -45, -90, -45, 0, 45, 90, 45, 0]
    seq_tilt = [0, -20, -40, -20, 0, 20, 40, 20, 0]
    for a in seq_pan:
        set_pan(a); time.sleep(0.25)
    for a in seq_tilt:
        set_tilt(a); time.sleep(0.25)
    return jsonify(state)

if __name__ == "__main__":
    # listen on LAN at port 8000
    try:
        app.run(host="0.0.0.0", port=8000, threaded=True)
    finally:
        # center on exit
        try:
            set_pan(0); set_tilt(0)
        except Exception:
            pass
        try:
            picam.stop_recording()
        except Exception:
            pass

