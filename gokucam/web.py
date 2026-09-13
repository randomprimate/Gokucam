import os
from datetime import timedelta, datetime
from pathlib import Path
from flask import Flask, Response, request, jsonify, render_template, send_from_directory, abort, url_for, redirect
from .config import STEP_DEG, SNAP_DIR, SECRET_KEY, SESSION_LIFETIME_MIN
from .camera_manager import camera
from .servo_controller import servos
from . import auth
from . import store

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
        store.record_snapshot(str(path), reason="manual")
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

# --- Biomarkers ---
def _snapshot_media_url(path_str: str) -> str:
    return url_for("media", name=Path(path_str).name)

def _prepared_history():
    history = store.recent_history()
    for e in history:
        e["when"] = datetime.fromtimestamp(e["ts"]).strftime("%Y-%m-%d %H:%M")
        if e["kind"] == "snapshot":
            e["url"] = _snapshot_media_url(e["path"])
    return history

@app.route("/biomarkers")
@auth.login_required
def biomarkers():
    return render_template("biomarkers.html", history=_prepared_history(),
                            calibration=store.get_latest_calibration(), error=None)

@app.route("/api/feeding", methods=["POST"])
@auth.login_required
def api_feeding():
    try:
        store.log_feeding(
            food=request.form.get("food", ""),
            portion=request.form.get("portion", ""),
            note=request.form.get("note", ""),
        )
    except ValueError as e:
        return render_template("biomarkers.html", history=_prepared_history(),
                                calibration=store.get_latest_calibration(), error=str(e)), 400
    return redirect(url_for("biomarkers"))

@app.route("/biomarkers/measure/<int:snapshot_id>")
@auth.login_required
def measure_page(snapshot_id):
    snap = store.get_snapshot(snapshot_id)
    if not snap:
        abort(404)
    calibration = store.get_latest_calibration()
    return render_template(
        "measure.html",
        snapshot_id=snapshot_id,
        image_url=_snapshot_media_url(snap["path"]),
        has_calibration=calibration is not None,
    )

@app.route("/api/calibration", methods=["POST"])
@auth.login_required
def api_calibration():
    data = request.get_json(silent=True) or {}
    try:
        px_distance = float(data["px_distance"])
        real_cm = float(data["real_cm"])
        snapshot_id = data.get("snapshot_id")
        if px_distance <= 0 or real_cm <= 0:
            raise ValueError
    except (KeyError, TypeError, ValueError):
        return jsonify({"error": "px_distance and real_cm must be positive numbers"}), 400
    cal_id = store.set_calibration(px_distance / real_cm, snapshot_id=snapshot_id)
    return jsonify({"calibration_id": cal_id, "px_per_cm": px_distance / real_cm})

@app.route("/api/measurement", methods=["POST"])
@auth.login_required
def api_measurement():
    data = request.get_json(silent=True) or {}
    calibration = store.get_latest_calibration()
    if not calibration:
        return jsonify({"error": "no calibration established yet — calibrate against a known distance first"}), 400
    try:
        px_distance = float(data["px_distance"])
        snapshot_id = data.get("snapshot_id")
        if px_distance <= 0:
            raise ValueError
    except (KeyError, TypeError, ValueError):
        return jsonify({"error": "px_distance must be a positive number"}), 400
    cm_distance = px_distance / calibration["px_per_cm"]
    m_id = store.record_measurement(snapshot_id, calibration["id"], px_distance, cm_distance)
    return jsonify({"measurement_id": m_id, "cm_distance": cm_distance})


