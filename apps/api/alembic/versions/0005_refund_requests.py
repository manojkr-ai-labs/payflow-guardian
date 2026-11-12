"""Refund requests."""

from alembic import op
import sqlalchemy as sa

revision = "0005_refund_requests"
down_revision = "0004_assistant_messages"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "refund_requests",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("merchant_id", sa.Uuid(as_uuid=True), sa.ForeignKey("merchants.id"), nullable=False),
        sa.Column("payment_id", sa.Uuid(as_uuid=True), sa.ForeignKey("payments.id"), nullable=False),
        sa.Column("capture_id", sa.String(64), nullable=False),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("prepared_by", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("approved_by", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_hash", sa.String(64), nullable=True),
        sa.Column("paypal_refund_id", sa.String(64), nullable=True),
        sa.Column("paypal_status", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("paypal_refund_id", name="uq_refund_requests_paypal_refund_id"),
    )
    op.create_index(
        "uq_refund_requests_open_capture",
        "refund_requests",
        ["merchant_id", "capture_id"],
        unique=True,
        sqlite_where=sa.text("status IN ('pending_approval', 'needs_checking')"),
        postgresql_where=sa.text("status IN ('pending_approval', 'needs_checking')"),
    )


def downgrade() -> None:
    op.drop_index("uq_refund_requests_open_capture", table_name="refund_requests")
    op.drop_table("refund_requests")
