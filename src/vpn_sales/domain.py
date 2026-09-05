from dataclasses import dataclass
from enum import StrEnum


class OrderStatus(StrEnum):
    DRAFT = "draft"
    PAYMENT_PENDING = "payment_pending"
    PAID = "paid"
    ALLOCATING = "allocating"
    PROVISIONING = "provisioning"
    ACTIVE = "active"
    PAYMENT_FAILED = "payment_failed"
    EXPIRED = "expired"
    NO_CAPACITY = "no_capacity"
    RETRY_PENDING = "retry_pending"
    MANUAL_REVIEW = "manual_review"


ALLOWED_ORDER_TRANSITIONS: dict[OrderStatus, set[OrderStatus]] = {
    OrderStatus.DRAFT: {OrderStatus.PAYMENT_PENDING},
    OrderStatus.PAYMENT_PENDING: {
        OrderStatus.PAID,
        OrderStatus.PAYMENT_FAILED,
        OrderStatus.EXPIRED,
    },
    OrderStatus.PAID: {OrderStatus.ALLOCATING},
    OrderStatus.ALLOCATING: {OrderStatus.PROVISIONING, OrderStatus.NO_CAPACITY},
    OrderStatus.PROVISIONING: {
        OrderStatus.ACTIVE,
        OrderStatus.RETRY_PENDING,
        OrderStatus.MANUAL_REVIEW,
    },
    OrderStatus.RETRY_PENDING: {OrderStatus.PROVISIONING, OrderStatus.MANUAL_REVIEW},
}


def assert_order_transition(current: OrderStatus, target: OrderStatus) -> None:
    if target not in ALLOWED_ORDER_TRANSITIONS.get(current, set()):
        raise ValueError(f"invalid order transition: {current} -> {target}")


def toman_to_provider_amount(amount_toman: int, unit: str) -> int:
    if amount_toman < 0:
        raise ValueError("amount_toman cannot be negative")
    normalized = unit.upper()
    if normalized == "TOMAN":
        return amount_toman
    if normalized == "IRR":
        return amount_toman * 10
    raise ValueError(f"unsupported provider unit: {unit}")


@dataclass(frozen=True, slots=True)
class TargetCandidate:
    id: str
    priority: int
    max_active_services: int
    active_services: int
    reserved_services: int
    healthy: bool
    compatible: bool = True

    @property
    def utilization(self) -> float:
        return (self.active_services + self.reserved_services) / self.max_active_services


def select_target(candidates: list[TargetCandidate]) -> TargetCandidate:
    eligible = [
        target
        for target in candidates
        if target.max_active_services > 0
        and target.healthy
        and target.compatible
        and target.active_services + target.reserved_services < target.max_active_services
    ]
    if not eligible:
        raise LookupError("no healthy target has available capacity")
    return min(eligible, key=lambda target: (target.priority, target.utilization, target.id))
