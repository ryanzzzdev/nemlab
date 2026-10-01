"""Worker process configuration.

Mirrors the Java worker flags: all polling/scheduling is opt-in and disabled
by default, so the process idles with no credentials. Poll intervals are
milliseconds, matching ``NEMLAB_WORKER_POLL_MS``/``NEMLAB_SIMULATION_POLL_MS``.
The OE credential (``OPEN_ELECTRICITY_API_KEY``, outside the NEMLAB_ prefix)
is required only when refresh polling is enabled — never for the idle default.
"""

from pydantic import Field, model_validator
from pydantic_settings import SettingsConfigDict

from nemlab_core.prices import Region
from nemlab_infrastructure.settings import DatabaseSettings


class WorkerSettings(DatabaseSettings):
    model_config = SettingsConfigDict(env_prefix="NEMLAB_", extra="ignore")

    worker_enabled: bool = False
    worker_schedule_enabled: bool = False
    worker_regions: str = "NSW1"
    worker_poll_ms: int = Field(default=5000, ge=1)
    simulation_enabled: bool = False
    simulation_poll_ms: int = Field(default=5000, ge=1)
    open_electricity_api_key: str | None = Field(
        default=None, validation_alias="OPEN_ELECTRICITY_API_KEY"
    )

    @property
    def regions(self) -> list[str]:
        return [part.strip() for part in self.worker_regions.split(",") if part.strip()]

    @model_validator(mode="after")
    def _worker_requirements(self) -> "WorkerSettings":
        if not self.worker_enabled:
            return self
        if not 1000 <= self.worker_poll_ms <= 60_000:
            raise ValueError("worker poll interval must be between 1000 and 60000 ms")
        key = self.open_electricity_api_key
        if key is None or not key.strip() or "\n" in key or "\r" in key:
            raise ValueError(
                "OPEN_ELECTRICITY_API_KEY is required when the worker is enabled"
            )
        if self.worker_schedule_enabled:
            for name in self.regions:
                try:
                    Region[name]
                except KeyError:
                    raise ValueError(
                        f"unknown NEM region in NEMLAB_WORKER_REGIONS: {name!r}"
                    ) from None
        return self
