"""Initial M1 schema."""

import sqlalchemy as sa
from alembic import op

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "customers",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False, unique=True),
        sa.Column("username", sa.String(64)),
        sa.Column("is_blocked", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "packages",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("code", sa.String(32), nullable=False, unique=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("traffic_bytes", sa.BigInteger(), nullable=False),
        sa.Column("duration_days", sa.Integer(), nullable=False),
        sa.Column("price_toman", sa.BigInteger(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.CheckConstraint("traffic_bytes > 0"),
        sa.CheckConstraint("duration_days > 0"),
        sa.CheckConstraint("price_toman >= 0"),
    )
    op.create_table(
        "provider_accounts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("provider_type", sa.String(32), nullable=False),
        sa.Column("credential_ref", sa.String(128), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_table(
        "panel_instances",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("provider_account_id", sa.Uuid(), sa.ForeignKey("provider_accounts.id"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("base_url", sa.String(500), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_table(
        "provisioning_targets",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("panel_instance_id", sa.Uuid(), sa.ForeignKey("panel_instances.id"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("provider_config", sa.JSON(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("weight", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("max_active_services", sa.Integer(), nullable=False),
        sa.Column("reserved_services", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("active_services", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("health_status", sa.String(32), nullable=False, server_default="unknown"),
        sa.Column("last_health_at", sa.DateTime(timezone=True)),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.CheckConstraint("max_active_services > 0"),
    )
    op.create_table(
        "orders",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("customer_id", sa.Uuid(), sa.ForeignKey("customers.id"), nullable=False),
        sa.Column("package_id", sa.Uuid(), sa.ForeignKey("packages.id"), nullable=False),
        sa.Column("package_snapshot", sa.JSON(), nullable=False),
        sa.Column("amount_toman", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("amount_toman >= 0"),
    )
    op.create_table(
        "payment_attempts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("order_id", sa.Uuid(), sa.ForeignKey("orders.id"), nullable=False),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("provider_reference", sa.String(255)),
        sa.Column("amount_toman", sa.BigInteger(), nullable=False),
        sa.Column("provider_amount", sa.BigInteger()),
        sa.Column("provider_unit", sa.String(16)),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("provider", "provider_reference"),
    )
    op.create_table(
        "allocations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("order_id", sa.Uuid(), sa.ForeignKey("orders.id"), nullable=False, unique=True),
        sa.Column("target_id", sa.Uuid(), sa.ForeignKey("provisioning_targets.id"), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("reserved_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "services",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("allocation_id", sa.Uuid(), sa.ForeignKey("allocations.id"), nullable=False, unique=True),
        sa.Column("external_id", sa.String(255)),
        sa.Column("idempotency_key", sa.String(100), nullable=False, unique=True),
        sa.Column("subscription_url", sa.Text()),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("traffic_limit_bytes", sa.BigInteger(), nullable=False),
    )
    op.create_table(
        "provisioning_jobs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("order_id", sa.Uuid(), sa.ForeignKey("orders.id"), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text()),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "outbox_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("aggregate_id", sa.Uuid(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "audit_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("actor", sa.String(100), nullable=False),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("aggregate_id", sa.Uuid()),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    for table in (
        "audit_events", "outbox_events", "provisioning_jobs", "services", "allocations",
        "payment_attempts", "orders", "provisioning_targets", "panel_instances",
        "provider_accounts", "packages", "customers",
    ):
        op.drop_table(table)
