from flask import Flask
from .config import Config
from .camera import Camera
from .servos import Servos

camera: Camera | None = None
servos: Servos | None = None

def create_app(config_object: type[Config] = Config) -> Flask:
    app = Flask(__name__, static_folder="static", template_folder="templates")
    app.config.from_object(config_object)

    global camera, servos
    camera = Camera(app.config)
    servos = Servos(app.config)

    from .routes.api import bp as api_bp
    from .routes.ui import bp as ui_bp
    app.register_blueprint(api_bp, url_prefix="/api")
    app.register_blueprint(ui_bp)

    app.extensions["gokucam.camera"] = camera
    app.extensions["gokucam.servos"] = servos

    @app.teardown_appcontext
    def _shutdown(_exc=None):
        # Only stop camera stream, don't center servos on every request
        try:
            camera.stop_stream()
        except Exception:
            pass

    return app
