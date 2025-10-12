from flask import Blueprint, render_template, current_app, Response, send_from_directory, make_response
import os

bp = Blueprint("ui", __name__)

@bp.get("/")
def index():
    return render_template("index.html",
                           step=current_app.config["STEP_DEG"])

@bp.get("/stream.mjpg")
def stream():
    cam = current_app.extensions["gokucam.camera"]
    headers = {
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0",
    }
    return Response(cam.mjpeg_frames(),
                    headers=headers,
                    mimetype="multipart/x-mixed-replace; boundary=frame")

@bp.get("/debug.jpg")
def debug_jpg():
    cam = current_app.extensions["gokucam.camera"]
    frame = cam.snapshot_bytes()
    if not frame:
        return "no frame", 503
    resp = make_response(frame)
    resp.headers["Content-Type"] = "image/jpeg"
    resp.headers["Cache-Control"] = "no-cache"
    return resp

@bp.get("/gallery")
def gallery():
    snap_dir = current_app.config["SNAP_DIR"]
    items = [f for f in os.listdir(snap_dir)
             if f.lower().endswith((".jpg",".mp4",".avi",".json"))]
    items.sort(reverse=True)
    return render_template("gallery.html", items=items)

@bp.get("/captures/<path:fname>")
def captures(fname):
    return send_from_directory(current_app.config["SNAP_DIR"], fname)
