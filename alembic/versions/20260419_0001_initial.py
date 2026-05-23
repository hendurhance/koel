"""Initial Koel v2 schema.

Revision ID: 20260419_0001
Revises:
Create Date: 2026-04-19

Clean v2 schema. Predecessor (cfc173228e49) was dropped during the rebuild;
this migration assumes an empty database.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

import sqlalchemy as sa
from alembic import op
from koel.db.partitions import PARTITIONED_TABLES, create_partition_sql, months_around
from sqlalchemy.dialects import postgresql

revision = "20260419_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------ extensions
    op.execute("CREATE EXTENSION IF NOT EXISTS citext")
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')

    # ------------------------------------------------------------------ currencies
    op.create_table(
        "currencies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(3), nullable=False, unique=True),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("symbol", sa.Text),
        sa.Column("decimal_digits", sa.SmallInteger, nullable=False, server_default="2"),
        sa.Column("tier", sa.String(16), nullable=False, server_default="exotic"),
        sa.Column("scrape_interval_seconds", sa.Integer),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("tier IN ('major','minor','exotic')", name="tier_valid"),
    )
    op.create_index("ix_currencies_tier_active", "currencies", ["tier", "is_active"])

    # ------------------------------------------------------------------ sources
    op.create_table(
        "sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("slug", sa.String(64), nullable=False, unique=True),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("base_url", sa.Text, nullable=False),
        sa.Column("weight", sa.Numeric(5, 3), nullable=False, server_default="1.000"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column(
            "config", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )

    # ------------------------------------------------------------------ source_health
    op.create_table(
        "source_health",
        sa.Column(
            "source_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sources.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("consecutive_failures", sa.Integer, nullable=False, server_default="0"),
        sa.Column("total_requests", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("total_failures", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("avg_latency_ms", sa.Numeric(10, 2)),
        sa.Column("circuit_state", sa.String(16), nullable=False, server_default="closed"),
        sa.Column("circuit_opened_at", sa.DateTime(timezone=True)),
        sa.Column("last_success_at", sa.DateTime(timezone=True)),
        sa.Column("last_failure_at", sa.DateTime(timezone=True)),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint(
            "circuit_state IN ('closed','open','half_open')",
            name="circuit_state_valid",
        ),
    )

    # ------------------------------------------------------------------ exchange_rates_current
    op.create_table(
        "exchange_rates_current",
        sa.Column(
            "base_currency_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("currencies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "target_currency_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("currencies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("rate", sa.Numeric(24, 12), nullable=False),
        sa.Column("confidence", sa.Numeric(4, 3)),
        sa.Column("sources_count", sa.SmallInteger, nullable=False, server_default="0"),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("base_currency_id", "target_currency_id"),
        sa.CheckConstraint("rate > 0", name="rate_positive"),
        sa.CheckConstraint(
            "base_currency_id <> target_currency_id",
            name="different_currencies",
        ),
    )

    # ------------------------------------------------------------------ exchange_rates_history (partitioned)
    op.execute(
        """
        CREATE TABLE exchange_rates_history (
            id               BIGINT GENERATED BY DEFAULT AS IDENTITY,
            base_currency_id UUID NOT NULL,
            target_currency_id UUID NOT NULL,
            rate             NUMERIC(24, 12) NOT NULL,
            confidence       NUMERIC(4, 3),
            sources_count    SMALLINT,
            observed_at      TIMESTAMPTZ NOT NULL,
            CONSTRAINT pk_exchange_rates_history PRIMARY KEY (id, observed_at),
            CONSTRAINT ck_exchange_rates_history_rate_positive CHECK (rate > 0)
        ) PARTITION BY RANGE (observed_at)
        """
    )
    op.execute(
        """
        CREATE INDEX ix_history_pair_time
        ON exchange_rates_history (base_currency_id, target_currency_id, observed_at DESC)
        """
    )

    # ------------------------------------------------------------------ rate_observations (partitioned)
    op.execute(
        """
        CREATE TABLE rate_observations (
            id               BIGINT GENERATED BY DEFAULT AS IDENTITY,
            source_id        UUID NOT NULL,
            base_currency_id UUID NOT NULL,
            target_currency_id UUID NOT NULL,
            rate             NUMERIC(24, 12) NOT NULL,
            fetched_at       TIMESTAMPTZ NOT NULL,
            latency_ms       INTEGER,
            CONSTRAINT pk_rate_observations PRIMARY KEY (id, fetched_at),
            CONSTRAINT ck_rate_observations_rate_positive CHECK (rate > 0)
        ) PARTITION BY RANGE (fetched_at)
        """
    )
    op.execute(
        """
        CREATE INDEX ix_observations_pair_time
        ON rate_observations (base_currency_id, target_currency_id, fetched_at DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX ix_observations_source_time
        ON rate_observations (source_id, fetched_at DESC)
        """
    )

    # ------------------------------------------------------------------ users
    op.execute(
        """
        CREATE TABLE users (
            id            UUID PRIMARY KEY,
            email         CITEXT NOT NULL UNIQUE,
            role          VARCHAR(16) NOT NULL DEFAULT 'user',
            is_active     BOOLEAN NOT NULL DEFAULT TRUE,
            last_login_at TIMESTAMPTZ,
            created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT ck_users_role_valid CHECK (role IN ('user','admin'))
        )
        """
    )

    # ------------------------------------------------------------------ magic_links
    op.execute(
        """
        CREATE TABLE magic_links (
            id          UUID PRIMARY KEY,
            email       CITEXT NOT NULL,
            token_hash  TEXT NOT NULL UNIQUE,
            expires_at  TIMESTAMPTZ NOT NULL,
            used_at     TIMESTAMPTZ,
            ip_address  INET,
            user_agent  TEXT,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute("CREATE INDEX ix_magic_links_email_expires ON magic_links (email, expires_at)")

    # ------------------------------------------------------------------ api_key_groups
    op.create_table(
        "api_key_groups",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("user_id", "name", name="uq_group_user_name"),
    )

    # ------------------------------------------------------------------ api_keys
    op.create_table(
        "api_keys",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "group_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("api_key_groups.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("key_hash", sa.Text, nullable=False, unique=True),
        sa.Column("key_prefix", sa.String(8), nullable=False),
        sa.Column(
            "scopes",
            postgresql.ARRAY(sa.Text),
            nullable=False,
            server_default=sa.text("ARRAY['rates:read']::text[]"),
        ),
        sa.Column("rate_limit_per_min", sa.Integer, nullable=False, server_default="60"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("last_used_at", sa.DateTime(timezone=True)),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_api_keys_group_active", "api_keys", ["group_id", "is_active"])
    op.create_index("ix_api_keys_prefix", "api_keys", ["key_prefix"])

    # ------------------------------------------------------------------ api_usage_events (partitioned)
    op.execute(
        """
        CREATE TABLE api_usage_events (
            id               BIGINT GENERATED BY DEFAULT AS IDENTITY,
            api_key_id       UUID NOT NULL,
            endpoint         VARCHAR(128) NOT NULL,
            method           VARCHAR(8) NOT NULL,
            status_code      SMALLINT NOT NULL,
            response_time_ms INTEGER,
            bytes_sent       INTEGER,
            ip_address       INET,
            occurred_at      TIMESTAMPTZ NOT NULL,
            CONSTRAINT pk_api_usage_events PRIMARY KEY (id, occurred_at)
        ) PARTITION BY RANGE (occurred_at)
        """
    )
    op.execute(
        """
        CREATE INDEX ix_usage_key_time
        ON api_usage_events (api_key_id, occurred_at DESC)
        """
    )

    # ------------------------------------------------------------------ audit_log
    op.create_table(
        "audit_log",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True)),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("subject_type", sa.String(32)),
        sa.Column("subject_id", postgresql.UUID(as_uuid=True)),
        sa.Column(
            "metadata", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
        sa.Column("ip_address", postgresql.INET),
        sa.Column(
            "occurred_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_audit_actor_time", "audit_log", ["actor_user_id", "occurred_at"])
    op.create_index("ix_audit_action_time", "audit_log", ["action", "occurred_at"])

    # ------------------------------------------------------------------ initial partitions
    # Seed current month + 2 forward months so the app can start writing immediately.
    for month_start in months_around(lookahead=2):
        for spec in PARTITIONED_TABLES:
            op.execute(create_partition_sql(spec, month_start))


def downgrade() -> None:
    # Drop in reverse dependency order. Child partitions cascade with the parent.
    op.drop_table("audit_log")
    op.execute("DROP TABLE IF EXISTS api_usage_events CASCADE")
    op.drop_table("api_keys")
    op.drop_table("api_key_groups")
    op.execute("DROP TABLE IF EXISTS magic_links")
    op.execute("DROP TABLE IF EXISTS users")
    op.execute("DROP TABLE IF EXISTS rate_observations CASCADE")
    op.execute("DROP TABLE IF EXISTS exchange_rates_history CASCADE")
    op.drop_table("exchange_rates_current")
    op.drop_table("source_health")
    op.drop_table("sources")
    op.drop_table("currencies")
    op.execute('DROP EXTENSION IF EXISTS "uuid-ossp"')
    op.execute("DROP EXTENSION IF EXISTS citext")


_ = (date, datetime, timezone)  # reserved for future time-ref migrations
