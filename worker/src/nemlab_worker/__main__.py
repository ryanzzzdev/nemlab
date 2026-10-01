"""``python -m nemlab_worker`` — like ``WorkerApplication.main``: fetch-child
mode first, otherwise the worker process."""

import sys

from nemlab_worker.main import main

if __name__ == "__main__":
    main()
    sys.exit(0)
