from __future__ import annotations

import subprocess
import sys

from neuralstock.schema import project_root

SCRIPT = project_root() / "tools" / "run-with-timeout.py"


def test_timeout_wrapper_returns_child_status() -> None:
    result = subprocess.run(
        [sys.executable, SCRIPT, "5", sys.executable, "-c", "raise SystemExit(7)"],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 7


def test_timeout_wrapper_enforces_wall_clock_limit() -> None:
    result = subprocess.run(
        [
            sys.executable,
            SCRIPT,
            "0.05",
            sys.executable,
            "-c",
            "import time; time.sleep(5)",
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 124
    assert "wall-clock limit" in result.stderr
