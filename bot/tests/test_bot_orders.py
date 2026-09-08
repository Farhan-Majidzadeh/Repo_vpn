import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from bot.app import main as bot


def make_message(user_id, text, *, chat_id=100, message_id=55, chat_type="private"):
    return SimpleNamespace(
        from_user=SimpleNamespace(id=user_id, username="tester", full_name="Test User") if user_id is not None else None,
        chat=SimpleNamespace(id=chat_id, type=chat_type),
        message_id=message_id,
        text=text,
        answer=AsyncMock(),
    )


def test_buy_creates_order_with_idempotency_and_admin_key(monkeypatch):
    secret = "test-secret"
    monkeypatch.setenv("APP_SECRET", secret)
    request = AsyncMock(side_effect=[
        {"id": 7},
        {
            "id": 12,
            "status": "pending",
            "plan_name": "Starter",
            "price": 500000,
            "currency": "IRR",
            "payment_instructions": "PAY HERE",
        },
    ])
    monkeypatch.setattr(bot, "api_request", request)
    message = make_message(123, "/buy 3")

    asyncio.run(bot.buy(message))

    assert request.await_count == 2
    create = request.await_args_list[1]
    assert create.args == ("POST", "/api/orders")
    assert create.kwargs["headers"] == {"X-Admin-Key": secret}
    assert create.kwargs["json"] == {
        "user_id": 7,
        "plan_id": 3,
        "idempotency_key": "telegram:100:55",
    }
    assert "PAY HERE" in message.answer.call_args.args[0]


def test_buy_rejects_group_chat_without_api_call(monkeypatch):
    request = AsyncMock()
    monkeypatch.setattr(bot, "api_request", request)
    message = make_message(123, "/buy 3", chat_type="group")

    asyncio.run(bot.buy(message))

    request.assert_not_awaited()
    message.answer.assert_awaited_once()


def test_orders_use_admin_key_and_show_subscription(monkeypatch):
    secret = "test-secret"
    monkeypatch.setenv("APP_SECRET", secret)
    request = AsyncMock(side_effect=[
        {"id": 7},
        [{"id": 12, "plan_name": "Starter", "status": "completed", "subscription_id": 9}],
    ])
    monkeypatch.setattr(bot, "api_request", request)
    message = make_message(123, "/orders")

    asyncio.run(bot.my_orders(message))

    listing = request.await_args_list[1]
    assert listing.args == ("GET", "/api/orders/by-user/7")
    assert listing.kwargs["headers"] == {"X-Admin-Key": secret}
    assert "#12" in message.answer.call_args.args[0]
    assert "#9" in message.answer.call_args.args[0]


@pytest.mark.parametrize("action,handler", [
    ("approve", bot.approve),
    ("reject", bot.reject),
    ("reconcile", bot.reconcile),
])
def test_admin_order_decisions_forward_key(monkeypatch, action, handler):
    secret = "test-secret"
    monkeypatch.setenv("APP_SECRET", secret)
    monkeypatch.setattr(bot, "ADMINS", {123})
    request = AsyncMock(return_value={"id": 5, "status": "completed"})
    monkeypatch.setattr(bot, "api_request", request)
    message = make_message(123, f"/{action} 5")

    asyncio.run(handler(message))

    request.assert_awaited_once_with(
        "POST",
        f"/api/orders/5/{action}",
        headers={"X-Admin-Key": secret},
    )
    message.answer.assert_awaited_once()


@pytest.mark.parametrize("handler", [bot.approve, bot.reject, bot.reconcile])
def test_non_admin_cannot_decide_orders(monkeypatch, handler):
    monkeypatch.setattr(bot, "ADMINS", {999})
    request = AsyncMock()
    monkeypatch.setattr(bot, "api_request", request)
    message = make_message(123, "/approve 5")

    asyncio.run(handler(message))

    request.assert_not_awaited()
    message.answer.assert_not_awaited()
