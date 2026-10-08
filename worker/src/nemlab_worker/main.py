"""Worker process entry point: ``nemlab-worker`` / ``python -m nemlab_worker``.

Non-HTTP process, kept alive like the Java Spring ``web-application-type=none``
worker. With every flag off it idles without credentials and exits cleanly on
SIGTERM/SIGINT. ``--fetch-price`` runs the isolated fetch child mode, which
never sees database credentials.
"""

import logging
import signal
import sys
import threading

from pydantic import ValidationError

from nemlab_core.prices import Region
from nemlab_infrastructure.admin.access import AccessRequests
from nemlab_infrastructure.admin.mail import LocalMailbox, OutboxMailer
from nemlab_infrastructure.database import create_bounded_engine
from nemlab_infrastructure.grid.imports import GridImportJobs
from nemlab_infrastructure.grid.store import GridStore
from nemlab_infrastructure.jobs import RefreshJobService
from nemlab_infrastructure.prices.store import PriceStore
from nemlab_infrastructure.simulations import SimulationJobs
from nemlab_worker.grid import (
    MODE as GRID_MODE,
)
from nemlab_worker.grid import (
    GridFetchProcess,
    GridImportWorker,
    run_grid_fetch_command,
)
from nemlab_worker.mail import MailWorker
from nemlab_worker.refresh import (
    MODE,
    PriceFetchProcess,
    RefreshSchedule,
    RefreshWorker,
    _utc_now,
    run_fetch_command,
)
from nemlab_worker.settings import WorkerSettings
from nemlab_worker.simulation import (
    SIMULATE_MODE,
    SimulationProcess,
    SimulationWorker,
    run_simulation_command,
)

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s"
)
logger = logging.getLogger("nemlab_worker")


def run(settings: WorkerSettings, stop: threading.Event) -> None:
    if (
        not settings.worker_enabled
        and not settings.simulation_enabled
        and not settings.grid_import_enabled
        and not settings.mail_enabled
    ):
        logger.info("worker idle: all features disabled")
        stop.wait()
        return
    engine = create_bounded_engine(settings)
    workers: list[RefreshWorker | SimulationWorker | GridImportWorker | MailWorker] = []
    try:
        api_key = settings.open_electricity_api_key
        if settings.worker_enabled:
            jobs = RefreshJobService(engine, PriceStore(engine))
            if api_key is None:  # the settings validator guarantees this
                raise ValueError("OPEN_ELECTRICITY_API_KEY is required")
            fetcher = PriceFetchProcess(api_key)
            regions = (
                [Region[name] for name in settings.regions]
                if settings.worker_schedule_enabled
                else []
            )
            workers.append(
                RefreshWorker(
                    jobs,
                    RefreshSchedule(jobs, _utc_now, regions),
                    fetcher,
                    settings.worker_poll_ms / 1000,
                )
            )
        if settings.grid_import_enabled:
            if api_key is None:
                raise ValueError("OPEN_ELECTRICITY_API_KEY is required")
            workers.append(
                GridImportWorker(
                    GridImportJobs(engine, GridStore(engine)),
                    GridFetchProcess(api_key),
                    settings.grid_import_poll_ms / 1000,
                )
            )
        if settings.simulation_enabled:
            workers.append(
                SimulationWorker(
                    SimulationJobs(engine),
                    SimulationProcess(),
                    settings.simulation_poll_ms / 1000,
                )
            )
        if settings.mail_enabled:
            retention = AccessRequests(engine).prune
            workers.append(
                MailWorker(
                    OutboxMailer(engine, LocalMailbox(settings.mail_dir)),
                    settings.mail_poll_ms / 1000,
                    retention=retention,
                )
            )
        for worker in workers:
            worker.start()
        try:
            stop.wait()
        finally:
            for worker in workers:
                worker.stop()
    finally:
        engine.dispose()


def main() -> None:
    argv = sys.argv[1:]
    if argv and argv[0] == MODE:
        sys.exit(run_fetch_command(argv))
    if argv and argv[0] == SIMULATE_MODE:
        sys.exit(run_simulation_command(argv))
    if argv and argv[0] == GRID_MODE:
        sys.exit(run_grid_fetch_command(argv))

    try:
        settings = WorkerSettings()
    except ValidationError as error:
        print("nemlab-worker: invalid configuration", file=sys.stderr)
        for detail in error.errors():
            location = ".".join(str(part) for part in detail["loc"])
            print(f"  {location}: {detail['msg']}", file=sys.stderr)
        sys.exit(2)

    stop = threading.Event()

    def _signal(_signum: int, _frame: object) -> None:
        stop.set()

    signal.signal(signal.SIGTERM, _signal)
    signal.signal(signal.SIGINT, _signal)
    run(settings, stop)
    logger.info("worker stopped")


if __name__ == "__main__":
    main()
