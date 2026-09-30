import logging
import os
from datetime import timedelta

from flask import Flask, jsonify, redirect, request, url_for
from werkzeug.exceptions import HTTPException

import db
from config import FRONTEND_DIR, Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("vault")


def create_app(overrides: dict | None = None) -> Flask:
    app = Flask(__name__, template_folder=str(FRONTEND_DIR / "templates"), static_folder=str(FRONTEND_DIR / "static"))
    app.config.from_object(Config)
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=14)
    if overrides:
        app.config.update(overrides)
    if app.config["SECRET_KEY"] == "dev-only-change-me" and not app.config.get("TESTING"):
        logger.warning("SECRET_KEY is the default. Set a random value in .env before deploying.")

    kb = app.config["KB_DIR"]
    for sub in ("documents", "embeddings", "metadata"):
        (kb / sub).mkdir(parents=True, exist_ok=True)
    os.makedirs(os.path.dirname(app.config["DATABASE"]), exist_ok=True)
    db.init_db(app.config["DATABASE"])
    app.teardown_appcontext(db.close_db)

    from routes import auth, chat, dashboard, documents
    for module in (auth, documents, chat, dashboard):
        app.register_blueprint(module.bp)

    @app.get("/")
    def index():
        return redirect(url_for("dashboard.page"))

    def error(message: str, code: int):
        if request.path.startswith("/api/"):
            return jsonify(error=message), code
        return message, code

    @app.errorhandler(413)
    def too_large(_e):
        return error(f"File too large. Maximum size is {app.config['MAX_CONTENT_LENGTH'] // (1024 * 1024)} MB.", 413)

    @app.errorhandler(Exception)
    def unhandled(e):
        if isinstance(e, HTTPException):
            return error(e.description, e.code)
        logger.exception("Unhandled error")
        return error("Something went wrong. Please try again.", 500)

    return app


if __name__ == "__main__":
    create_app().run(host=Config.HOST, port=Config.PORT, debug=False, threaded=True)
