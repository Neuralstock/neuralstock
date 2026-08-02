from __future__ import annotations

import os
import subprocess
import threading
import urllib.parse
from collections.abc import Iterator
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import ClassVar

from neuralstock.release import publish_canonical_contract_artifacts

ROOT = Path(__file__).resolve().parents[2]
IMMUTABLE_CACHE = "public, max-age=31536000, immutable"


class _ContractHandler(BaseHTTPRequestHandler):
    server_version = "NeuralStockContractOriginTest/1"

    def log_message(self, _format: str, *_args: object) -> None:
        return

    def do_GET(self) -> None:
        root: Path = self.server.contract_root  # type: ignore[attr-defined]
        mode: str = self.server.mode  # type: ignore[attr-defined]
        relative = urllib.parse.urlsplit(self.path).path.removeprefix("/")
        candidate = root.joinpath(*Path(relative).parts)
        should_serve = mode in {"matching", "mismatch"} or (
            mode == "partial" and relative == "v0.2/asset.intent.schema.json"
        )
        if not should_serve or not candidate.is_file():
            body = b"missing"
            self.send_response(404)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        body = candidate.read_bytes()
        if mode == "mismatch" and relative == "v0.2/common.schema.json":
            body = b"different canonical contract"
        if relative.endswith(".schema.json"):
            content_type = "application/schema+json"
        elif relative.endswith(".json"):
            content_type = "application/json"
        else:
            content_type = "text/plain"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", IMMUTABLE_CACHE)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class _ContractServer(ThreadingHTTPServer):
    contract_root: ClassVar[Path]
    mode: ClassVar[str]


@contextmanager
def _origin(root: Path, mode: str) -> Iterator[str]:
    server = _ContractServer(("127.0.0.1", 0), _ContractHandler)
    server.contract_root = root
    server.mode = mode
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        thread.join()
        server.server_close()


def _verify(release: Path, origin: str, *, allow_absent: bool) -> subprocess.CompletedProcess[str]:
    command = ["sh", str(ROOT / "tools/verify-contract-origin.sh")]
    if allow_absent:
        command.append("--allow-absent")
    command.extend([str(release), origin])
    return subprocess.run(
        command,
        cwd=ROOT,
        env={
            **os.environ,
            "NEURALSTOCK_ALLOW_INSECURE_TEST_ORIGIN": "1",
        },
        check=False,
        capture_output=True,
        text=True,
        timeout=20,
    )


def test_fresh_namespace_is_accepted_only_in_explicit_bootstrap_mode(tmp_path: Path) -> None:
    release = tmp_path / "release"
    publish_canonical_contract_artifacts(release)
    with _origin(release, "absent") as origin:
        strict = _verify(release, origin, allow_absent=False)
        bootstrap = _verify(release, origin, allow_absent=True)

    assert strict.returncode != 0
    assert "namespace is absent" in strict.stderr
    assert bootstrap.returncode == 0, bootstrap.stderr
    assert "locally coherent fresh v0.2" in bootstrap.stdout


def test_bootstrap_rejects_partial_or_mismatched_namespace(tmp_path: Path) -> None:
    release = tmp_path / "release"
    publish_canonical_contract_artifacts(release)
    for mode, expected in (
        ("partial", "partially published"),
        ("mismatch", "differs from the candidate bytes"),
    ):
        with _origin(release, mode) as origin:
            completed = _verify(release, origin, allow_absent=True)
        assert completed.returncode != 0
        assert expected in completed.stderr


def test_strict_mode_accepts_complete_matching_namespace(tmp_path: Path) -> None:
    release = tmp_path / "release"
    publish_canonical_contract_artifacts(release)
    with _origin(release, "matching") as origin:
        completed = _verify(release, origin, allow_absent=False)

    assert completed.returncode == 0, completed.stderr
    assert "Verified canonical contract" in completed.stdout
