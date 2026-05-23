from logging.config import fileConfig

from alembic import context
from koel.config import get_settings

# Ensure all models are imported so their tables register on the metadata.
from koel.db import models  # noqa: F401  (side-effect import)
from koel.db.base import metadata as target_metadata
from sqlalchemy import engine_from_config, pool

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Feed DATABASE_URL from koel settings into Alembic. Doubling ``%`` escapes
# configparser's interpolation — required whenever the URL contains URL-encoded
# characters (e.g. ``P%40ssw0rd`` for a password containing ``@``).
config.set_main_option("sqlalchemy.url", get_settings().DATABASE_URL.replace("%", "%%"))


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
