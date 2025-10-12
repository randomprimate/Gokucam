from flask import Blueprint, render_template, current_app, Response, send_from_directory
import os

bp = Blueprint("ui", __name__)

@bp.get("/")
def index():
    return render_template("index.html",
                           step=current_app.config["STEP_DEG"])

@bp.get("/stream.mjpg")
def stream():
    cam = current_app.extensions["gokucam.camera"]
    return Response(cam.mjpeg_frames(),
                    mimetype="multipart/x-mixed-replace; boundary=frame")

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
