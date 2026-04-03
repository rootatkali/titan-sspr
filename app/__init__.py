"""Flask application factory."""
from __future__ import annotations

import os

from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix

from app.extensions import Base, flask_session, limiter
import app.extensions as ext


def create_app(test_config: dict | None = None) -> Flask:
    flask_app = Flask(__name__, template_folder="templates")

    # ── Configuration ────────────────────────────────────────────────────────
    if test_config is not None:
        flask_app.config.update(test_config)
    else:
        from config import Config
        cfg = Config.from_env()
        flask_app.config.from_mapping(vars(cfg))

    # ── Proxy fix (real IPs for Flask-Limiter behind nginx) ──────────────────
    flask_app.wsgi_app = ProxyFix(flask_app.wsgi_app, x_for=1, x_proto=1)

    # ── Extensions ───────────────────────────────────────────────────────────
    # Skip Flask-Session in TESTING mode; use default Flask cookie session.
    if not flask_app.config.get("TESTING"):
        flask_session.init_app(flask_app)
    limiter.init_app(flask_app)

    # ── Database (SQLAlchemy) ─────────────────────────────────────────────────
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    db_uri = flask_app.config.get("SQLALCHEMY_DATABASE_URI", "sqlite:///data/audit.db")

    # Ensure the data/ directory exists for SQLite
    if db_uri.startswith("sqlite:///") and not db_uri.startswith("sqlite:///:"):
        db_path = db_uri[len("sqlite:///"):]
        os.makedirs(os.path.dirname(db_path) if os.path.dirname(db_path) else ".", exist_ok=True)

    engine = create_engine(
        db_uri,
        connect_args={"check_same_thread": False} if "sqlite" in db_uri else {},
    )
    ext.db_engine = engine
    ext.DbSession = sessionmaker(bind=engine)

    # Enable WAL mode for SQLite
    if "sqlite" in db_uri:
        from sqlalchemy import text, event

        @event.listens_for(engine, "connect")
        def set_wal(dbapi_con, _):
            dbapi_con.execute("PRAGMA journal_mode=WAL")

    # Create tables
    from app.models import audit_log  # noqa: F401 — registers model with Base
    Base.metadata.create_all(engine)

    # ── Blueprints ────────────────────────────────────────────────────────────
    from app.blueprints.sspr import sspr_bp
    from app.blueprints.admin import admin_bp

    flask_app.register_blueprint(sspr_bp)
    flask_app.register_blueprint(admin_bp)

    return flask_app
