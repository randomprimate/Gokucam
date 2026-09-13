import atexit
from gokucam.camera_manager import camera
from gokucam.servo_controller import servos
from gokucam.scheduler import scheduler
from gokucam.web import create_app
from gokucam.config import HOST, PORT
from gokucam import sdnotify

app = create_app()
scheduler.start()
atexit.register(lambda: camera.stop_mjpeg_stream())
atexit.register(scheduler.stop)


def _healthy() -> bool:
    return camera.is_healthy() and servos.is_healthy()


sdnotify.ready()
sdnotify.start_watchdog_loop(_healthy)

if __name__ == "__main__":
    app.run(host=HOST, port=PORT, threaded=True)
