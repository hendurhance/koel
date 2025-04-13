"""initial migration

Revision ID: c6fa53d631f8
Revises: 
Create Date: 2025-04-12 15:37:57.925110

"""
import datetime
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'c6fa53d631f8'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create the currencies table (unchanged)
    op.create_table(
        'currencies',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('name_plural', sa.String(length=100), nullable=True),
        sa.Column('code', sa.String(length=3), nullable=False),
        sa.Column('symbol', sa.String(length=10), nullable=False),
        sa.Column('decimal_digits', sa.Integer(), nullable=False),
        sa.Column('icon', sa.String(length=100), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    # Use raw SQL to create the partitioned exchange_rates table with a composite primary key.
    op.execute("""
        CREATE TABLE exchange_rates (
            id SERIAL,
            base_currency_id INTEGER NOT NULL,
            target_currency_id INTEGER NOT NULL,
            rate FLOAT NOT NULL,
            source VARCHAR(50) NOT NULL,
            created_at TIMESTAMPTZ NOT NULL,
            CONSTRAINT fk_exchange_rates_base_currency 
                FOREIGN KEY (base_currency_id) REFERENCES currencies(id),
            CONSTRAINT fk_exchange_rates_target_currency 
                FOREIGN KEY (target_currency_id) REFERENCES currencies(id),
            CONSTRAINT pk_exchange_rates PRIMARY KEY (id, created_at),
            CONSTRAINT unique_exchange_rates UNIQUE (base_currency_id, target_currency_id, created_at)
        ) PARTITION BY RANGE (created_at);
    """)

    # Create an index on the parent table.
    op.execute("""
        CREATE INDEX exchange_rates_index 
        ON exchange_rates (base_currency_id, target_currency_id, created_at);
    """)

    # Determine current month's date range in UTC for the first child partition.
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    start_date = datetime.datetime(now_utc.year, now_utc.month, 1, tzinfo=datetime.timezone.utc)
    # Calculate first day of the next month
    if start_date.month == 12:
        next_year = start_date.year + 1
        next_month = 1
    else:
        next_year = start_date.year
        next_month = start_date.month + 1
    end_date = datetime.datetime(next_year, next_month, 1, tzinfo=datetime.timezone.utc)

    # Convert dates to ISO format strings
    start_date_str = start_date.isoformat()
    end_date_str = end_date.isoformat()
    partition_name = f"exchange_rates_{start_date.strftime('%Y_%m')}"
    
    # Create the first child partition for the current month.
    op.execute(f"""
        CREATE TABLE {partition_name} PARTITION OF exchange_rates
        FOR VALUES FROM ('{start_date_str}') TO ('{end_date_str}');
    """)


def downgrade() -> None:
    """Downgrade schema."""
    # Drop the child partition first. Use the dynamically computed name as in upgrade.
    import datetime
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    start_date = datetime.datetime(now_utc.year, now_utc.month, 1, tzinfo=datetime.timezone.utc)
    partition_name = f"exchange_rates_{start_date.strftime('%Y_%m')}"
    op.execute(f"DROP TABLE IF EXISTS {partition_name};")

    # Drop the partitioned exchange_rates table.
    op.execute("DROP TABLE IF EXISTS exchange_rates;")
    
    # Drop the currencies table.
    op.drop_table('currencies')
