import os
os.environ["DATABASE_URL"] = "sqlite:///./test.db"
os.environ["PANEL_KIND"] = "mock"
from fastapi.testclient import TestClient
from app.main import app


def test_health():
    with TestClient(app) as client:
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"
