"""Initial schema."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20250107_000000_init_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "City",
        sa.Column(
            "cityId", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False
        ),
        sa.Column("cityName", sa.String(), nullable=False),
        sa.Column("country", sa.String(), nullable=False),
        sa.Column("locode", sa.String(), nullable=True),
        sa.Column("areaKm2", sa.Numeric(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
    )

    op.create_table(
        "Sector",
        sa.Column(
            "sectorId", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False
        ),
        sa.Column("sectorName", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
    )

    op.create_table(
        "FundingSource",
        sa.Column(
            "fundingSourceId",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
    )

    op.create_table(
        "Stakeholder",
        sa.Column(
            "stakeholderId",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("type", sa.String(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
    )

    op.create_table(
        "TefCategory",
        sa.Column(
            "tefId", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False
        ),
        sa.Column("parentId", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("code", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["parentId"], ["TefCategory.tefId"]),
    )

    op.create_table(
        "CityAnnualStats",
        sa.Column(
            "statId", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False
        ),
        sa.Column("cityId", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("population", sa.Integer(), nullable=True),
        sa.Column("populationDensity", sa.Numeric(), nullable=True),
        sa.Column("gdpPerCapita", sa.Numeric(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["cityId"], ["City.cityId"]),
        sa.UniqueConstraint("cityId", "year"),
    )

    op.create_table(
        "ClimateCityContract",
        sa.Column(
            "climateCityContractId",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column("cityId", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("contractDate", sa.DateTime(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("version", sa.String(), nullable=True),
        sa.Column("language", sa.String(), nullable=True),
        sa.Column("documentUrl", sa.String(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["cityId"], ["City.cityId"]),
        sa.UniqueConstraint("cityId"),
    )

    op.create_table(
        "EmissionRecord",
        sa.Column(
            "emissionRecordId",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column("cityId", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("sectorId", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("scope", sa.String(), nullable=False),
        sa.Column("ghgType", sa.String(), nullable=False),
        sa.Column("value", sa.Integer(), nullable=False),
        sa.Column("unit", sa.String(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["cityId"], ["City.cityId"]),
        sa.ForeignKeyConstraint(["sectorId"], ["Sector.sectorId"]),
        sa.UniqueConstraint("cityId", "year", "sectorId", "scope", "ghgType"),
    )

    op.create_table(
        "CityBudget",
        sa.Column(
            "budgetId", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False
        ),
        sa.Column("cityId", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("totalAmount", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["cityId"], ["City.cityId"]),
    )

    op.create_table(
        "BudgetFunding",
        sa.Column(
            "budgetFundingId",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column("budgetId", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("fundingSourceId", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["budgetId"], ["CityBudget.budgetId"]),
        sa.ForeignKeyConstraint(["fundingSourceId"], ["FundingSource.fundingSourceId"]),
    )

    op.create_table(
        "Initiative",
        sa.Column(
            "initiativeId",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column("cityId", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("startYear", sa.Integer(), nullable=True),
        sa.Column("endYear", sa.Integer(), nullable=True),
        sa.Column("totalEstimatedCost", sa.Integer(), nullable=True),
        sa.Column("currency", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["cityId"], ["City.cityId"]),
    )

    op.create_table(
        "InitiativeStakeholder",
        sa.Column(
            "initiativeStakeholderId",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column("initiativeId", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("stakeholderId", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("role", sa.String(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["initiativeId"], ["Initiative.initiativeId"]),
        sa.ForeignKeyConstraint(["stakeholderId"], ["Stakeholder.stakeholderId"]),
        sa.UniqueConstraint("initiativeId", "stakeholderId"),
    )

    op.create_table(
        "Indicator",
        sa.Column(
            "indicatorId",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column("cityId", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("sectorId", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("unit", sa.String(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["cityId"], ["City.cityId"]),
        sa.ForeignKeyConstraint(["sectorId"], ["Sector.sectorId"]),
    )

    op.create_table(
        "IndicatorValue",
        sa.Column(
            "indicatorValueId",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column("indicatorId", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("value", sa.Numeric(), nullable=False),
        sa.Column("valueType", sa.String(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["indicatorId"], ["Indicator.indicatorId"]),
        sa.UniqueConstraint("indicatorId", "year"),
    )

    op.create_table(
        "CityTarget",
        sa.Column(
            "cityTargetId",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column("cityId", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("indicatorId", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("targetYear", sa.Date(), nullable=False),
        sa.Column("targetValue", sa.Numeric(), nullable=False),
        sa.Column("baselineYear", sa.Date(), nullable=True),
        sa.Column("baselineValue", sa.Numeric(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["cityId"], ["City.cityId"]),
        sa.ForeignKeyConstraint(["indicatorId"], ["Indicator.indicatorId"]),
    )

    op.create_table(
        "InitiativeIndicator",
        sa.Column(
            "initiativeIndicatorId",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column("initiativeId", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("indicatorId", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("contributionType", sa.String(), nullable=False),
        sa.Column("expectedChange", sa.Numeric(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["initiativeId"], ["Initiative.initiativeId"]),
        sa.ForeignKeyConstraint(["indicatorId"], ["Indicator.indicatorId"]),
        sa.UniqueConstraint("initiativeId", "indicatorId"),
    )

    op.create_table(
        "InitiativeTef",
        sa.Column(
            "initiativeTefId",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column("initiativeId", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("tefId", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["initiativeId"], ["Initiative.initiativeId"]),
        sa.ForeignKeyConstraint(["tefId"], ["TefCategory.tefId"]),
        sa.UniqueConstraint("initiativeId", "tefId"),
    )


def downgrade() -> None:
    op.drop_table("InitiativeTef")
    op.drop_table("InitiativeIndicator")
    op.drop_table("CityTarget")
    op.drop_table("IndicatorValue")
    op.drop_table("Indicator")
    op.drop_table("InitiativeStakeholder")
    op.drop_table("Initiative")
    op.drop_table("BudgetFunding")
    op.drop_table("CityBudget")
    op.drop_table("EmissionRecord")
    op.drop_table("ClimateCityContract")
    op.drop_table("CityAnnualStats")
    op.drop_table("TefCategory")
    op.drop_table("Stakeholder")
    op.drop_table("FundingSource")
    op.drop_table("Sector")
    op.drop_table("City")
