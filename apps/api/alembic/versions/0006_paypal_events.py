"""PayPal webhook events."""

from alembic import op
import sqlalchemy as sa

revision = "0006_paypal_events"
down_revision = "0005_refund_requests"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "paypal_events",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("paypal_event_id", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("paypal_event_id", name="uq_paypal_events_paypal_event_id"),
    )


def downgrade() -> None:
    op.drop_table("paypal_events")
