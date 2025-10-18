from flask import Flask, Response, request, jsonify, render_template
from .config import STEP_DEG
from .camera_manager import camera
from .servo_controller import servos

app = Flask(__name__, template_folder="templates")

def create_app():
    # Start MJPEG stream once at app creation (Flask 2.x/3.x safe)
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
