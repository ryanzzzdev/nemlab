"""Worker process configuration.

Mirrors the Java worker flags: all polling/scheduling is opt-in and disabled
by default, so the process idles with no credentials. Poll intervals are
milliseconds, matching ``NEMLAB_WORKER_POLL_MS``/``NEMLAB_SIMULATION_POLL_MS``.
"""

from pydantic import Field
from pydantic_settings import SettingsConfigDict

from nemlab_infrastructure.settings import DatabaseSettings


class WorkerSettings(DatabaseSettings):
    model_config = SettingsConfigDict(env_prefix="NEMLAB_", extra="ignore")

    worker_enabled: bool = False
    worker_schedule_enabled: bool = False
    worker_regions: str = "NSW1"
    worker_poll_ms: int = Field(default=5000, ge=1)
    simulation_enabled: bool = False
    simulation_poll_ms: int = Field(default=5000, ge=1)

    @property
    def regions(self) -> list[str]:
        return [part.strip() for part in self.worker_regions.split(",") if part.strip()]
