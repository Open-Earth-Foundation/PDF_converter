"""Change Initiative.totalEstimatedCost from INTEGER to BIGINT."""

from alembic import op
import sqlalchemy as sa

revision = "20260127_initiative_bigint"
down_revision = "20260126_budgetfunding_bigint"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "Initiative",
        "totalEstimatedCost",
        existing_type=sa.Integer(),
        type_=sa.BigInteger(),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "Initiative",
        "totalEstimatedCost",
        existing_type=sa.BigInteger(),
        type_=sa.Integer(),
        existing_nullable=True,
    )
