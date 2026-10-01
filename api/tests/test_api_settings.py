import pytest
from pydantic import ValidationError

from nemlab_api.settings import ApiSettings


def test_all_features_disabled_by_default() -> None:
    settings = ApiSettings()
    assert not settings.data_enabled
    assert not settings.simulation_api_enabled
    assert not settings.admin_enabled
    assert settings.admin_operator == ""
    assert settings.admin_token == ""


def test_flags_read_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NEMLAB_DATA_ENABLED", "true")
    monkeypatch.setenv("NEMLAB_ADMIN_ENABLED", "true")
    monkeypatch.setenv("NEMLAB_ADMIN_TOKEN", "token")
    settings = ApiSettings()
    assert settings.data_enabled
    assert settings.admin_enabled
    assert settings.admin_token == "token"


def test_invalid_flag_gives_validation_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NEMLAB_DATA_ENABLED", "not-a-bool")
    with pytest.raises(ValidationError):
        ApiSettings()
