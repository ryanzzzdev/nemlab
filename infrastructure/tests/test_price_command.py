"""Ports the Java ``PriceImportCommandTest`` — retired ingestion commands
exit 2 without reaching the database or OE, and never echo env names.
"""

import os
import subprocess
import sys


def test_retired_commands_cannot_reach_database_or_oe() -> None:
    for command in ("start", "resume"):
        result = subprocess.run(  # noqa: S603
            [sys.executable, "-m", "nemlab_infrastructure.prices", command],
            capture_output=True,
            text=True,
            env={"PATH": os.environ.get("PATH", "")},
            timeout=10,
        )
        assert result.returncode == 2
        assert "Direct ingestion is retired" in result.stderr
        assert "NEMLAB_DB" not in result.stderr
