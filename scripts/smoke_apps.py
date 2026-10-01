#!/usr/bin/env python3
"""Start the Python applications with all features off, check readiness and
liveness, then stop only the children this script started.

The API serves ``/actuator/health`` (Spring-compatible shape); the worker idles
without credentials. Both must exit cleanly on SIGTERM.
"""

import json
import os
import re
import socket
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def check_api() -> None:
    port = _free_port()
    env = {
        **os.environ,
        "SERVER_ADDRESS": "127.0.0.1",
        "PORT": str(port),
    }
    for flag in (
        "NEMLAB_DATA_ENABLED",
        "NEMLAB_ADMIN_ENABLED",
        "NEMLAB_SIMULATION_API_ENABLED",
    ):
        env[flag] = "false"
    with tempfile.TemporaryFile(mode="w+t") as log:
        process = subprocess.Popen(
            ["uv", "run", "nemlab-api"],
            cwd=ROOT,
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        try:
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                log.seek(0)
                output = log.read()
                if process.poll() is not None:
                    raise RuntimeError(f"api exited early: {output}")
                if re.search(r"Uvicorn running on", output):
                    with urllib.request.urlopen(
                        f"http://127.0.0.1:{port}/actuator/health", timeout=5
                    ) as response:
                        assert response.status == 200
                        assert json.load(response)["status"] == "UP"
                    print("PASS: nemlab-api starts and serves actuator health")
                    return
                time.sleep(0.1)
            raise RuntimeError(f"api startup timed out: {output}")
        finally:
            _stop(process)


def check_worker() -> None:
    env = {
        **os.environ,
        "NEMLAB_WORKER_ENABLED": "false",
        "NEMLAB_SIMULATION_ENABLED": "false",
    }
    with tempfile.TemporaryFile(mode="w+t") as log:
        process = subprocess.Popen(
            ["uv", "run", "nemlab-worker"],
            cwd=ROOT,
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        try:
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                log.seek(0)
                output = log.read()
                if process.poll() is not None:
                    raise RuntimeError(f"worker exited early: {output}")
                if "worker idle" in output:
                    time.sleep(1)
                    assert process.poll() is None, (
                        "worker should stay alive without scheduled jobs"
                    )
                    print("PASS: nemlab-worker starts and remains available")
                    return
                time.sleep(0.1)
            raise RuntimeError(f"worker startup timed out: {output}")
        finally:
            _stop(process)


def _stop(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


if __name__ == "__main__":
    check_api()
    check_worker()
