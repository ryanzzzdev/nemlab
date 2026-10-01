import pytest
from pydantic import ValidationError

from nemlab_infrastructure.settings import DatabaseSettings


def test_defaults_match_env_example() -> None:
    settings = DatabaseSettings()
    assert settings.db_url == "jdbc:postgresql://127.0.0.1:55432/nemlab"
    assert settings.db_user == "nemlab"


def test_sqlalchemy_url_translates_jdbc_with_credentials() -> None:
    settings = DatabaseSettings(
        db_url="jdbc:postgresql://db.internal:55432/nemlab",
        db_user="nemlab",
        db_password="secret",
    )
    assert (
        settings.sqlalchemy_url()
        == "postgresql+psycopg://nemlab:secret@db.internal:55432/nemlab"
    )


def test_sqlalchemy_url_without_user() -> None:
    settings = DatabaseSettings(db_user="")
    assert settings.sqlalchemy_url() == "postgresql+psycopg://127.0.0.1:55432/nemlab"


def test_non_jdbc_url_rejected() -> None:
    with pytest.raises(ValidationError):
        DatabaseSettings(db_url="postgresql://127.0.0.1/nemlab")


def test_env_prefix(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NEMLAB_DB_URL", "jdbc:postgresql://example:5432/x")
    monkeypatch.setenv("NEMLAB_DB_PASSWORD", "pw")
    assert DatabaseSettings().db_url == "jdbc:postgresql://example:5432/x"
    assert DatabaseSettings().db_password == "pw"
