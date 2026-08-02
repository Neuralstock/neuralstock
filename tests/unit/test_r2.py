from __future__ import annotations

import sys
from collections.abc import Callable
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from neuralstock.package import run_gltf_validator
from neuralstock.r2 import (
    ALIAS_CACHE_CONTROL,
    IMMUTABLE_CACHE_CONTROL,
    R2ImmutableConflict,
    build_upload_plan,
    execute_upload_plan,
    r2_client,
    sync_release,
)
from neuralstock.release import publish_release
from tests.unit.test_package import make_candidate, make_comparison, run_package


class PreconditionFailed(Exception):
    def __init__(self) -> None:
        super().__init__("precondition failed")
        self.response = {
            "ResponseMetadata": {"HTTPStatusCode": 412},
            "Error": {"Code": "PreconditionFailed"},
        }


class ObjectLockedByBucketPolicy(Exception):
    def __init__(self, code: str = "10069") -> None:
        super().__init__("the object is locked by the bucket policy")
        self.response = {
            "ResponseMetadata": {"HTTPStatusCode": 403},
            "Error": {"Code": code},
        }


class AccessDenied(Exception):
    def __init__(self) -> None:
        super().__init__("access denied")
        self.response = {
            "ResponseMetadata": {"HTTPStatusCode": 403},
            "Error": {"Code": "AccessDenied"},
        }


class FakeR2Client:
    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], dict[str, Any]] = {}
        self.calls: list[tuple[str, str, dict[str, Any]]] = []
        self.existing_error: Callable[[], Exception] = PreconditionFailed

    def put_object(self, **arguments: Any) -> dict[str, str]:
        body = arguments["Body"]
        payload = body.read() if hasattr(body, "read") else bytes(body)
        recorded = {key: value for key, value in arguments.items() if key != "Body"}
        self.calls.append(("put", arguments["Key"], recorded))
        identity = (arguments["Bucket"], arguments["Key"])
        if arguments.get("IfNoneMatch") == "*" and identity in self.objects:
            raise self.existing_error()
        self.objects[identity] = {
            "Body": payload,
            "Metadata": dict(arguments.get("Metadata", {})),
            "ContentType": arguments.get("ContentType"),
            "CacheControl": arguments.get("CacheControl"),
        }
        return {"ETag": '"fake"'}

    def head_object(self, **arguments: Any) -> dict[str, Any]:
        self.calls.append(("head", arguments["Key"], dict(arguments)))
        stored = self.objects[(arguments["Bucket"], arguments["Key"])]
        return {
            "ContentLength": len(stored["Body"]),
            "Metadata": dict(stored["Metadata"]),
            "ContentType": stored["ContentType"],
            "CacheControl": stored["CacheControl"],
        }

    def get_object(self, **arguments: Any) -> dict[str, Any]:
        self.calls.append(("get", arguments["Key"], dict(arguments)))
        stored = self.objects[(arguments["Bucket"], arguments["Key"])]
        return {"Body": BytesIO(stored["Body"])}


def _static_release(tmp_path: Path) -> Path:
    candidate = make_candidate(tmp_path)
    comparison = make_comparison(candidate, tmp_path)
    report = run_gltf_validator(candidate["blender"] / "model.glb")
    package = run_package(candidate, report=report, comparison=comparison).output
    release = tmp_path / "release"
    publish_release(
        [package],
        root=release,
        generated_at="2026-08-01T00:00:00Z",
    )
    return release


def test_upload_plan_and_sync_order_immutable_content_before_aliases(tmp_path: Path) -> None:
    release = _static_release(tmp_path)
    plan = build_upload_plan(release)
    client = FakeR2Client()

    result = execute_upload_plan(plan, bucket="neuralstock-public", client=client)

    put_calls = [call for call in client.calls if call[0] == "put"]
    assert [call[1] for call in put_calls] == [item.key for item in plan.items]
    assert [item.release_key for item in plan.items[-2:]] == [
        "registry.json",
        "snapshots/latest.json",
    ]
    assert all(item.immutable for item in plan.items[:-2])
    assert all(not item.immutable for item in plan.items[-2:])
    assert result.aliases_updated == (
        "registry.json",
        "snapshots/latest.json",
    )
    assert result.uploaded == tuple(item.key for item in plan.items[:-2])
    for item, (_, _, arguments) in zip(plan.items, put_calls, strict=True):
        assert arguments["Metadata"] == {"neuralstock-sha256": item.sha256}
        assert arguments["ContentType"] == item.content_type
        if item.immutable:
            assert arguments["IfNoneMatch"] == "*"
            assert arguments["CacheControl"] == IMMUTABLE_CACHE_CONTROL
        else:
            assert "IfNoneMatch" not in arguments
            assert arguments["CacheControl"] == ALIAS_CACHE_CONTROL


def test_immutable_only_phase_stops_before_both_aliases(tmp_path: Path) -> None:
    release = _static_release(tmp_path)
    plan = build_upload_plan(release)
    client = FakeR2Client()

    bootstrap = execute_upload_plan(
        plan,
        bucket="neuralstock-public",
        client=client,
        immutable_only=True,
    )

    immutable_keys = tuple(item.key for item in plan.items if item.immutable)
    assert bootstrap.uploaded == immutable_keys
    assert bootstrap.already_present == ()
    assert bootstrap.aliases_updated == ()
    assert [call[1] for call in client.calls if call[0] == "put"] == list(immutable_keys)
    assert not any(key in {"registry.json", "snapshots/latest.json"} for _, key, _ in client.calls)

    publication = execute_upload_plan(
        plan,
        bucket="neuralstock-public",
        client=client,
    )
    assert publication.uploaded == ()
    assert publication.already_present == immutable_keys
    assert publication.aliases_updated == ("registry.json", "snapshots/latest.json")


def test_upload_plan_contains_owned_immutable_contracts(tmp_path: Path) -> None:
    plan = build_upload_plan(_static_release(tmp_path))
    contracts = [item for item in plan.items if item.verify_existing_bytes]

    assert [item.release_key for item in contracts] == [
        "v0.2/asset.intent.schema.json",
        "v0.2/asset.schema.json",
        "v0.2/build-receipt.schema.json",
        "v0.2/common.schema.json",
        "v0.2/discovery.schema.json",
        "v0.2/inspection.schema.json",
        "v0.2/profile.schema.json",
        "v0.2/provenance.schema.json",
        "v0.2/registry.schema.json",
        "v0.2/LICENSE",
        "profiles/v0.2/web-v1.json",
        "profiles/v0.2/LICENSE",
    ]
    assert all(item.immutable for item in contracts)
    assert all(
        item.content_type == "application/schema+json"
        for item in contracts
        if item.release_key.startswith("v0.2/") and item.release_key != "v0.2/LICENSE"
    )
    assert (
        next(
            item for item in contracts if item.release_key == "profiles/v0.2/web-v1.json"
        ).content_type
        == "application/json"
    )
    assert all(
        next(item for item in contracts if item.release_key == key).content_type == "text/plain"
        for key in ("v0.2/LICENSE", "profiles/v0.2/LICENSE")
    )
    assert all(item.cache_control == IMMUTABLE_CACHE_CONTROL for item in contracts)
    assert all(
        item.source_path.read_bytes() == (plan.release_root / item.release_key).read_bytes()
        for item in contracts
    )


def test_sync_is_idempotent_when_remote_immutable_metadata_matches(tmp_path: Path) -> None:
    release = _static_release(tmp_path)
    client = FakeR2Client()
    plan = build_upload_plan(release)

    first = sync_release(release, bucket="assets", client=client)
    second = sync_release(release, bucket="assets", client=client)

    immutable_keys = tuple(item.key for item in plan.items if item.immutable)
    assert first.uploaded == immutable_keys
    assert not first.already_present
    assert not second.uploaded
    assert second.already_present == immutable_keys
    assert second.aliases_updated == ("registry.json", "snapshots/latest.json")
    second_run_calls = client.calls[len(plan.items) :]
    expected_immutable_calls = [
        action
        for item in plan.items
        if item.immutable
        for action in (("put", "head", "get") if item.verify_existing_bytes else ("put", "head"))
    ]
    assert [call[0] for call in second_run_calls[:-2]] == expected_immutable_calls
    assert [call[1] for call in second_run_calls[-2:]] == [
        "registry.json",
        "snapshots/latest.json",
    ]


def test_existing_contract_without_integrity_metadata_is_downloaded_and_verified(
    tmp_path: Path,
) -> None:
    release = _static_release(tmp_path)
    plan = build_upload_plan(release)
    contract = next(item for item in plan.items if item.release_key == "v0.2/discovery.schema.json")
    client = FakeR2Client()
    client.objects[("assets", contract.key)] = {
        "Body": contract.source_path.read_bytes(),
        "Metadata": {},
        "ContentType": contract.content_type,
        "CacheControl": contract.cache_control.replace(", ", ","),
    }

    result = execute_upload_plan(plan, bucket="assets", client=client)

    assert contract.key in result.already_present
    assert ("get", contract.key) in [(action, key) for action, key, _ in client.calls]


def test_existing_contract_without_metadata_must_match_exact_bytes(tmp_path: Path) -> None:
    release = _static_release(tmp_path)
    plan = build_upload_plan(release)
    contract = next(item for item in plan.items if item.release_key == "v0.2/discovery.schema.json")
    client = FakeR2Client()
    payload = bytearray(contract.source_path.read_bytes())
    payload[-2] ^= 1
    client.objects[("assets", contract.key)] = {
        "Body": bytes(payload),
        "Metadata": {},
        "ContentType": contract.content_type,
        "CacheControl": contract.cache_control,
    }

    with pytest.raises(R2ImmutableConflict, match="different content"):
        execute_upload_plan(plan, bucket="assets", client=client)

    assert not any(call[1] in {"registry.json", "snapshots/latest.json"} for call in client.calls)


def test_existing_graph_object_still_requires_integrity_metadata(tmp_path: Path) -> None:
    release = _static_release(tmp_path)
    plan = build_upload_plan(release)
    graph_object = next(
        item for item in plan.items if item.immutable and not item.verify_existing_bytes
    )
    client = FakeR2Client()
    client.objects[("assets", graph_object.key)] = {
        "Body": graph_object.source_path.read_bytes(),
        "Metadata": {},
        "ContentType": graph_object.content_type,
        "CacheControl": graph_object.cache_control,
    }

    with pytest.raises(R2ImmutableConflict, match="lacks matching integrity metadata"):
        execute_upload_plan(plan, bucket="assets", client=client)

    assert not any(call[1] in {"registry.json", "snapshots/latest.json"} for call in client.calls)


@pytest.mark.parametrize("lock_code", ["10069", "ObjectLockedByBucketPolicy"])
def test_bucket_locked_existing_graph_is_downloaded_and_verified(
    tmp_path: Path,
    lock_code: str,
) -> None:
    release = _static_release(tmp_path)
    plan = build_upload_plan(release)
    graph_object = next(
        item for item in plan.items if item.immutable and not item.verify_existing_bytes
    )
    client = FakeR2Client()
    client.existing_error = lambda: ObjectLockedByBucketPolicy(lock_code)
    client.objects[("assets", graph_object.key)] = {
        "Body": graph_object.source_path.read_bytes(),
        "Metadata": {},
        "ContentType": graph_object.content_type,
        "CacheControl": graph_object.cache_control,
    }

    result = execute_upload_plan(plan, bucket="assets", client=client)

    assert graph_object.key in result.already_present
    assert ("head", graph_object.key) in [(action, key) for action, key, _ in client.calls]
    assert ("get", graph_object.key) in [(action, key) for action, key, _ in client.calls]


def test_bucket_locked_existing_graph_must_match_downloaded_bytes(tmp_path: Path) -> None:
    release = _static_release(tmp_path)
    plan = build_upload_plan(release)
    graph_object = next(
        item for item in plan.items if item.immutable and not item.verify_existing_bytes
    )
    client = FakeR2Client()
    client.existing_error = ObjectLockedByBucketPolicy
    payload = bytearray(graph_object.source_path.read_bytes())
    payload[-1] ^= 1
    client.objects[("assets", graph_object.key)] = {
        "Body": bytes(payload),
        "Metadata": {},
        "ContentType": graph_object.content_type,
        "CacheControl": graph_object.cache_control,
    }

    with pytest.raises(R2ImmutableConflict, match="different content"):
        execute_upload_plan(plan, bucket="assets", client=client)

    assert ("get", graph_object.key) in [(action, key) for action, key, _ in client.calls]
    assert not any(call[1] in {"registry.json", "snapshots/latest.json"} for call in client.calls)


def test_unrelated_403_is_not_treated_as_an_existing_object(tmp_path: Path) -> None:
    release = _static_release(tmp_path)
    plan = build_upload_plan(release)
    first = plan.items[0]
    client = FakeR2Client()
    client.existing_error = AccessDenied
    client.objects[("assets", first.key)] = {
        "Body": first.source_path.read_bytes(),
        "Metadata": {"neuralstock-sha256": first.sha256},
        "ContentType": first.content_type,
        "CacheControl": first.cache_control,
    }

    with pytest.raises(AccessDenied):
        execute_upload_plan(plan, bucket="assets", client=client)

    assert not any(call[0] in {"head", "get"} for call in client.calls)


@pytest.mark.parametrize(
    ("metadata_digest", "extra_bytes"),
    [("0" * 64, b""), (None, b"different-size")],
)
def test_existing_immutable_object_must_match_digest_and_size(
    tmp_path: Path,
    metadata_digest: str | None,
    extra_bytes: bytes,
) -> None:
    release = _static_release(tmp_path)
    plan = build_upload_plan(release)
    first = plan.items[0]
    client = FakeR2Client()
    payload = first.source_path.read_bytes() + extra_bytes
    client.objects[("assets", first.key)] = {
        "Body": payload,
        "Metadata": {
            "neuralstock-sha256": metadata_digest or first.sha256,
        },
        "ContentType": first.content_type,
        "CacheControl": IMMUTABLE_CACHE_CONTROL,
    }

    with pytest.raises(R2ImmutableConflict, match="already contains different content"):
        execute_upload_plan(plan, bucket="assets", client=client)

    assert not any(call[1] in {"registry.json", "snapshots/latest.json"} for call in client.calls)


@pytest.mark.parametrize(
    "prefix",
    [
        "/absolute",
        "trailing/",
        "../escape",
        "nested/../../escape",
        "nested\\escape",
        "double//slash",
        ".",
        "space not allowed",
    ],
)
def test_upload_plan_rejects_unsafe_prefixes(tmp_path: Path, prefix: str) -> None:
    release = _static_release(tmp_path)

    with pytest.raises(ValueError, match="R2 prefixes are not supported"):
        build_upload_plan(release, prefix=prefix)


def test_r2_client_uses_lazy_boto3_factory_with_auto_region(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, Any]] = []
    fake_boto3 = SimpleNamespace(client=lambda **kwargs: calls.append(kwargs) or object())
    monkeypatch.setitem(sys.modules, "boto3", fake_boto3)

    result = r2_client(
        endpoint_url="https://account-id.r2.cloudflarestorage.com",
        access_key_id="access",
        secret_access_key="secret",
    )

    assert result is not None
    assert calls == [
        {
            "service_name": "s3",
            "endpoint_url": "https://account-id.r2.cloudflarestorage.com",
            "region_name": "auto",
            "aws_access_key_id": "access",
            "aws_secret_access_key": "secret",
        }
    ]


@pytest.mark.parametrize(
    "endpoint",
    [
        "http://account-id.r2.cloudflarestorage.com",
        "https://example.com",
        "https://user:secret@account-id.r2.cloudflarestorage.com",
    ],
)
def test_r2_client_rejects_non_cloudflare_or_insecure_endpoints(endpoint: str) -> None:
    with pytest.raises(ValueError, match="HTTPS Cloudflare R2"):
        r2_client(
            endpoint_url=endpoint,
            access_key_id="access",
            secret_access_key="secret",
        )


def test_r2_client_never_falls_back_to_ambient_credentials() -> None:
    with pytest.raises(ValueError, match="ambient AWS credentials are disabled"):
        r2_client(endpoint_url="https://account-id.r2.cloudflarestorage.com")
