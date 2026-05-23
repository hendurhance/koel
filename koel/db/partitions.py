from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime

from sqlalchemy import text
from sqlalchemy.engine import Connection


@dataclass(frozen=True)
class PartitionSpec:
    parent: str
    partition_key: str
    retention_months: int


PARTITIONED_TABLES: tuple[PartitionSpec, ...] = (
    PartitionSpec(
        parent="exchange_rates_history", partition_key="observed_at", retention_months=24
    ),
    PartitionSpec(parent="rate_observations", partition_key="fetched_at", retention_months=3),
    PartitionSpec(parent="api_usage_events", partition_key="occurred_at", retention_months=6),
)


def month_floor(d: date) -> date:
    return d.replace(day=1)


def next_month(d: date) -> date:
    year, month = d.year, d.month
    return date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)


def months_around(anchor: datetime | None = None, *, lookahead: int = 2) -> list[date]:
    """Return month starts from current month up to `lookahead` months forward."""
    anchor = anchor or datetime.now(tz=UTC)
    start = month_floor(anchor.date())
    out = [start]
    for _ in range(lookahead):
        out.append(next_month(out[-1]))
    return out


def partition_name(parent: str, month_start: date) -> str:
    return f"{parent}_{month_start:%Y%m}"


def create_partition_sql(spec: PartitionSpec, month_start: date) -> str:
    name = partition_name(spec.parent, month_start)
    end = next_month(month_start)
    return (
        f"CREATE TABLE IF NOT EXISTS {name} "
        f"PARTITION OF {spec.parent} "
        f"FOR VALUES FROM ('{month_start.isoformat()}') TO ('{end.isoformat()}')"
    )


def ensure_partitions(conn: Connection, *, lookahead: int = 2) -> list[str]:
    """Create partitions for the current month + `lookahead` forward. Idempotent."""
    created: list[str] = []
    for month_start in months_around(lookahead=lookahead):
        for spec in PARTITIONED_TABLES:
            sql = create_partition_sql(spec, month_start)
            conn.execute(text(sql))
            created.append(partition_name(spec.parent, month_start))
    return created


def drop_expired_partitions(conn: Connection, *, now: datetime | None = None) -> list[str]:
    """Drop partitions older than each spec's retention window."""
    now = now or datetime.now(tz=UTC)
    dropped: list[str] = []
    for spec in PARTITIONED_TABLES:
        cutoff_month = month_floor(now.date())
        for _ in range(spec.retention_months):
            cutoff_month = _prev_month(cutoff_month)
        # Postgres inheritance: list children of the parent, drop any with
        # upper bound <= cutoff_month start.
        rows = conn.execute(
            text(
                """
                SELECT inhrelid::regclass::text AS child
                FROM pg_inherits
                WHERE inhparent = :parent::regclass
                """
            ),
            {"parent": spec.parent},
        ).all()
        for (child_name,) in rows:
            suffix = child_name.rsplit("_", 1)[-1]
            if len(suffix) != 6 or not suffix.isdigit():
                continue
            part_month = date(int(suffix[:4]), int(suffix[4:]), 1)
            if part_month < cutoff_month:
                conn.execute(text(f"DROP TABLE IF EXISTS {child_name}"))
                dropped.append(child_name)
    return dropped


def _prev_month(d: date) -> date:
    return date(d.year - 1, 12, 1) if d.month == 1 else date(d.year, d.month - 1, 1)
