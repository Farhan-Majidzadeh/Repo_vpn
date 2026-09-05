import pytest

from vpn_sales.domain import (
    OrderStatus,
    TargetCandidate,
    assert_order_transition,
    select_target,
    toman_to_provider_amount,
)


def test_toman_conversion_is_integer_and_explicit() -> None:
    assert toman_to_provider_amount(150_000, "TOMAN") == 150_000
    assert toman_to_provider_amount(150_000, "IRR") == 1_500_000


def test_invalid_order_transition_is_rejected() -> None:
    with pytest.raises(ValueError):
        assert_order_transition(OrderStatus.PAYMENT_PENDING, OrderStatus.ACTIVE)


def test_allocator_prefers_priority_then_lower_utilization() -> None:
    selected = select_target(
        [
            TargetCandidate("iran-a", 10, 100, 90, 0, True),
            TargetCandidate("iran-b", 10, 100, 30, 5, True),
            TargetCandidate("turkey-a", 20, 100, 0, 0, True),
        ]
    )
    assert selected.id == "iran-b"


def test_allocator_excludes_unhealthy_and_full_targets() -> None:
    with pytest.raises(LookupError):
        select_target(
            [
                TargetCandidate("unhealthy", 10, 100, 0, 0, False),
                TargetCandidate("full", 10, 100, 99, 1, True),
            ]
        )
