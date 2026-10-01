"""Shared database configuration.

Reads the same environment contract as the Java backend: ``NEMLAB_DB_URL``
carries the existing ``jdbc:postgresql://`` URL so ``.env`` files stay shared;
``sqlalchemy_url`` translates it for SQLAlchemy/Psycopg.
"""

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="NEMLAB_", extra="ignore")

    db_url: str = "jdbc:postgresql://127.0.0.1:55432/nemlab"
    db_user: str = "nemlab"
    db_password: str = ""

    @field_validator("db_url")
    @classmethod
    def _jdbc_postgres_url(cls, value: str) -> str:
        if not value.startswith("jdbc:postgresql://"):
            raise ValueError(
                "must be a jdbc:postgresql:// URL (same value as the Java backend)"
            )
        return value

    def sqlalchemy_url(self) -> str:
        url = "postgresql+psycopg://" + self.db_url.removeprefix("jdbc:postgresql://")
        if self.db_user:
            credentials = self.db_user
            if self.db_password:
                credentials += ":" + self.db_password
            host, _, rest = url.partition("://")
            url = f"{host}://{credentials}@{rest}"
        return url
