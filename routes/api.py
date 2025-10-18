from flask import Blueprint, Response, request, jsonify, render_template
from datetime import datetime
import os, subprocess, time

# Create blueprint
bp = Blueprint('routes', __name__)

# These will be injected by the main app
buffer = None
state = None
set_pan = None
set_tilt = None

def init_routes(app_buffer, app_state, app_set_pan, app_set_tilt):
    """Initialize routes with dependencies from main app"""
    global buffer, state, set_pan, set_tilt
    buffer = app_buffer
    state = app_state
    set_pan = app_set_pan
    set_tilt = app_set_tilt

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

@bp.route("/")
def index():
    return render_template("index.html", step_deg=10)

@bp.route("/stream.mjpg")
def stream():
    return Response(mjpeg_generator(),
                    mimetype="multipart/x-mixed-replace; boundary=frame")

@bp.route("/api/snapshot", methods=["POST"])
def api_snapshot():
    """Save current frame from the MJPEG buffer as a JPEG file."""
    name = datetime.now().strftime("%Y%m%d_%H%M%S") + ".jpg"
    path = os.path.join("./captures", name)
    with buffer.condition:
        frame = buffer.frame
    if frame:
        open(path, "wb").write(frame)
        print(f"[+] Snapshot saved: {path}")
        return jsonify({"saved": path})
    return jsonify({"error": "no frame"}), 500

@bp.route("/api/record", methods=["POST"])
def api_record():
    """Record a short clip (default 10 s) using rpicam-vid."""
    secs = int(request.args.get("secs", 10))
    name = datetime.now().strftime("%Y%m%d_%H%M%S") + ".mp4"
    path = os.path.join("./captures", name)
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

@bp.route("/api/pan", methods=["POST"])
def api_pan():
    # pan by relative step (?step=+/-deg) or to absolute (?to=deg)
    step = request.args.get("step", type=float)
    to   = request.args.get("to",   type=float)
    if to is not None:
        a = set_pan(to)
    else:
        a = set_pan(state["pan"] + (step if step is not None else 0))
    return jsonify({"pan": a, "tilt": state["tilt"]})

@bp.route("/api/tilt", methods=["POST"])
def api_tilt():
    step = request.args.get("step", type=float)
    to   = request.args.get("to",   type=float)
    if to is not None:
        a = set_tilt(to)
    else:
        a = set_tilt(state["tilt"] + (step if step is not None else 0))
    return jsonify({"pan": state["pan"], "tilt": a})

@bp.route("/api/center", methods=["POST"])
def api_center():
    set_pan(0); set_tilt(0)
    return jsonify(state)

@bp.route("/api/sweep", methods=["POST"])
def api_sweep():
    # gentle demo sweep; non-blocking would need threading, but short is fine
    seq_pan  = [0, -45, -90, -45, 0, 45, 90, 45, 0]
    seq_tilt = [0, -20, -40, -20, 0, 20, 40, 20, 0]
    for a in seq_pan:
        set_pan(a); time.sleep(0.25)
    for a in seq_tilt:
        set_tilt(a); time.sleep(0.25)
    return jsonify(state)
