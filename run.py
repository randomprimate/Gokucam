#!/usr/bin/env python3
from flask import Flask, render_template
import config

# Import hardware modules
from camera import Camera
from servos import Servos

app = Flask(__name__, template_folder='templates', static_folder='static')

# Initialize hardware
camera = Camera()
servos = Servos()

# Import and register routes
from routes.api import bp, init_routes

# Initialize routes with dependencies
init_routes(camera.buffer, servos.state, servos.set_pan, servos.set_tilt)

# Register blueprint
app.register_blueprint(bp)

@app.route("/")
def index():
    return render_template("index.html", step_deg=config.STEP_DEG)

if __name__ == "__main__":
    try:
        app.run(host="0.0.0.0", port=8000, debug=True)
    finally:
        # Center servos on exit
        try:
            servos.center()
        except Exception:
            pass
        try:
            camera.stop_recording()
        except Exception:
            pass
