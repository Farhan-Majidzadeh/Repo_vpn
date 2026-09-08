from unittest.mock import Mock

from backend.app.panels import MockAdapter


def headers(settings):
    return {"X-Admin-Key": settings.app_secret}


def seed(client, settings):
    user = client.post("/api/users", json={"telegram_id": 9001, "display_name": "Buyer"}).json()
    plan = client.post(
        "/api/plans",
        headers=headers(settings),
        json={"name": "Starter", "days": 30, "traffic_gb": 20, "price": 500000, "currency": "IRR"},
    ).json()
    return user, plan


def create_order(client, settings, user, plan, key="order-1"):
    return client.post(
        "/api/orders",
        headers=headers(settings),
        json={"user_id": user["id"], "plan_id": plan["id"], "idempotency_key": key},
    )


def test_order_mutations_require_admin(api):
    client, settings, _, _ = api
    user, plan = seed(client, settings)
    response = client.post(
        "/api/orders",
        json={"user_id": user["id"], "plan_id": plan["id"], "idempotency_key": "denied"},
    )
    assert response.status_code == 403
    assert client.get(f"/api/orders/by-user/{user['id']}").status_code == 403


def test_create_order_is_idempotent_and_snapshots_plan(api):
    client, settings, panel, _ = api
    settings.payment_instructions = "TEST PAYMENT INSTRUCTIONS"
    user, plan = seed(client, settings)

    first = create_order(client, settings, user, plan)
    second = create_order(client, settings, user, plan)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]
    assert first.json()["status"] == "pending"
    assert first.json()["plan_name"] == "Starter"
    assert first.json()["price"] == 500000
    assert first.json()["payment_instructions"] == "TEST PAYMENT INSTRUCTIONS"
    panel.create_user.assert_not_called()

    listed = client.get(f"/api/orders/by-user/{user['id']}", headers=headers(settings))
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [first.json()["id"]]


def test_approve_order_provisions_once(api):
    client, settings, panel, _ = api
    user, plan = seed(client, settings)
    order = create_order(client, settings, user, plan).json()

    first = client.post(f"/api/orders/{order['id']}/approve", headers=headers(settings))
    second = client.post(f"/api/orders/{order['id']}/approve", headers=headers(settings))

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["status"] == "completed"
    assert first.json()["subscription_id"] is not None
    assert second.json()["subscription_id"] == first.json()["subscription_id"]
    panel.create_user.assert_called_once()
    assert panel.create_user.call_args.args[0] == f"order_{order['id']}"


def test_reject_is_idempotent_and_never_provisions(api):
    client, settings, panel, _ = api
    user, plan = seed(client, settings)
    order = create_order(client, settings, user, plan).json()

    first = client.post(f"/api/orders/{order['id']}/reject", headers=headers(settings))
    second = client.post(f"/api/orders/{order['id']}/reject", headers=headers(settings))
    approve = client.post(f"/api/orders/{order['id']}/approve", headers=headers(settings))

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["status"] == "rejected"
    assert approve.status_code == 409
    panel.create_user.assert_not_called()


def test_failed_approval_can_be_reconciled(api):
    client, settings, panel, _ = api
    user, plan = seed(client, settings)
    order = create_order(client, settings, user, plan).json()

    panel.create_user.side_effect = RuntimeError("temporary panel failure")
    failed = client.post(f"/api/orders/{order['id']}/approve", headers=headers(settings))
    assert failed.status_code == 502

    panel.create_user = Mock(wraps=MockAdapter().create_user)
    recovered = client.post(f"/api/orders/{order['id']}/reconcile", headers=headers(settings))
    assert recovered.status_code == 200
    assert recovered.json()["status"] == "completed"
    assert recovered.json()["subscription_id"] is not None
