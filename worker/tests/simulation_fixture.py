"""Real child-process fixture mirroring the Java ``SimulationFixture``:
scenarios with no database access and no live compute credentials.

Invocation: ``python simulation_fixture.py SCENARIO MARKER --simulate INPUT
OUTPUT`` — the trailing args come from ``SimulationProcess`` exactly like a
real simulation child. The marker carries ``pid``, the input path and the
output path so tests can prove cleanup.
"""

import os
import sys
import time
from pathlib import Path

from nemlab_infrastructure import simulations
from nemlab_worker.simulation import run_simulation_command

scenario = sys.argv[1]
marker = Path(sys.argv[2])
input_file = Path(sys.argv[4])
output = Path(sys.argv[5])

# The parent clears the environment entirely; CPython may still coerce the
# C locale into LC_CTYPE — every other variable must be absent.
if any(key != "LC_CTYPE" for key in os.environ):
    sys.exit(9)

marker.write_text(f"{os.getpid()}\n{input_file}\n{output}")

if scenario == "hang":
    time.sleep(60)
    sys.exit(0)
if scenario == "crash":
    sys.exit(8)
if scenario == "watchdog":
    run_simulation_command(sys.argv[3:])
    time.sleep(60)
    sys.exit(0)
if scenario == "wrongkey":
    # An honest-shaped but tampered response: the echoed key must differ.
    code = run_simulation_command(sys.argv[3:])
    _key, result = simulations.read_output(output.read_text())
    output.write_text(simulations.output_json("0" * 64, result))
    sys.exit(code)
if scenario == "malformed":
    output.write_text("not JSON")
    sys.exit(0)
if scenario == "oversized":
    output.write_text("x" * 1_000_001)
    sys.exit(0)
sys.exit(run_simulation_command(sys.argv[3:]))
