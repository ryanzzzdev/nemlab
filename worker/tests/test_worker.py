import threading

import pytest
from pydantic import ValidationError

from nemlab_worker.main import run
from nemlab_worker.settings import WorkerSettings


def test_defaults_match_env_example() -> None:
    settings = WorkerSettings()
    assert not settings.worker_enabled
    assert not settings.worker_schedule_enabled
    assert settings.worker_poll_ms == 5000
    assert not settings.simulation_enabled
    assert settings.simulation_poll_ms == 5000
    assert settings.regions == ["NSW1"]


def test_regions_split() -> None:
    assert WorkerSettings(worker_regions="NSW1, QLD1 ,VIC1").regions == [
        "NSW1",
        "QLD1",
        "VIC1",
    ]


def test_poll_interval_must_be_positive() -> None:
    with pytest.raises(ValidationError):
        WorkerSettings(worker_poll_ms=0)


def test_idle_run_returns_on_stop() -> None:
    stop = threading.Event()
    stop.set()
    run(WorkerSettings(), stop)  # returns immediately; no credentials needed


def test_enabled_run_waits_for_stop() -> None:
    stop = threading.Event()
    timer = threading.Timer(0.05, stop.set)
    timer.start()
    run(WorkerSettings(worker_enabled=True), stop)
    assert stop.is_set()
