"""One bounded SQLAlchemy Engine pool per process.

Mirrors the Java HikariCP role: a single pool owned by the process entry point,
explicit transaction contexts in the services that use it. No ORM — SQLAlchemy
Core only — and no second ``psycopg_pool``.
"""

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from nemlab_infrastructure.settings import DatabaseSettings

POOL_SIZE = 5
MAX_OVERFLOW = 5
POOL_TIMEOUT_SECONDS = 30


def create_bounded_engine(settings: DatabaseSettings) -> Engine:
    return create_engine(
        settings.sqlalchemy_url(),
        pool_size=POOL_SIZE,
        max_overflow=MAX_OVERFLOW,
        pool_timeout=POOL_TIMEOUT_SECONDS,
        pool_pre_ping=True,
    )


def check_database(engine: Engine) -> None:
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
