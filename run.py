from gokucam.web import create_app
from gokucam.config import HOST, PORT

app = create_app()

if __name__ == "__main__":
    app.run(host=HOST, port=PORT, threaded=True)
