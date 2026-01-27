"""Change BudgetFunding.amount from INTEGER to BIGINT."""

from alembic import op
import sqlalchemy as sa

revision = "20260126_budgetfunding_bigint"
down_revision = "20260123_170000_add_misc_columns"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "BudgetFunding",
        "amount",
        existing_type=sa.Integer(),
        type_=sa.BigInteger(),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "BudgetFunding",
        "amount",
        existing_type=sa.BigInteger(),
        type_=sa.Integer(),
        existing_nullable=False,
    )
