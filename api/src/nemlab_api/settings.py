"""API process configuration.

Mirrors the Java API flags: every feature is opt-in and disabled by default,
so the API shell starts with no credentials. ``SERVER_ADDRESS``/``PORT`` match
the Spring ``server.address``/``server.port`` environment contract.
"""

from pydantic_settings import SettingsConfigDict

from nemlab_infrastructure.settings import DatabaseSettings


class ApiSettings(DatabaseSettings):
    model_config = SettingsConfigDict(env_prefix="NEMLAB_", extra="ignore")

    data_enabled: bool = False
    simulation_api_enabled: bool = False
    admin_enabled: bool = False
    admin_operator: str = ""
    admin_token: str = ""
