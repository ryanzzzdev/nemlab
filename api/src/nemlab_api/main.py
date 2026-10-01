"""API process entry point: ``nemlab-api`` / ``python -m nemlab_api.main``."""

import os
import sys

import uvicorn
from pydantic import ValidationError

from nemlab_api.app import create_app
from nemlab_api.settings import ApiSettings


def main() -> None:
    try:
        settings = ApiSettings()
    except ValidationError as error:
        print("nemlab-api: invalid configuration", file=sys.stderr)
        for detail in error.errors():
            location = ".".join(str(part) for part in detail["loc"])
            print(f"  {location}: {detail['msg']}", file=sys.stderr)
        sys.exit(2)

    host = os.environ.get("SERVER_ADDRESS", "127.0.0.1")
    port = int(os.environ.get("PORT", "8080"))
    uvicorn.run(create_app(settings), host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
