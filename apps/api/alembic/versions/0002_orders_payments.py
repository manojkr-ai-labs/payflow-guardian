"""Orders and payments."""

from alembic import op
import sqlalchemy as sa

revision = "0002_orders_payments"
down_revision = "0001_auth_activity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "orders",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("merchant_id", sa.Uuid(as_uuid=True), sa.ForeignKey("merchants.id"), nullable=False),
        sa.Column("test_order_code", sa.String(32), nullable=False),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("created_by", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "payments",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("merchant_id", sa.Uuid(as_uuid=True), sa.ForeignKey("merchants.id"), nullable=False),
        sa.Column("order_id", sa.Uuid(as_uuid=True), sa.ForeignKey("orders.id"), nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("paypal_order_id", sa.String(64), nullable=True),
        sa.Column("paypal_capture_id", sa.String(64), nullable=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("confirmation", sa.String(32), nullable=False),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("paypal_status", sa.String(64), nullable=True),
        sa.Column("approve_url", sa.Text(), nullable=True),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("merchant_id", "idempotency_key", name="uq_payments_merchant_idempotency"),
        sa.UniqueConstraint("paypal_order_id", name="uq_payments_paypal_order_id"),
        sa.UniqueConstraint("paypal_capture_id", name="uq_payments_paypal_capture_id"),
    )
    op.create_index("ix_payments_merchant_created", "payments", ["merchant_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_payments_merchant_created", table_name="payments")
    op.drop_table("payments")
    op.drop_table("orders")
