from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class PanelHealth:
    healthy: bool
    latency_ms: int | None = None
    detail: str | None = None


@dataclass(frozen=True, slots=True)
class ProvisionRequest:
    idempotency_key: str
    username: str
    traffic_limit_bytes: int
    expires_at: datetime
    provider_config: dict


@dataclass(frozen=True, slots=True)
class ProvisionResult:
    external_id: str
    subscription_url: str


class PanelAdapter(ABC):
    @abstractmethod
    async def health_check(self) -> PanelHealth:
        raise NotImplementedError

    @abstractmethod
    async def create_service(self, request: ProvisionRequest) -> ProvisionResult:
        raise NotImplementedError

    @abstractmethod
    async def get_service(self, external_id: str) -> ProvisionResult:
        raise NotImplementedError

    @abstractmethod
    async def update_limits(self, external_id: str, request: ProvisionRequest) -> None:
        raise NotImplementedError

    @abstractmethod
    async def suspend_service(self, external_id: str) -> None:
        raise NotImplementedError

    @abstractmethod
    async def delete_service(self, external_id: str) -> None:
        raise NotImplementedError

    @abstractmethod
    async def get_usage_bytes(self, external_id: str) -> int:
        raise NotImplementedError


class MarzbanAdapter(PanelAdapter):
    """M1 boundary; HTTP implementation follows after test-panel access."""


class ThreeXUIAdapter(PanelAdapter):
    """M1 boundary; HTTP implementation follows after test-panel access."""
