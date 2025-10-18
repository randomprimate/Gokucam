from flask import Blueprint, current_app, request, jsonify
from pathlib import Path
from ..utils import timestamp, write_meta

bp = Blueprint("api", __name__)

def _svc():
    cam = current_app.extensions["gokucam.camera"]
    srv = current_app.extensions["gokucam.servos"]
    snap_dir = current_app.config["SNAP_DIR"]
    return cam, srv, snap_dir

@bp.route("/pan", methods=["POST"])
def pan():
    _, servos, _ = _svc()
    step = request.args.get("step", type=float)
    to   = request.args.get("to",   type=float)
    
    # Direct servo control like working script
    if to is not None:
        new_angle = servos.set_pan(to)
    else:
        new_angle = servos.set_pan(servos.state["pan"] + (step if step is not None else 0))
    
    return jsonify({"pan": servos.state["pan"], "tilt": servos.state["tilt"]})

@bp.route("/tilt", methods=["POST"])
def tilt():
    _, servos, _ = _svc()
    step = request.args.get("step", type=float)
    to   = request.args.get("to",   type=float)
    
    # Direct servo control like working script
    if to is not None:
        new_angle = servos.set_tilt(to)
    else:
        new_angle = servos.set_tilt(servos.state["tilt"] + (step if step is not None else 0))
    
    return jsonify({"pan": servos.state["pan"], "tilt": servos.state["tilt"]})

@bp.route("/center", methods=["POST"])
def center():
    _, servos, _ = _svc()
    servos.center()
    return jsonify(servos.state)

@bp.route("/sweep", methods=["POST"])
def sweep():
    import time
    _, servos, _ = _svc()
    for a in [0,-45,-90,-45,0,45,90,45,0]:
        servos.set_pan(a);  time.sleep(0.25)
    for a in [0,-20,-40,-20,0,20,40,20,0]:
        servos.set_tilt(a); time.sleep(0.25)
    return jsonify(servos.state)

@bp.route("/snapshot", methods=["POST"])
def snapshot():
    cam, servos, snap_dir = _svc()
    frame = cam.snapshot_bytes()
    if not frame:
        return jsonify({"error":"no_frame"}), 500
    name = f"{timestamp()}.jpg"
    path = Path(snap_dir) / name
    path.write_bytes(frame)
    write_meta(path, "snapshot", servos.state["pan"], servos.state["tilt"])
    return jsonify({"saved": str(path)})


@bp.route("/record", methods=["POST"])
def record():
    """Record a short clip (default 10 s)."""
    cam, servos, snap_dir = _svc()
    secs = int(request.args.get("secs", 10))
    name = f"{timestamp()}_recording.mp4"
    path = Path(snap_dir) / name
    cam.record_clip(secs, path)
    write_meta(path, "recording", servos.state["pan"], servos.state["tilt"], {"secs": secs})
    return jsonify({"saved": str(path)})

def _snapdir() -> Path:
    """Return SNAP_DIR as a Path, even if config provided a tuple/list/str."""
    sd = current_app.config.get("SNAP_DIR")
    # handle weird cases (tuple/list from env or config loaders)
    if isinstance(sd, (list, tuple)):
        sd = sd[0] if sd else ""
    return Path(str(sd)) 

@bp.route("/delete", methods=["POST"])
def delete():
    """
    Delete a capture file (and its .json sidecar if present).
    Body JSON: {"name": "20251013_105643_recording.mp4"}
    """
    data = request.get_json(silent=True) or {}
    name = str(data.get("name", "")).strip()

    # Safety: base name only (no dirs), simple characters
    if not name or "/" in name or "\\" in name:
        return jsonify({"error": "invalid_name"}), 400

    snap_dir = _snapdir()
    target = snap_dir / name

    # Extra guard: ensure the resolved parent is exactly SNAP_DIR
    try:
        if target.resolve().parent != snap_dir.resolve():
            return jsonify({"error": "invalid_path"}), 400
    except FileNotFoundError:
        # resolve() can throw if parent doesn’t exist yet; fall back to exists check
        pass

    if not target.exists():
        return jsonify({"error": "not_found"}), 404
    try:
        target.unlink()
    except Exception as e:
        return jsonify({"error": "unlink_failed", "detail": str(e)}), 500
    sidecar = Path(str(target) + ".json")
    if sidecar.exists():
        try:
            sidecar.unlink()
        except Exception:
            pass

    return jsonify({"ok": True, "deleted": name})
