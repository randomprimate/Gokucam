import atexit
from gokucam.camera_manager import camera
from gokucam.web import create_app
from gokucam.config import HOST, PORT

app = create_app()
atexit.register(lambda: camera.stop_mjpeg_stream())

if __name__ == "__main__":
    app.run(host=HOST, port=PORT, threaded=True)
