"""Configuration and read-only connectivity checks, not application feature tests."""

import pytest
from sqlalchemy import text
from sqlalchemy.engine import make_url

from app import create_app
from app import config
from app.extensions import db


@pytest.fixture
def environment(monkeypatch):
    for key in (
        "APP_ENV", "SECRET_KEY", "DEV_DATABASE_URL", "TEST_DATABASE_URL",
        "DATABASE_URL", "EMAIL_MODE", "FLASK_RUN_HOST", "FLASK_RUN_PORT",
    ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("SECRET_KEY", "test-only-secret-not-for-deployment-123456789")
    monkeypatch.setenv("DEV_DATABASE_URL", "postgresql+psycopg://postgres@127.0.0.1:5432/finset_dev")
    monkeypatch.setenv("TEST_DATABASE_URL", "postgresql+psycopg://postgres@127.0.0.1:5432/finset_test")
    return monkeypatch


@pytest.mark.parametrize("name,database", [("development", "finset_dev"), ("testing", "finset_test")])
def test_configuration_selects_its_database(environment, name, database):
    app = create_app(name, load_env=False)
    assert make_url(app.config["SQLALCHEMY_DATABASE_URI"]).database == database
    assert app.testing is (name == "testing")
    assert app.debug is (name == "development")
    assert app.config["EMAIL_MODE"] == "fake"
    assert app.config["HOST"] == "127.0.0.1"
    assert app.config["PORT"] == 5000
    assert "sqlalchemy" in app.extensions
    assert "migrate" in app.extensions


@pytest.mark.parametrize("url", [
    "postgresql+psycopg://postgres@127.0.0.1:5432/finset_dev",
    "postgresql+psycopg://different_user@localhost:5432/finset_dev",
    "postgresql+psycopg://postgres@127.0.0.1:5432/finset_test?dbname=finset_dev",
    "postgresql+psycopg://postgres@127.0.0.1:5432/finset_test?database=finset_dev",
    "postgresql+psycopg://postgres@127.0.0.1:5432/finset_test?service=development",
    "postgresql+psycopg://postgres@127.0.0.1:5432/finset_test?hostaddr=192.0.2.1",
    "postgresql+psycopg://postgres@remote.example:5432/finset_test",
    "sqlite:///:memory:",
    "not-a-database-url",
])
def test_testing_rejects_unsafe_database_urls(environment, url):
    environment.setenv("TEST_DATABASE_URL", url)
    with pytest.raises(ValueError, match="TEST_DATABASE_URL"):
        create_app("testing", load_env=False)


def test_testing_never_falls_back_to_development(environment):
    environment.delenv("TEST_DATABASE_URL")
    with pytest.raises(ValueError, match="TEST_DATABASE_URL is required"):
        create_app("testing", load_env=False)


def test_shared_development_and_testing_database_is_rejected(environment):
    environment.setenv("DEV_DATABASE_URL", "postgresql+psycopg://postgres@localhost:5432/finset_test")
    with pytest.raises(ValueError, match="DEV_DATABASE_URL"):
        create_app("testing", load_env=False)


def test_bad_url_error_does_not_expose_credentials(environment):
    environment.setenv("TEST_DATABASE_URL", "postgresql+psycopg://postgres:private-value@localhost:bad/finset_test")
    with pytest.raises(ValueError) as error:
        create_app("testing", load_env=False)
    assert "private-value" not in str(error.value)


def test_environment_overrides_local_dotenv(environment):
    environment.setattr(config, "dotenv_values", lambda path: {"FLASK_RUN_PORT": "5001"})
    environment.setenv("FLASK_RUN_PORT", "5002")
    app = create_app("testing")
    assert app.config["PORT"] == 5002


def test_production_uses_process_environment_only(environment):
    environment.setenv("DATABASE_URL", "postgresql+psycopg://postgres@database.example/finset_prod")
    app = create_app("production", load_env=False)
    assert not app.debug
    assert not app.testing
    assert app.config["SESSION_COOKIE_SECURE"]
    environment.delenv("SECRET_KEY")
    environment.setattr(config, "dotenv_values", lambda path: {"SECRET_KEY": "local-secret-that-must-not-be-used-123456789"})
    with pytest.raises(ValueError, match="SECRET_KEY"):
        create_app("production")


def test_production_never_falls_back_to_development_database(environment):
    with pytest.raises(ValueError, match="DATABASE_URL is required"):
        create_app("production", load_env=False)


@pytest.mark.parametrize("value", ["", "short", "replace-with-a-generated-secret-of-at-least-32-characters"])
def test_secret_is_required(environment, value):
    environment.setenv("SECRET_KEY", value)
    with pytest.raises(ValueError, match="SECRET_KEY"):
        create_app("testing", load_env=False)


@pytest.mark.parametrize("port", ["not-a-port", "0", "65536"])
def test_port_is_validated(environment, port):
    environment.setenv("FLASK_RUN_PORT", port)
    with pytest.raises(ValueError, match="FLASK_RUN_PORT"):
        create_app("testing", load_env=False)


def test_real_email_delivery_is_not_enabled(environment):
    environment.setenv("EMAIL_MODE", "smtp")
    with pytest.raises(ValueError, match="EMAIL_MODE"):
        create_app("testing", load_env=False)


def test_unknown_environment_is_rejected(environment):
    with pytest.raises(ValueError, match="APP_ENV"):
        create_app("unknown", load_env=False)


def test_factory_does_not_create_tables(environment):
    def unexpected_create_all(*args, **kwargs):
        pytest.fail("Application startup must not create database tables.")
    environment.setattr(db, "create_all", unexpected_create_all)
    create_app("testing", load_env=False)


@pytest.mark.integration
def test_local_test_database_connection():
    app = create_app("testing")
    with app.app_context():
        try:
            assert db.session.execute(text("SELECT current_database()")).scalar_one() == "finset_test"
        finally:
            db.session.remove()
            db.engine.dispose()
