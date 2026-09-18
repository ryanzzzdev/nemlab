#!/usr/bin/env python3
"""Start packaged applications locally, check readiness/liveness, and stop only our children."""
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
JAVA = str(Path(os.environ["JAVA_HOME"]) / "bin/java") if os.environ.get("JAVA_HOME") else "java"


def jar(module):
    candidates = [p for p in (ROOT / module / "build/libs").glob("*.jar") if not p.name.endswith("-plain.jar")]
    if len(candidates) != 1:
        raise RuntimeError(f"Build {module}:bootJar first; expected one executable jar, got {candidates}")
    return candidates[0]


def check(module):
    with tempfile.TemporaryFile(mode="w+t") as log:
        args = [JAVA, "-jar", str(jar(module))]
        if module == "api":
            args += ["--server.port=0", "--server.address=127.0.0.1"]
        else:
            args += ["--nemlab.worker.enabled=false"]
        process = subprocess.Popen(args, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
        try:
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                log.seek(0)
                output = log.read()
                if process.poll() is not None:
                    raise RuntimeError(f"{module} exited early: {output}")
                if f"Started {module.capitalize()}Application" in output:
                    if module == "api":
                        match = re.search(r"Tomcat started on port (\d+)", output)
                        if not match:
                            raise RuntimeError(f"API port not reported: {output}")
                        with urllib.request.urlopen(f"http://127.0.0.1:{match[1]}/actuator/health", timeout=5) as response:
                            assert response.status == 200
                            assert json.load(response)["status"] == "UP"
                    else:
                        time.sleep(1)
                        assert process.poll() is None, "worker should stay alive without scheduled jobs"
                    print(f"PASS: packaged {module} starts and remains available")
                    return
                time.sleep(.1)
            raise RuntimeError(f"{module} startup timed out: {output}")
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)


if __name__ == "__main__":
    check("api")
    check("worker")
