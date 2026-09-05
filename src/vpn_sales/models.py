import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from vpn_sales.db import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class Customer(Base):
    __tablename__ = "customers"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(64))
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Package(Base):
    __tablename__ = "packages"
    __table_args__ = (
        CheckConstraint("traffic_bytes > 0"),
        CheckConstraint("duration_days > 0"),
        CheckConstraint("price_toman >= 0"),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(32), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    traffic_bytes: Mapped[int] = mapped_column(BigInteger)
    duration_days: Mapped[int] = mapped_column(Integer)
    price_toman: Mapped[int] = mapped_column(BigInteger)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class ProviderAccount(Base):
    __tablename__ = "provider_accounts"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    provider_type: Mapped[str] = mapped_column(String(32))
    credential_ref: Mapped[str] = mapped_column(String(128))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class PanelInstance(Base):
    __tablename__ = "panel_instances"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    provider_account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("provider_accounts.id"))
    name: Mapped[str] = mapped_column(String(100), unique=True)
    base_url: Mapped[str] = mapped_column(String(500))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class ProvisioningTarget(Base):
    __tablename__ = "provisioning_targets"
    __table_args__ = (CheckConstraint("max_active_services > 0"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    panel_instance_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("panel_instances.id"))
    name: Mapped[str] = mapped_column(String(100), unique=True)
    provider_config: Mapped[dict] = mapped_column(JSON)
    priority: Mapped[int] = mapped_column(Integer, default=100)
    weight: Mapped[int] = mapped_column(Integer, default=1)
    max_active_services: Mapped[int] = mapped_column(Integer)
    reserved_services: Mapped[int] = mapped_column(Integer, default=0)
    active_services: Mapped[int] = mapped_column(Integer, default=0)
    health_status: Mapped[str] = mapped_column(String(32), default="unknown")
    last_health_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (CheckConstraint("amount_toman >= 0"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customers.id"))
    package_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("packages.id"))
    package_snapshot: Mapped[dict] = mapped_column(JSON)
    amount_toman: Mapped[int] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class PaymentAttempt(Base):
    __tablename__ = "payment_attempts"
    __table_args__ = (UniqueConstraint("provider", "provider_reference"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id"))
    provider: Mapped[str] = mapped_column(String(64))
    provider_reference: Mapped[str | None] = mapped_column(String(255))
    amount_toman: Mapped[int] = mapped_column(BigInteger)
    provider_amount: Mapped[int | None] = mapped_column(BigInteger)
    provider_unit: Mapped[str | None] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(32))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Allocation(Base):
    __tablename__ = "allocations"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id"), unique=True)
    target_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("provisioning_targets.id"))
    status: Mapped[str] = mapped_column(String(32))
    reserved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Service(Base):
    __tablename__ = "services"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    allocation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("allocations.id"), unique=True)
    external_id: Mapped[str | None] = mapped_column(String(255))
    idempotency_key: Mapped[str] = mapped_column(String(100), unique=True)
    subscription_url: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    traffic_limit_bytes: Mapped[int] = mapped_column(BigInteger)


class ProvisioningJob(Base):
    __tablename__ = "provisioning_jobs"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id"))
    status: Mapped[str] = mapped_column(String(32))
    attempt: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(Text)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class OutboxEvent(Base):
    __tablename__ = "outbox_events"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    event_type: Mapped[str] = mapped_column(String(100))
    aggregate_id: Mapped[uuid.UUID]
    payload: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    actor: Mapped[str] = mapped_column(String(100))
    action: Mapped[str] = mapped_column(String(100))
    aggregate_id: Mapped[uuid.UUID | None]
    details: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
