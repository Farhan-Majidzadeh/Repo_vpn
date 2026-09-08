from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from sqlalchemy import func, select

from backend.app import main, models

PLAN = {"name": "Trial", "days": 7, "traffic_gb": 2, "price": 0}
REQUESTS = [
    ("/api/plans", PLAN),
    ("/api/subscriptions", {"user_id": 1, "plan_id": 1}),
]


@pytest.mark.parametrize("path,payload", REQUESTS)
@pytest.mark.parametrize("key", [None, "", "wrong", "dev-only-change-me", b"\xff"])
def test_unauthorized_writes_have_no_effect(api, path, payload, key):
    client, _, panel, sessions = api
    headers = {} if key is None else {"X-Admin-Key": key}
    response = client.post(path, json=payload, headers=headers)
    assert response.status_code == 403
    assert response.json() == {"detail": "admin authorization required"}
    panel.create_user.assert_not_called()
    with sessions() as db:
        assert db.scalar(select(func.count()).select_from(models.Plan)) == 0
        assert db.scalar(select(func.count()).select_from(models.Subscription)) == 0


@pytest.mark.parametrize("path,payload", REQUESTS)
@pytest.mark.parametrize("secret", ["", "dev-only-change-me"])
def test_unconfigured_secret_fails_closed(api, path, payload, secret):
    client, settings, panel, _ = api
    settings.app_secret = secret
    response = client.post(path, json=payload, headers={"X-Admin-Key": secret})
    assert response.status_code == 403
    panel.create_user.assert_not_called()


def test_authorized_plan_and_mock_subscription(api):
    client, settings, panel, sessions = api
    headers = {"X-Admin-Key": settings.app_secret}
    user = client.post("/api/users", json={"telegram_id": 123}).json()
    plan_response = client.post("/api/plans", json=PLAN, headers=headers)
    assert plan_response.status_code == 200
    plan = plan_response.json()
    assert plan.items() >= PLAN.items()
    assert client.get("/api/plans").json() == [plan]

    response = client.post(
        "/api/subscriptions",
        headers=headers,
        json={"user_id": user["id"], "plan_id": plan["id"]},
    )
    assert response.status_code == 200
    sub = response.json()
    assert sub["status"] == "active"
    assert sub["traffic_limit_bytes"] == 2 * 1024**3
    assert sub["subscription_url"] == f"https://example.invalid/sub/{sub['panel_username']}"
    assert datetime.fromisoformat(sub["expires_at"]) - datetime.fromisoformat(sub["starts_at"]) == timedelta(days=7)
    panel.create_user.assert_called_once()
    with sessions() as db:
        assert db.get(models.Subscription, sub["id"]).user_id == user["id"]


def test_authorized_missing_resources(api):
    client, settings, panel, _ = api
    response = client.post(
        "/api/subscriptions",
        json={"user_id": 99, "plan_id": 99},
        headers={"X-Admin-Key": settings.app_secret},
    )
    assert response.status_code == 404
    panel.create_user.assert_not_called()


def test_admin_uses_constant_time_comparison(api):
    client, settings, _, _ = api
    supplied = "wrong"
    with patch.object(main.secrets, "compare_digest", wraps=main.secrets.compare_digest) as compare:
        response = client.post("/api/plans", json=PLAN, headers={"X-Admin-Key": supplied})
    compare.assert_called_once_with(supplied.encode("utf-8"), settings.app_secret.encode("utf-8"))
    assert response.status_code == 403
