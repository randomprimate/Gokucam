import os
from pathlib import Path
from flask import Flask, Response, request, jsonify, render_template, send_from_directory, abort, url_for
from .config import STEP_DEG, SNAP_DIR
from .camera_manager import camera
from .servo_controller import servos

app = Flask(__name__, template_folder="templates", static_folder="static")

def _safe_in_snapdir(name: str) -> Path:
    p = (SNAP_DIR / name).resolve()
    if not str(p).startswith(str(SNAP_DIR.resolve())):
        raise ValueError("Invalid path")
    return p

def create_app():
    try:
        camera.start_mjpeg_stream()
        print("[GokuCam] MJPEG stream started.")
    except Exception as e:
        print("[GokuCam] Failed to start camera:", e)
    return app

@app.route("/")
def index():
    return render_template("index.html", step=STEP_DEG)

@app.route("/stream.mjpg")
def stream():
    return Response(
        camera.mjpeg_generator(),
        mimetype="multipart/x-mixed-replace; boundary=frame"
    )

# --- Servo APIs ---
@app.route("/api/pan", methods=["POST"])
def api_pan():
    step = request.args.get("step", type=float)
    to   = request.args.get("to",   type=float)
    if to is not None:
        return jsonify(servos.set_pan(to))
    if step is not None:
        return jsonify(servos.step_pan(step))
    return jsonify(servos.state())

@app.route("/api/tilt", methods=["POST"])
def api_tilt():
    step = request.args.get("step", type=float)
    to   = request.args.get("to",   type=float)
    if to is not None:
        return jsonify(servos.set_tilt(to))
    if step is not None:
        return jsonify(servos.step_tilt(step))
    return jsonify(servos.state())

@app.route("/api/center", methods=["POST"])
def api_center():
    return jsonify(servos.center())

@app.route("/api/sweep", methods=["POST"])
def api_sweep():
    return jsonify(servos.sweep_demo())

# --- Media APIs ---
@app.route("/api/snapshot", methods=["POST"])
def api_snapshot():
    try:
        path = camera.snapshot()
        return jsonify({"saved": str(path)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/record", methods=["POST"])
def api_record():
    secs = int(request.args.get("secs", 10))
    path = camera.record_mp4(secs)
    return jsonify({"saved": str(path)})

# --- Health ---
@app.route("/health")
def health():
    return jsonify({"ok": True, **servos.state()})

@app.route("/media/<path:name>")
def media(name):
    # download/view a file from captures
    try:
        p = _safe_in_snapdir(name)
        if not p.exists():
            abort(404)
        return send_from_directory(SNAP_DIR, p.name, as_attachment=False)
    except ValueError:
        abort(400)

@app.route("/api/media/<path:name>", methods=["DELETE"])
def api_media_delete(name):
    try:
        p = _safe_in_snapdir(name)
        if p.exists():
            p.unlink()
            return jsonify({"deleted": name})
        return jsonify({"error": "not found"}), 404
    except ValueError:
        return jsonify({"error": "bad name"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/gallery")
def gallery():
    image_exts = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
    video_exts = {".mp4", ".mov", ".m4v", ".webm"}
    files = []
    for f in sorted(SNAP_DIR.glob("*"), key=lambda x: x.stat().st_mtime, reverse=True):
        ext = f.suffix.lower()
        if ext in image_exts:
            kind = "image"
        elif ext in video_exts:
            kind = "video"
        elif ext == ".json":
            kind = "json"
        else:
            kind = "file"
        files.append({
            "name": f.name,
            "url": url_for("media", name=f.name),
            "kind": kind,
            "ts": f.stat().st_mtime,
            "size": f.stat().st_size,
        })
    return render_template("gallery.html", files=files)


