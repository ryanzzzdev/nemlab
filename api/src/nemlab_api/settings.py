"""API process configuration.

Mirrors the Java API flags: every feature is opt-in and disabled by default,
so the API shell starts with no credentials. ``SERVER_ADDRESS``/``PORT`` match
the Spring ``server.address``/``server.port`` environment contract. When a
database-backed feature is enabled the DB credentials must be present, and
admin controls additionally require a validated operator identity and token —
failing fast at startup like ``AdminConfiguration``.
"""

import re

from pydantic import model_validator
from pydantic_settings import SettingsConfigDict

from nemlab_infrastructure.settings import DatabaseSettings

OPERATOR_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}")
TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_-]{43,128}")


class ApiSettings(DatabaseSettings):
    model_config = SettingsConfigDict(env_prefix="NEMLAB_", extra="ignore")

    data_enabled: bool = False
    simulation_api_enabled: bool = False
    admin_enabled: bool = False
    admin_operator: str = ""
    admin_token: str = ""

    @model_validator(mode="after")
    def _enabled_features_have_credentials(self) -> "ApiSettings":
        if self.data_enabled or self.admin_enabled or self.simulation_api_enabled:
            for name in ("db_url", "db_user", "db_password"):
                if not getattr(self, name).strip():
                    raise ValueError(
                        f"NEMLAB_{name.upper()} is required when database-backed"
                        " API features are enabled"
                    )
        if self.admin_enabled:
            if not self.admin_operator.strip():
                raise ValueError(
                    "NEMLAB_ADMIN_OPERATOR is required when admin controls are enabled"
                )
            if not self.admin_token.strip():
                raise ValueError(
                    "NEMLAB_ADMIN_TOKEN is required when admin controls are enabled"
                )
            if not OPERATOR_PATTERN.fullmatch(self.admin_operator):
                raise ValueError("Invalid operator identifier")
            if not TOKEN_PATTERN.fullmatch(self.admin_token):
                raise ValueError("Admin token must be 43-128 base64url characters")
        return self
