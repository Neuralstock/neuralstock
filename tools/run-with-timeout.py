#!/usr/bin/env python3
"""Run one command with a portable wall-clock deadline and process-group cleanup."""

from __future__ import annotations

import os
import signal
import subprocess
import sys


def main() -> int:
    if len(sys.argv) < 3:
        print(f"usage: {sys.argv[0]} SECONDS COMMAND [ARG ...]", file=sys.stderr)
        return 64
    try:
        timeout_seconds = float(sys.argv[1])
    except ValueError:
        print("timeout must be a positive number of seconds", file=sys.stderr)
        return 64
    if timeout_seconds <= 0:
        print("timeout must be a positive number of seconds", file=sys.stderr)
        return 64

    process = subprocess.Popen(sys.argv[2:], start_new_session=True)
    try:
        return process.wait(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        print(
            f"command exceeded its {timeout_seconds:g}-second wall-clock limit",
            file=sys.stderr,
        )
        os.killpg(process.pid, signal.SIGTERM)
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
        return 124


if __name__ == "__main__":
    raise SystemExit(main())
