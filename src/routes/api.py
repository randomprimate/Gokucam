from flask import Blueprint, current_app, request, jsonify
from pathlib import Path
from ..utils import timestamp, write_meta

bp = Blueprint("api", __name__)

def _svc():
    cam = current_app.extensions["gokucam.camera"]
    srv = current_app.extensions["gokucam.servos"]
    snap_dir = current_app.config["SNAP_DIR"]
    return cam, srv, snap_dir

@bp.post("/pan")
def pan():
    _, servos, _ = _svc()
    step = request.args.get("step", type=float)
    to   = request.args.get("to",   type=float)
    a = servos.set_pan(to if to is not None else servos.state["pan"] + (step or 0))
    return jsonify({"pan": a, "tilt": servos.state["tilt"]})

@bp.post("/tilt")
def tilt():
    _, servos, _ = _svc()
    step = request.args.get("step", type=float)
    to   = request.args.get("to",   type=float)
    a = servos.set_tilt(to if to is not None else servos.state["tilt"] + (step or 0))
    return jsonify({"pan": servos.state["pan"], "tilt": a})

@bp.post("/center")
def center():
    _, servos, _ = _svc()
    servos.center()
    return jsonify(servos.state)

@bp.post("/sweep")
def sweep():
    import time
    _, servos, _ = _svc()
    for a in [0,-45,-90,-45,0,45,90,45,0]:
        servos.set_pan(a);  time.sleep(0.25)
    for a in [0,-20,-40,-20,0,20,40,20,0]:
        servos.set_tilt(a); time.sleep(0.25)
    return jsonify(servos.state)

@bp.post("/snapshot")
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

@bp.post("/record")
def record():
    cam, servos, snap_dir = _svc()
    secs = int(request.args.get("secs", 10))
    mode = request.args.get("mode", "archival")
    name = f"{timestamp()}_{mode}.mp4"
    path = Path(snap_dir) / name
    cam.record_clip(mode, secs, path)
    write_meta(path, "recording", servos.state["pan"], servos.state["tilt"],
               {"mode": mode, "secs": secs})
    return jsonify({"saved": str(path)})
