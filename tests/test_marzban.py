import json
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from vpn_sales.panels import (
    MarzbanAdapter,
    MarzbanConfig,
    ProvisionRequest,
    UnknownProvisionResultError,
)


def request() -> ProvisionRequest:
    return ProvisionRequest(
        idempotency_key="order-123",
        username="vpn_order_123",
        traffic_limit_bytes=10 * 1024**3,
        expires_at=datetime.now(UTC) + timedelta(days=30),
        provider_config={
            "proxies": {"vless": {}},
            "inbounds": {"vless": ["VLESS TCP REALITY"]},
        },
    )


@pytest.mark.asyncio
async def test_create_authenticates_reconciles_and_creates() -> None:
    seen: list[tuple[str, str]] = []

    def handler(http_request: httpx.Request) -> httpx.Response:
        seen.append((http_request.method, http_request.url.path))
        if http_request.url.path == "/api/admin/token":
            return httpx.Response(200, json={"access_token": "token"})
        assert http_request.headers["Authorization"] == "Bearer token"
        if http_request.method == "GET":
            return httpx.Response(404, json={"detail": "User not found"})
        payload = json.loads(http_request.content)
        assert payload["data_limit"] == 10 * 1024**3
        assert payload["note"] == "vpn-sales:order-123"
        return httpx.Response(
            200,
            json={
                "username": "vpn_order_123",
                "subscription_url": "https://panel.example/sub/token",
            },
        )

    adapter = MarzbanAdapter(
        MarzbanConfig("https://panel.example", "admin", "secret"),
        transport=httpx.MockTransport(handler),
    )
    try:
        result = await adapter.create_service(request())
    finally:
        await adapter.aclose()

    assert result.external_id == "vpn_order_123"
    assert seen == [
        ("POST", "/api/admin/token"),
        ("GET", "/api/user/vpn_order_123"),
        ("POST", "/api/user"),
    ]


@pytest.mark.asyncio
async def test_create_is_idempotent_when_user_already_exists() -> None:
    def handler(http_request: httpx.Request) -> httpx.Response:
        if http_request.url.path == "/api/admin/token":
            return httpx.Response(200, json={"access_token": "token"})
        if http_request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "username": "vpn_order_123",
                    "subscription_url": "https://panel.example/sub/existing",
                },
            )
        raise AssertionError("adapter attempted to create a duplicate user")

    adapter = MarzbanAdapter(
        MarzbanConfig("https://panel.example", "admin", "secret"),
        transport=httpx.MockTransport(handler),
    )
    try:
        result = await adapter.create_service(request())
    finally:
        await adapter.aclose()

    assert result.subscription_url.endswith("/existing")


@pytest.mark.asyncio
async def test_uncertain_create_requires_reconciliation() -> None:
    def handler(http_request: httpx.Request) -> httpx.Response:
        if http_request.url.path == "/api/admin/token":
            return httpx.Response(200, json={"access_token": "token"})
        if http_request.method == "GET":
            return httpx.Response(404, json={"detail": "User not found"})
        raise httpx.ReadTimeout("timeout after request write", request=http_request)

    adapter = MarzbanAdapter(
        MarzbanConfig("https://panel.example", "admin", "secret"),
        transport=httpx.MockTransport(handler),
    )
    try:
        with pytest.raises(UnknownProvisionResultError):
            await adapter.create_service(request())
    finally:
        await adapter.aclose()
