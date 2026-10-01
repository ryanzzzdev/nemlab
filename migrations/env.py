"""Alembic environment for the adopted NEMLab schema.

Database URL comes from the shared ``NEMLAB_*`` environment via
``DatabaseSettings`` — the same contract as the Java ``prices migrate``
command. No autogenerate metadata target: the existing schema is owned by the
adopted DDL, verified under NEM-070.
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from nemlab_infrastructure.settings import DatabaseSettings

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = None


def _url() -> str:
    return DatabaseSettings().sqlalchemy_url()


def run_migrations_offline() -> None:
    context.configure(
        url=_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = _url()
    connectable = engine_from_config(
        configuration, prefix="sqlalchemy.", poolclass=pool.NullPool
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
