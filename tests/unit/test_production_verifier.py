from __future__ import annotations

import hashlib
import json
import os
import subprocess
import threading
import urllib.parse
import xml.etree.ElementTree as ET
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
IMMUTABLE_CACHE = "public, max-age=31536000, immutable"
ALIAS_CACHE = "public, max-age=60, must-revalidate"
EXPOSED_HEADERS = (
    "Accept-Ranges, Cache-Control, Content-Length, Content-Range, Content-Type, ETag, Last-Modified"
)
REDIRECT_PROBE = "/asset/neuralstock-redirect-probe/0.0.0?neuralstock_redirect_probe=1"


def _pretty_json(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _registry_revision(value: dict[str, Any]) -> str:
    payload = {
        "generated_at": value["generated_at"],
        "profiles": value["profiles"],
        "entries": value["entries"],
        "aliases": value["aliases"],
        "withdrawals": value["withdrawals"],
    }
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return _sha256(canonical)


def _asset_references() -> list[tuple[str, str]]:
    sitemap = ET.parse(ROOT / "examples/room-zero/public/sitemap.xml")
    namespace = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
    references: list[tuple[str, str]] = []
    for location in sitemap.getroot().findall(f"{namespace}url/{namespace}loc"):
        if location.text == "https://neuralstock.ai/":
            continue
        parts = urllib.parse.urlsplit(location.text or "").path.strip("/").split("/")
        assert parts[0] == "asset" and len(parts) == 3
        references.append((urllib.parse.unquote(parts[1]), urllib.parse.unquote(parts[2])))
    return references


def _fixture() -> dict[str, Any]:
    runtime = b"glTF" * 512
    source = b"BLENDER" * 256
    runtime_sha = _sha256(runtime)
    source_sha = _sha256(source)
    first_id, first_version = _asset_references()[0]
    manifest = {
        "id": first_id,
        "version": first_version,
        "artifacts": {
            "runtime": {
                "uri": f"/objects/sha256/{runtime_sha[:2]}/{runtime_sha}",
                "sha256": runtime_sha,
                "bytes": len(runtime),
                "media_type": "model/gltf-binary",
            },
            "source": {
                "uri": f"/objects/sha256/{source_sha[:2]}/{source_sha}",
                "sha256": source_sha,
                "bytes": len(source),
                "media_type": "application/x-blender",
            },
        },
    }
    manifest_bytes = _pretty_json(manifest)
    manifest_sha = _sha256(manifest_bytes)
    manifest_uri = f"/assets/{first_id}/{first_version}/manifest.json"
    entries = [
        {
            "asset": {"id": asset_id, "version": version},
            "manifest": {
                "uri": manifest_uri,
                "sha256": manifest_sha,
                "bytes": len(manifest_bytes),
            },
        }
        for asset_id, version in _asset_references()
    ]
    registry: dict[str, Any] = {
        "$schema": "https://schemas.neuralstock.ai/v0.2/registry.schema.json",
        "schema_version": "0.2",
        "document_type": "registry",
        "generated": True,
        "revision": "",
        "generated_at": "2026-08-01T00:00:00Z",
        "profiles": ["web-v1"],
        "entries": entries,
        "aliases": [
            {"id": asset_id, "alias": "latest", "version": version}
            for asset_id, version in _asset_references()
        ],
        "withdrawals": [],
    }
    registry["revision"] = _registry_revision(registry)
    return {
        "registry": _pretty_json(registry),
        "registry_value": registry,
        "manifest": manifest_bytes,
        "manifest_uri": manifest_uri,
        "runtime": runtime,
        "runtime_uri": manifest["artifacts"]["runtime"]["uri"],
        "source": source,
        "source_uri": manifest["artifacts"]["source"]["uri"],
    }


class _Handler(BaseHTTPRequestHandler):
    server_version = "NeuralStockVerifierTest/1"

    def log_message(self, _format: str, *_args: object) -> None:
        return

    def _send(
        self,
        status: int,
        body: bytes,
        content_type: str,
        *,
        cache_control: str | None = None,
        cors: bool = False,
        ranges: bool = False,
        extra: dict[str, str] | None = None,
    ) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        if cache_control is not None:
            self.send_header("Cache-Control", cache_control)
        if cors:
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Expose-Headers", EXPOSED_HEADERS)
        if ranges:
            self.send_header("Accept-Ranges", "bytes")
        for name, value in (extra or {}).items():
            self.send_header(name, value)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def do_GET(self) -> None:
        fixture = self.server.fixture  # type: ignore[attr-defined]
        kind = self.server.kind  # type: ignore[attr-defined]
        path = urllib.parse.urlsplit(self.path).path
        if kind == "www":
            if self.path != REDIRECT_PROBE:
                self._send(404, b"missing", "text/plain")
                return
            self.send_response(301)
            self.send_header(
                "Location",
                f"{self.server.site_origin}{REDIRECT_PROBE}",  # type: ignore[attr-defined]
            )
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if kind == "site":
            if path == "/.well-known/neuralstock.json":
                self._send(
                    200,
                    (ROOT / "discovery/neuralstock.json").read_bytes(),
                    "application/json; charset=utf-8",
                    cache_control="public, max-age=300, stale-while-revalidate=86400",
                    cors=True,
                )
            elif path == "/sitemap.xml":
                self._send(
                    200,
                    (ROOT / "examples/room-zero/public/sitemap.xml").read_bytes(),
                    "application/xml",
                )
            elif path == "/" or path.startswith("/asset/"):
                self._send(200, b"<!doctype html><title>NeuralStock test</title>", "text/html")
            else:
                self._send(404, b"missing", "text/plain")
            return
        if kind == "schema":
            if path in {"/v0.2/LICENSE", "/profiles/v0.2/LICENSE"}:
                self._send(
                    200,
                    (ROOT / "LICENSE").read_bytes(),
                    "text/plain",
                    cache_control=IMMUTABLE_CACHE,
                    cors=True,
                )
            elif path == "/v0.2/common.schema.json":
                body = (ROOT / "schemas/common.schema.json").read_bytes()
                self._send(
                    200,
                    body,
                    "application/schema+json",
                    cache_control=IMMUTABLE_CACHE,
                    cors=True,
                )
            elif path == "/profiles/v0.2/web-v1.json":
                body = (ROOT / "profiles/web-v1.json").read_bytes()
                self._send(
                    200,
                    body,
                    "application/json",
                    cache_control=IMMUTABLE_CACHE,
                    cors=True,
                )
            else:
                self._send(404, b"missing", "text/plain")
            return
        assert kind == "asset"
        revision = fixture["registry_value"]["revision"]
        if path in {"/registry.json", "/snapshots/latest.json"}:
            self._send(
                200,
                fixture["registry"],
                "application/json",
                cache_control=ALIAS_CACHE,
                cors=True,
            )
        elif path == f"/snapshots/{revision}/registry.json":
            self._send(
                200,
                fixture["registry"],
                "application/json",
                cache_control=IMMUTABLE_CACHE,
                cors=True,
            )
        elif path == fixture["manifest_uri"]:
            self._send(
                200,
                fixture["manifest"],
                "application/json",
                cache_control=IMMUTABLE_CACHE,
                cors=True,
            )
        elif path in {fixture["runtime_uri"], fixture["source_uri"]}:
            is_runtime = path == fixture["runtime_uri"]
            body = fixture["runtime"] if is_runtime else fixture["source"]
            content_type = "model/gltf-binary" if is_runtime else "application/x-blender"
            range_header = self.headers.get("Range")
            if range_header:
                prefix = "bytes=0-"
                assert range_header.startswith(prefix)
                last = int(range_header.removeprefix(prefix))
                ranged = body[: last + 1]
                self._send(
                    206,
                    ranged,
                    content_type,
                    cache_control=IMMUTABLE_CACHE,
                    cors=True,
                    ranges=True,
                    extra={"Content-Range": f"bytes 0-{last}/{len(body)}"},
                )
            else:
                self._send(
                    200,
                    body,
                    content_type,
                    cache_control=IMMUTABLE_CACHE,
                    cors=True,
                    ranges=True,
                )
        else:
            self._send(404, b"missing", "text/plain")


@contextmanager
def _server(kind: str, fixture: dict[str, Any]) -> Iterator[ThreadingHTTPServer]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    server.kind = kind  # type: ignore[attr-defined]
    server.fixture = fixture  # type: ignore[attr-defined]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        thread.join()
        server.server_close()


def _origin(server: ThreadingHTTPServer) -> str:
    return f"http://127.0.0.1:{server.server_port}"


def test_complete_production_verifier_accepts_matching_public_contract(
    tmp_path: Path,
) -> None:
    fixture = _fixture()
    release_root = tmp_path / "release"
    release_root.mkdir()
    (release_root / "registry.json").write_bytes(fixture["registry"])
    for relative in (Path("v0.2/LICENSE"), Path("profiles/v0.2/LICENSE")):
        target = release_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / "LICENSE").read_bytes())

    with ExitStack() as stack:
        asset = stack.enter_context(_server("asset", fixture))
        schema = stack.enter_context(_server("schema", fixture))
        site = stack.enter_context(_server("site", fixture))
        www = stack.enter_context(_server("www", fixture))
        www.site_origin = _origin(site)  # type: ignore[attr-defined]
        environment = {
            **os.environ,
            "NEURALSTOCK_VERIFY_ASSET_ORIGIN": _origin(asset),
            "NEURALSTOCK_VERIFY_SCHEMA_ORIGIN": _origin(schema),
            "NEURALSTOCK_VERIFY_SITE_ORIGIN": _origin(site),
            "NEURALSTOCK_VERIFY_WWW_ORIGIN": _origin(www),
        }
        completed = subprocess.run(
            [
                "sh",
                str(ROOT / "tools/verify-production.sh"),
                fixture["registry_value"]["revision"],
                str(release_root),
            ],
            cwd=ROOT,
            env=environment,
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )

    assert completed.returncode == 0, completed.stderr
    assert "Verified NeuralStock production revision" in completed.stdout
