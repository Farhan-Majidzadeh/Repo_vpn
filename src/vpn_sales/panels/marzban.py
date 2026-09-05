import asyncio
import time
from dataclasses import dataclass
from datetime import UTC
from typing import Any

import httpx

from vpn_sales.panels.base import (
    PanelAdapter,
    PanelHealth,
    PanelNotFoundError,
    PermanentPanelError,
    ProvisionRequest,
    ProvisionResult,
    RetryablePanelError,
    UnknownProvisionResultError,
)


@dataclass(frozen=True, slots=True)
class MarzbanConfig:
    base_url: str
    username: str
    password: str
    timeout_seconds: float = 10.0
    max_connections: int = 100
    max_keepalive_connections: int = 20


class MarzbanAdapter(PanelAdapter):
    """Async, connection-pooled adapter for the official Marzban REST API."""

    def __init__(
        self,
        config: MarzbanConfig,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._config = config
        self._token: str | None = None
        self._auth_lock = asyncio.Lock()
        self._client = httpx.AsyncClient(
            base_url=config.base_url.rstrip("/"),
            timeout=httpx.Timeout(config.timeout_seconds),
            limits=httpx.Limits(
                max_connections=config.max_connections,
                max_keepalive_connections=config.max_keepalive_connections,
            ),
            transport=transport,
            headers={"Accept": "application/json"},
        )

    async def _authenticate(self, *, force: bool = False) -> str:
        async with self._auth_lock:
            if self._token and not force:
                return self._token
            try:
                response = await self._client.post(
                    "/api/admin/token",
                    data={
                        "username": self._config.username,
                        "password": self._config.password,
                    },
                )
            except httpx.RequestError as exc:
                raise RetryablePanelError("Marzban authentication is unavailable") from exc
            if response.status_code in {401, 403}:
                raise PermanentPanelError("Marzban credentials were rejected")
            self._raise_for_status(response)
            token = response.json().get("access_token")
            if not token:
                raise PermanentPanelError("Marzban token response is invalid")
            self._token = str(token)
            return self._token

    async def _request(
        self,
        method: str,
        path: str,
        *,
        retry_auth: bool = True,
        **kwargs: Any,
    ) -> httpx.Response:
        token = await self._authenticate()
        headers = dict(kwargs.pop("headers", {}))
        headers["Authorization"] = f"Bearer {token}"
        try:
            response = await self._client.request(method, path, headers=headers, **kwargs)
        except httpx.RequestError as exc:
            raise RetryablePanelError(f"Marzban request failed: {method} {path}") from exc
        if response.status_code == 401 and retry_auth:
            await self._authenticate(force=True)
            return await self._request(
                method,
                path,
                retry_auth=False,
                headers=headers,
                **kwargs,
            )
        self._raise_for_status(response)
        return response

    @staticmethod
    def _raise_for_status(response: httpx.Response) -> None:
        if response.status_code < 400:
            return
        detail = response.text[:500]
        if response.status_code == 404:
            raise PanelNotFoundError(detail or "Marzban resource was not found")
        if response.status_code in {408, 425, 429} or response.status_code >= 500:
            raise RetryablePanelError(detail or "Marzban returned a transient error")
        raise PermanentPanelError(detail or "Marzban rejected the request")

    @staticmethod
    def _result(payload: dict[str, Any]) -> ProvisionResult:
        username = payload.get("username")
        subscription_url = payload.get("subscription_url")
        if not username or not subscription_url:
            raise PermanentPanelError("Marzban user response is missing required fields")
        return ProvisionResult(
            external_id=str(username),
            subscription_url=str(subscription_url),
        )

    async def health_check(self) -> PanelHealth:
        started = time.monotonic()
        try:
            await self._request("GET", "/api/system")
        except Exception as exc:  # Health checks return state instead of breaking schedulers.
            return PanelHealth(healthy=False, detail=type(exc).__name__)
        latency_ms = round((time.monotonic() - started) * 1000)
        return PanelHealth(healthy=True, latency_ms=latency_ms)

    async def create_service(self, request: ProvisionRequest) -> ProvisionResult:
        try:
            return await self.get_service(request.username)
        except PanelNotFoundError:
            pass

        if request.expires_at.tzinfo is None:
            raise PermanentPanelError("expires_at must be timezone-aware")
        config = request.provider_config
        proxies = config.get("proxies")
        if not proxies:
            raise PermanentPanelError("Marzban target requires at least one proxy protocol")
        payload = {
            "username": request.username,
            "status": "active",
            "expire": int(request.expires_at.astimezone(UTC).timestamp()),
            "data_limit": request.traffic_limit_bytes,
            "data_limit_reset_strategy": "no_reset",
            "proxies": proxies,
            "inbounds": config.get("inbounds", {}),
            "note": f"vpn-sales:{request.idempotency_key}",
        }
        try:
            response = await self._request("POST", "/api/user", json=payload)
        except (RetryablePanelError, httpx.TimeoutException) as exc:
            raise UnknownProvisionResultError(
                "Marzban create outcome is unknown; reconcile by username before retry"
            ) from exc
        except PermanentPanelError as exc:
            if "already exists" in str(exc).lower():
                return await self.get_service(request.username)
            raise
        return self._result(response.json())

    async def get_service(self, external_id: str) -> ProvisionResult:
        response = await self._request("GET", f"/api/user/{external_id}")
        return self._result(response.json())

    async def update_limits(self, external_id: str, request: ProvisionRequest) -> None:
        if request.expires_at.tzinfo is None:
            raise PermanentPanelError("expires_at must be timezone-aware")
        await self._request(
            "PUT",
            f"/api/user/{external_id}",
            json={
                "expire": int(request.expires_at.astimezone(UTC).timestamp()),
                "data_limit": request.traffic_limit_bytes,
                "status": "active",
            },
        )

    async def suspend_service(self, external_id: str) -> None:
        await self._request(
            "PUT",
            f"/api/user/{external_id}",
            json={"status": "disabled"},
        )

    async def delete_service(self, external_id: str) -> None:
        try:
            await self._request("DELETE", f"/api/user/{external_id}")
        except PanelNotFoundError:
            return

    async def get_usage_bytes(self, external_id: str) -> int:
        response = await self._request("GET", f"/api/user/{external_id}")
        used_traffic = response.json().get("used_traffic")
        if not isinstance(used_traffic, int):
            raise PermanentPanelError("Marzban user response has invalid used_traffic")
        return used_traffic

    async def aclose(self) -> None:
        await self._client.aclose()
