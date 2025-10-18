#!/usr/bin/env python3
from flask import Flask, render_template
import config

# Import unified hardware module
from hardware import Hardware

app = Flask(__name__, template_folder='templates', static_folder='static')

# Initialize hardware
hardware = Hardware()

# Import and register routes
from routes.api import bp, init_routes

# Initialize routes with dependencies
init_routes(hardware.buffer, hardware.state, hardware.set_pan, hardware.set_tilt)

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
            hardware.center()
        except Exception:
            pass
        try:
            hardware.stop_recording()
        except Exception:
            pass
