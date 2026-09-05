from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True, slots=True)
class PaymentRequest:
    order_id: str
    amount_toman: int
    callback_url: str
    description: str


@dataclass(frozen=True, slots=True)
class PaymentSession:
    provider_reference: str
    payment_url: str
    provider_amount: int
    provider_unit: str


@dataclass(frozen=True, slots=True)
class VerificationResult:
    verified: bool
    provider_reference: str
    provider_transaction_id: str | None
    provider_amount: int
    provider_unit: str


class PaymentProvider(ABC):
    @abstractmethod
    async def create_payment(self, request: PaymentRequest) -> PaymentSession:
        raise NotImplementedError

    @abstractmethod
    async def verify_callback(
        self,
        *,
        expected_order_id: str,
        expected_amount_toman: int,
        callback_data: Mapping[str, str],
    ) -> VerificationResult:
        """Verify server-to-server; callback values alone are never trusted."""
        raise NotImplementedError

    @abstractmethod
    async def inquire(self, provider_reference: str) -> VerificationResult:
        raise NotImplementedError


class PaymentProviderNotConfigured(RuntimeError):
    pass


def require_payment_provider(provider_name: str) -> None:
    if not provider_name:
        raise PaymentProviderNotConfigured(
            "A real payment provider must be configured before sales can be enabled"
        )
