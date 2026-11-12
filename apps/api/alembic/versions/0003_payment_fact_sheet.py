"""Payment fact sheet."""

from alembic import op
import sqlalchemy as sa

revision = "0003_payment_fact_sheet"
down_revision = "0002_orders_payments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("payments", sa.Column("fact_sheet", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("payments", "fact_sheet")
