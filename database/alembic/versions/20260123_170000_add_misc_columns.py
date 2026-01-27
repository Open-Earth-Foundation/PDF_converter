"""Add misc JSONB columns."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260123_170000_add_misc_columns"
down_revision = "20250107_000000_init_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("City", sa.Column("misc", postgresql.JSONB(), nullable=True))
    op.add_column("Sector", sa.Column("misc", postgresql.JSONB(), nullable=True))
    op.add_column("Indicator", sa.Column("misc", postgresql.JSONB(), nullable=True))
    op.add_column("CityAnnualStats", sa.Column("misc", postgresql.JSONB(), nullable=True))
    op.add_column("EmissionRecord", sa.Column("misc", postgresql.JSONB(), nullable=True))
    op.add_column("CityBudget", sa.Column("misc", postgresql.JSONB(), nullable=True))
    op.add_column("FundingSource", sa.Column("misc", postgresql.JSONB(), nullable=True))
    op.add_column("BudgetFunding", sa.Column("misc", postgresql.JSONB(), nullable=True))
    op.add_column("Initiative", sa.Column("misc", postgresql.JSONB(), nullable=True))
    op.add_column("Stakeholder", sa.Column("misc", postgresql.JSONB(), nullable=True))
    op.add_column(
        "InitiativeStakeholder", sa.Column("misc", postgresql.JSONB(), nullable=True)
    )
    op.add_column(
        "InitiativeIndicator", sa.Column("misc", postgresql.JSONB(), nullable=True)
    )
    op.add_column("CityTarget", sa.Column("misc", postgresql.JSONB(), nullable=True))
    op.add_column(
        "IndicatorValue", sa.Column("misc", postgresql.JSONB(), nullable=True)
    )
    op.add_column(
        "ClimateCityContract", sa.Column("misc", postgresql.JSONB(), nullable=True)
    )
    op.add_column("TefCategory", sa.Column("misc", postgresql.JSONB(), nullable=True))
    op.add_column("InitiativeTef", sa.Column("misc", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("InitiativeTef", "misc")
    op.drop_column("TefCategory", "misc")
    op.drop_column("ClimateCityContract", "misc")
    op.drop_column("IndicatorValue", "misc")
    op.drop_column("CityTarget", "misc")
    op.drop_column("InitiativeIndicator", "misc")
    op.drop_column("InitiativeStakeholder", "misc")
    op.drop_column("Stakeholder", "misc")
    op.drop_column("Initiative", "misc")
    op.drop_column("BudgetFunding", "misc")
    op.drop_column("FundingSource", "misc")
    op.drop_column("CityBudget", "misc")
    op.drop_column("EmissionRecord", "misc")
    op.drop_column("CityAnnualStats", "misc")
    op.drop_column("Indicator", "misc")
    op.drop_column("Sector", "misc")
    op.drop_column("City", "misc")
