import os
from datetime import timedelta
from pathlib import Path
from flask import Flask, Response, request, jsonify, render_template, send_from_directory, abort, url_for, redirect
from .config import STEP_DEG, SNAP_DIR, SECRET_KEY, SESSION_LIFETIME_MIN
from .camera_manager import camera
from .servo_controller import servos
from . import auth

app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = SECRET_KEY or "dev-only-insecure-key-mock-hardware-only"
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    PERMANENT_SESSION_LIFETIME=timedelta(minutes=SESSION_LIFETIME_MIN),
)

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

@app.route("/login", methods=["GET"])
def login_page():
    return render_template("login.html", error=None)

@app.route("/login", methods=["POST"])
def login_submit():
    username = request.form.get("username", "")
    password = request.form.get("password", "")
    if auth.login(username, password):
        return redirect(request.args.get("next") or url_for("index"))
    return render_template("login.html", error="Wrong username, password, or too many attempts."), 401

@app.route("/logout", methods=["POST"])
def logout():
    auth.logout()
    return redirect(url_for("login_page"))

@app.route("/")
@auth.login_required
def index():
    return render_template("index.html", step=STEP_DEG)

@app.route("/stream.mjpg")
@auth.login_required
def stream():
    return Response(
        camera.mjpeg_generator(),
        mimetype="multipart/x-mixed-replace; boundary=frame"
    )

# --- Servo APIs ---
@app.route("/api/pan", methods=["POST"])
@auth.login_required
def api_pan():
    step = request.args.get("step", type=float)
    to   = request.args.get("to",   type=float)
    if to is not None:
        return jsonify(servos.set_pan(to))
    if step is not None:
        return jsonify(servos.step_pan(step))
    return jsonify(servos.state())

@app.route("/api/tilt", methods=["POST"])
@auth.login_required
def api_tilt():
    step = request.args.get("step", type=float)
    to   = request.args.get("to",   type=float)
    if to is not None:
        return jsonify(servos.set_tilt(to))
    if step is not None:
        return jsonify(servos.step_tilt(step))
    return jsonify(servos.state())

@app.route("/api/center", methods=["POST"])
@auth.login_required
def api_center():
    return jsonify(servos.center())

@app.route("/api/sweep", methods=["POST"])
@auth.login_required
def api_sweep():
    return jsonify(servos.sweep_demo())

# --- Media APIs ---
@app.route("/api/snapshot", methods=["POST"])
@auth.login_required
def api_snapshot():
    try:
        path = camera.snapshot()
        return jsonify({"saved": str(path)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/record", methods=["POST"])
@auth.login_required
def api_record():
    secs = int(request.args.get("secs", 10))
    path = camera.record_mp4(secs)
    return jsonify({"saved": str(path)})

# --- Health ---
@app.route("/health")
def health():
    healthy = camera.is_healthy() and servos.is_healthy()
    return jsonify({
        "ok": healthy,
        "camera": camera.status(),
        "servo": servos.status(),
    })

@app.route("/media/<path:name>")
@auth.login_required
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
@auth.login_required
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
@auth.login_required
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


