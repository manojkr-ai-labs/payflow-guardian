"""Assistant messages."""

from alembic import op
import sqlalchemy as sa

revision = "0004_assistant_messages"
down_revision = "0003_payment_fact_sheet"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "assistant_messages",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("merchant_id", sa.Uuid(as_uuid=True), sa.ForeignKey("merchants.id"), nullable=False),
        sa.Column("user_id", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("conversation_id", sa.String(64), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("tool_name", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "ix_assistant_messages_conversation",
        "assistant_messages",
        ["merchant_id", "conversation_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_assistant_messages_conversation", table_name="assistant_messages")
    op.drop_table("assistant_messages")
