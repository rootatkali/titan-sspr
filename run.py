"""Entry point — imports the app factory so gunicorn can use `run:app`."""
from app import create_app

app = create_app()

if __name__ == "__main__":
    from config import Config
    cfg = Config.from_env()
    app.run(host=cfg.HOST, port=cfg.PORT, debug=cfg.DEBUG)
