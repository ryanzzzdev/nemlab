from sqlalchemy.pool import QueuePool

from nemlab_infrastructure.database import create_bounded_engine
from nemlab_infrastructure.settings import DatabaseSettings


def test_engine_is_single_bounded_pool() -> None:
    engine = create_bounded_engine(DatabaseSettings())
    try:
        assert isinstance(engine.pool, QueuePool)
        assert engine.pool.size() == 5
        assert engine.url.drivername == "postgresql+psycopg"
        assert engine.url.host == "127.0.0.1"
        assert engine.url.port == 55432
        assert engine.url.database == "nemlab"
    finally:
        engine.dispose()
