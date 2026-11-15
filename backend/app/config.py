"""Environment configuration with explicit PostgreSQL database separation."""

import os
from pathlib import Path

from dotenv import dotenv_values
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError


ENV_FILE = Path(__file__).resolve().parents[1] / ".env"


class Config:
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "connect_args": {"connect_timeout": 15},
    }
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"


class DevelopmentConfig(Config):
    DEBUG = True
    TESTING = False


class TestingConfig(Config):
    DEBUG = False
    TESTING = True


class ProductionConfig(Config):
    DEBUG = False
    TESTING = False
    SESSION_COOKIE_SECURE = True


CONFIGURATIONS = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}


def validate_database_url(value, variable, expected_database=None):
    if not value:
        raise ValueError(f"{variable} is required.")
    try:
        url = make_url(value)
        # Accessing the port also validates its syntax.
        url.port
    except (ArgumentError, ValueError, TypeError):
        raise ValueError(f"{variable} must be a valid PostgreSQL connection URL.") from None

    if url.drivername != "postgresql+psycopg":
        raise ValueError(f"{variable} must use postgresql+psycopg.")
    if not url.host or not url.username or not url.database:
        raise ValueError(f"{variable} must specify a host, role, and database.")

    # libpq query parameters can override a URL's database or connection target.
    allowed_options = {"sslmode", "sslrootcert", "connect_timeout", "application_name"}
    if set(url.query) - allowed_options:
        raise ValueError(f"{variable} contains unsupported connection options.")
    if expected_database is not None:
        if url.database != expected_database:
            raise ValueError(f"{variable} must use the database '{expected_database}'.")
        if url.host not in {"127.0.0.1", "localhost", "::1"}:
            raise ValueError(f"{variable} must use the local PostgreSQL server.")
    return value


def configure_app(app, environment=None, *, load_env=True):
    # Read local values without mutating the process environment between app instances.
    values = dict(dotenv_values(ENV_FILE)) if load_env else {}
    values.update(os.environ)
    name = environment or values.get("APP_ENV", "development")
    if name not in CONFIGURATIONS:
        raise ValueError("APP_ENV must be development, testing, or production.")
    if name == "production":
        values = dict(os.environ)

    secret_key = values.get("SECRET_KEY", "")
    if not secret_key or len(secret_key) < 32 or secret_key.startswith("replace-"):
        raise ValueError("SECRET_KEY must be a generated secret of at least 32 characters.")
    if values.get("EMAIL_MODE", "fake") != "fake":
        raise ValueError("EMAIL_MODE must remain fake; email delivery is not implemented.")
    try:
        port = int(values.get("FLASK_RUN_PORT", "5000"))
    except (ValueError, TypeError):
        raise ValueError("FLASK_RUN_PORT must be an integer from 1 to 65535.") from None
    if not 1 <= port <= 65535:
        raise ValueError("FLASK_RUN_PORT must be an integer from 1 to 65535.")

    if name == "testing":
        database_url = validate_database_url(
            values.get("TEST_DATABASE_URL"), "TEST_DATABASE_URL", "finset_test"
        )
        if values.get("DEV_DATABASE_URL"):
            validate_database_url(values["DEV_DATABASE_URL"], "DEV_DATABASE_URL", "finset_dev")
    elif name == "development":
        database_url = validate_database_url(
            values.get("DEV_DATABASE_URL"), "DEV_DATABASE_URL", "finset_dev"
        )
    else:
        database_url = validate_database_url(values.get("DATABASE_URL"), "DATABASE_URL")

    app.config.from_object(CONFIGURATIONS[name])
    app.config.update(
        APP_ENV=name,
        SECRET_KEY=secret_key,
        SQLALCHEMY_DATABASE_URI=database_url,
        HOST=values.get("FLASK_RUN_HOST", "127.0.0.1"),
        PORT=port,
        EMAIL_MODE="fake",
    )
