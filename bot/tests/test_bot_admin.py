import asyncio
import os
import secrets
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
import pytest

with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "", "TELEGRAM_ADMIN_IDS": "123, 456",
                             "API_BASE_URL": "http://api.invalid"}):
    from bot.app import main as bot_main

bot = bot_main


@pytest.fixture
def message(monkeypatch):
    monkeypatch.setattr(bot, "ADMINS", {123, 456})
    return make_message(123, "/grant 789 2")


def make_message(user_id, text):
    return SimpleNamespace(
        from_user=SimpleNamespace(id=user_id),
        text=text,
        answer=AsyncMock(),
    )


def test_admin_rejects_non_admin(monkeypatch):
    monkeypatch.setattr(bot_main, "ADMINS", {99})
    message = make_message(10, "/admin")

    asyncio.run(bot_main.admin(message))

    message.answer.assert_not_awaited()


def test_admin_allows_admin(monkeypatch):
    monkeypatch.setattr(bot_main, "ADMINS", {99})
    message = make_message(99, "/admin")
    asyncio.run(bot_main.admin(message))

    message.answer.assert_awaited_once()


def test_grant_rejects_non_admin(monkeypatch):
    monkeypatch.setattr(bot_main, "ADMINS", {99})
    api = AsyncMock()
    monkeypatch.setattr(bot_main, "api_request", api)
    message = make_message(10, "/grant 123 1")

    asyncio.run(bot_main.grant(message))

    api.assert_not_awaited()
    message.answer.assert_not_awaited()


def test_grant_forwards_admin_key(monkeypatch):
    monkeypatch.setattr(bot_main, "ADMINS", {99})
    secret = secrets.token_hex(32)
    monkeypatch.setenv("APP_SECRET", secret)
    api = AsyncMock(side_effect=[
        {"id": 7},
        {"id": 11, "subscription_url": None},
    ])
    monkeypatch.setattr(bot_main, "api_request", api)
    message = make_message(99, "/grant 123 1")

    asyncio.run(bot_main.grant(message))

    assert api.await_count == 2
    first, second = api.await_args_list
    assert first.args == ("GET", "/api/users/by-telegram/123")
    assert second.args == ("POST", "/api/subscriptions")
    assert second.kwargs["json"] == {"user_id": 7, "plan_id": 1}
    assert second.kwargs["headers"] == {"X-Admin-Key": secret}
    message.answer.assert_awaited_once()

@pytest.mark.parametrize("handler", [bot.admin, bot.grant])
def test_empty_allowlist_denies_everyone(monkeypatch, message, handler):
    monkeypatch.setattr(bot, "ADMINS", set())
    request = AsyncMock()
    monkeypatch.setattr(bot, "api_request", request)
    asyncio.run(handler(message))
    request.assert_not_awaited()
    message.answer.assert_not_awaited()


def test_missing_secret_never_posts_subscription(monkeypatch, message):
    monkeypatch.delenv("APP_SECRET", raising=False)
    request = AsyncMock(return_value={"id": 7})
    monkeypatch.setattr(bot, "api_request", request)
    asyncio.run(bot.grant(message))
    request.assert_awaited_once_with("GET", "/api/users/by-telegram/789")
    message.answer.assert_awaited_once()


def test_malformed_grant_never_calls_api(monkeypatch, message):
    message.text = "/grant invalid"
    request = AsyncMock()
    monkeypatch.setattr(bot, "api_request", request)
    asyncio.run(bot.grant(message))
    request.assert_not_awaited()
    message.answer.assert_awaited_once()


@pytest.mark.parametrize("handler", [bot.admin, bot.grant])
def test_missing_sender_is_denied(monkeypatch, message, handler):
    message.from_user = None
    request = AsyncMock()
    monkeypatch.setattr(bot, "api_request", request)
    asyncio.run(handler(message))
    request.assert_not_awaited()
    message.answer.assert_not_awaited()


def test_api_request_forwards_header(monkeypatch):
    secret = secrets.token_hex(32)
    def respond(request):
        assert request.headers["X-Admin-Key"] == secret
        assert request.method == "POST"
        assert request.url.path == "/api/subscriptions"
        return httpx.Response(200, json={"id": 8})
    client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
    monkeypatch.setattr(bot.httpx, "AsyncClient", lambda **kwargs: client)
    assert asyncio.run(bot.api_request("POST", "/api/subscriptions", headers={"X-Admin-Key": secret})) == {"id": 8}


def test_grant_failure_does_not_expose_secret(monkeypatch, message):
    secret = secrets.token_hex(32)
    monkeypatch.setenv("APP_SECRET", secret)
    request = AsyncMock(side_effect=[{"id": 7}, RuntimeError(secret)])
    monkeypatch.setattr(bot, "api_request", request)
    asyncio.run(bot.grant(message))
    assert secret not in message.answer.call_args.args[0]
    assert "RuntimeError" in message.answer.call_args.args[0]
