from flask import Blueprint, render_template, current_app, Response, send_from_directory
import os, datetime

bp = Blueprint("ui", __name__)

def _scan_items(snap_dir):
    items = []
    all_files = {}
    for f in os.listdir(snap_dir):
        if not f.lower().endswith((".jpg", ".mp4", ".avi", ".json")):
            continue
        full = os.path.join(snap_dir, f)
        try:
            st = os.stat(full)
        except FileNotFoundError:
            continue
        mtime = datetime.datetime.fromtimestamp(st.st_mtime)
        all_files[f] = {
            "name": f,
            "url": f"/captures/{f}",
            "ext": os.path.splitext(f)[1].lower(),
            "size": st.st_size,
            "mtime": mtime,
            "date": mtime.strftime("%Y-%m-%d"),
            "time": mtime.strftime("%H:%M:%S"),
        }
    
    for f, item in all_files.items():
        if item["ext"] == ".json":
            continue 
        base_name = os.path.splitext(f)[0]
        json_file = base_name + ".json"
        has_sidecar = json_file in all_files
        
        item["has_sidecar"] = has_sidecar
        items.append(item)
    
    items.sort(key=lambda x: x["mtime"], reverse=True)
    grouped = {}
    for it in items:
        grouped.setdefault(it["date"], []).append(it)
    return [(d, grouped[d]) for d in sorted(grouped.keys(), reverse=True)]

@bp.get("/")
def index():
    return render_template("index.html",
                           step=current_app.config["STEP_DEG"])

@bp.get("/stream.mjpg")
def stream():
    print("[STREAM] New stream connection started")
    cam = current_app.extensions["gokucam.camera"]
    headers = {
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0",
    }
    try:
        return Response(cam.mjpeg_frames(),
                        headers=headers,
                        mimetype="multipart/x-mixed-replace; boundary=frame")
    except Exception as e:
        print(f"[STREAM] Stream connection error: {e}")
        raise

@bp.get("/gallery")
def gallery():
    snap_dir = current_app.config["SNAP_DIR"]
    groups = _scan_items(snap_dir)
    return render_template("gallery.html", groups=groups)

@bp.get("/captures/<path:fname>")
def captures(fname):
    return send_from_directory(current_app.config["SNAP_DIR"], fname)
