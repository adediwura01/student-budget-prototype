"""FinSet application factory; model registration never creates database tables."""

from pathlib import Path

from flask import Flask

from .config import configure_app
from .extensions import db, migrate

# Load declarations into db.metadata before Flask-Migrate inspects it.
from . import models


def create_app(environment=None, *, load_env=True):
    """Configure the application and bind extensions without running migrations."""
    app = Flask(__name__, static_folder=None)
    configure_app(app, environment, load_env=load_env)
    db.init_app(app)
    migrate.init_app(app, db, directory=str(Path(__file__).resolve().parents[1] / "migrations"))
    return app
