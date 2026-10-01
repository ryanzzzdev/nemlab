"""Worker process entry point: ``nemlab-worker`` / ``python -m nemlab_worker.main``.

Non-HTTP process, kept alive like the Java Spring ``web-application-type=none``
worker. With every flag off it idles without credentials and exits cleanly on
SIGTERM/SIGINT.
"""

import logging
import signal
import sys
import threading

from pydantic import ValidationError

from nemlab_worker.settings import WorkerSettings

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s"
)
logger = logging.getLogger("nemlab_worker")


def run(settings: WorkerSettings, stop: threading.Event) -> None:
    if not (settings.worker_enabled or settings.simulation_enabled):
        logger.info("worker idle: all features disabled")
        stop.wait()
        return
    # NEM-072/NEM-076 attach refresh polling, daily schedules and simulation
    # polling here; until then an enabled worker still just waits for shutdown.
    logger.info(
        "worker started: worker_enabled=%s schedule=%s "
        "regions=%s simulation_enabled=%s",
        settings.worker_enabled,
        settings.worker_schedule_enabled,
        ",".join(settings.regions),
        settings.simulation_enabled,
    )
    stop.wait()


def main() -> None:
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
