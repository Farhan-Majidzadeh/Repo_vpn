import secrets
from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.config import Settings

# Isolate import-time settings too: never load .env or a configured database.
with patch("backend.app.config.get_settings", return_value=Settings(
    _env_file=None, database_url="sqlite://", panel_kind="mock", app_secret=""
)):
    from backend.app import main, service
    from backend.app.db import get_db
    from backend.app.panels import MockAdapter


@pytest.fixture
def api(monkeypatch):
    settings = Settings(_env_file=None, database_url="sqlite://", panel_kind="mock",
                        app_secret=secrets.token_hex(32))
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    sessions = sessionmaker(bind=engine)
    panel = Mock(wraps=MockAdapter())

    def isolated_db():
        with sessions() as session:
            yield session

    monkeypatch.setattr(main, "engine", engine)
    monkeypatch.setattr(main, "get_settings", lambda: settings)
    monkeypatch.setattr(main, "get_adapter", lambda: panel)
    monkeypatch.setattr(service, "get_adapter", lambda: panel)
    main.app.dependency_overrides[get_db] = isolated_db
    try:
        with TestClient(main.app) as client:
            yield client, settings, panel, sessions
    finally:
        main.app.dependency_overrides.clear()
        engine.dispose()
