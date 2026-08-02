"""Command-line entry point for NeuralStock project tooling."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Sequence
from pathlib import Path

from neuralstock import __version__
from neuralstock.canonical import read_json, sha256_file, sha256_json
from neuralstock.package import PackageError, package_asset, parse_parameter_values
from neuralstock.r2 import R2SyncError, build_upload_plan, execute_upload_plan, r2_client
from neuralstock.registry import build_registry
from neuralstock.release import publish_release, verify_release
from neuralstock.schema import DocumentValidationError, require_valid_document
from neuralstock.storage import publish_object


def _validate(arguments: argparse.Namespace) -> int:
    failed = False
    for value in arguments.documents:
        path = Path(value)
        try:
            require_valid_document(arguments.schema, read_json(path))
        except (OSError, json.JSONDecodeError, DocumentValidationError, TypeError) as error:
            failed = True
            print(f"FAIL {path}: {error}", file=sys.stderr)
        else:
            print(f"OK   {path}")
    return 1 if failed else 0


def _hash(arguments: argparse.Namespace) -> int:
    if arguments.json:
        print(sha256_json(read_json(arguments.path)))
    else:
        print(sha256_file(arguments.path))
    return 0


def _store_object(arguments: argparse.Namespace) -> int:
    published = publish_object(arguments.path, arguments.root)
    print(
        json.dumps(
            {
                "already_present": published.already_present,
                "key": published.key,
                "sha256": published.digest,
                "size_bytes": published.size_bytes,
            },
            sort_keys=True,
        )
    )
    return 0


def _build_registry(arguments: argparse.Namespace) -> int:
    registry = build_registry(
        arguments.manifests,
        output=arguments.output,
        generated_at=arguments.generated_at,
    )
    print(
        json.dumps(
            {
                "entries": len(registry["entries"]),
                "output": str(arguments.output),
                "revision": registry["revision"],
            },
            sort_keys=True,
        )
    )
    return 0


def _package(arguments: argparse.Namespace) -> int:
    try:
        result = package_asset(
            intent_path=arguments.intent,
            provenance_path=arguments.provenance,
            blender_output=arguments.blender_output,
            output=arguments.output,
            generated_at=arguments.generated_at,
            image_digest=arguments.image_digest,
            parameter_values=parse_parameter_values(arguments.parameters_json),
            platform=arguments.platform,
            comparison_blender_output=arguments.comparison_blender_output,
        )
    except (
        DocumentValidationError,
        FileExistsError,
        OSError,
        PackageError,
        TypeError,
    ) as error:
        print(f"FAIL package: {error}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "asset": f"{result.asset['id']}@{result.asset['version']}",
                "build_key": result.build_key,
                "output": str(result.output),
            },
            sort_keys=True,
        )
    )
    return 0


def _publish_release(arguments: argparse.Namespace) -> int:
    try:
        result = publish_release(
            arguments.packages,
            root=arguments.root,
            generated_at=arguments.generated_at,
        )
    except (DocumentValidationError, OSError, TypeError, ValueError) as error:
        print(f"FAIL release: {error}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "assets": result.asset_count,
                "objects": result.object_count,
                "revision": result.revision,
                "root": str(result.root),
            },
            sort_keys=True,
        )
    )
    return 0


def _verify_release(arguments: argparse.Namespace) -> int:
    try:
        result = verify_release(arguments.root, registry_path=arguments.registry)
    except (DocumentValidationError, OSError, TypeError, ValueError) as error:
        print(f"FAIL release: {error}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "artifacts": result.artifact_count,
                "assets": result.asset_count,
                "revision": result.revision,
                "verified_bytes": result.verified_bytes,
            },
            sort_keys=True,
        )
    )
    return 0


def _r2_plan(arguments: argparse.Namespace) -> int:
    try:
        plan = build_upload_plan(arguments.root)
    except (DocumentValidationError, OSError, TypeError, ValueError) as error:
        print(f"FAIL R2 plan: {error}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "items": [
                    {
                        "bytes": item.size_bytes,
                        "content_type": item.content_type,
                        "immutable": item.immutable,
                        "key": item.key,
                        "sha256": item.sha256,
                    }
                    for item in plan.items
                ],
                "revision": plan.revision,
            },
            sort_keys=True,
        )
    )
    return 0


def _r2_sync(arguments: argparse.Namespace) -> int:
    access_key_id = os.environ.get("NEURALSTOCK_R2_ACCESS_KEY_ID")
    secret_access_key = os.environ.get("NEURALSTOCK_R2_SECRET_ACCESS_KEY")
    try:
        client = r2_client(
            endpoint_url=arguments.endpoint_url,
            access_key_id=access_key_id,
            secret_access_key=secret_access_key,
        )
        plan = build_upload_plan(arguments.root)
        result = execute_upload_plan(
            plan,
            bucket=arguments.bucket,
            client=client,
            immutable_only=arguments.immutable_only,
        )
    except (
        DocumentValidationError,
        OSError,
        R2SyncError,
        RuntimeError,
        TypeError,
        ValueError,
    ) as error:
        print(f"FAIL R2 sync: {error}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "aliases_updated": list(result.aliases_updated),
                "already_present": len(result.already_present),
                "immutable_only": arguments.immutable_only,
                "mode": "immutable-only" if arguments.immutable_only else "full",
                "revision": plan.revision,
                "uploaded": len(result.uploaded),
            },
            sort_keys=True,
        )
    )
    return 0


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(
        prog="neuralstock",
        description="Validate, build, package, and publish NeuralStock assets.",
    )
    root.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    commands = root.add_subparsers(dest="command", required=True)

    validate = commands.add_parser("validate", help="validate JSON documents")
    validate.add_argument("--schema", required=True, help="schema name, for example asset.intent")
    validate.add_argument("documents", nargs="+", help="JSON files to validate")
    validate.set_defaults(handler=_validate)

    digest = commands.add_parser("sha256", help="hash a file or canonical JSON document")
    digest.add_argument("path")
    digest.add_argument("--json", action="store_true", help="hash canonicalized JSON")
    digest.set_defaults(handler=_hash)

    store = commands.add_parser("store-object", help="copy a file into a local object store")
    store.add_argument("path")
    store.add_argument("--root", required=True)
    store.set_defaults(handler=_store_object)

    package = commands.add_parser(
        "package",
        help="validate Blender output and create a publishable asset package",
    )
    package.add_argument("--intent", required=True, type=Path)
    package.add_argument("--provenance", required=True, type=Path)
    package.add_argument("--blender-output", required=True, type=Path)
    package.add_argument(
        "--comparison-blender-output",
        type=Path,
        help=(
            "independent second Blender output directory; verify exact runtime/core outputs "
            "and narrowly documented Blender/PNG nondeterminism"
        ),
    )
    package.add_argument("--output", required=True, type=Path)
    package.add_argument(
        "--generated-at",
        required=True,
        help="fixed RFC 3339 publication timestamp",
    )
    package.add_argument(
        "--image-digest",
        required=True,
        help="pinned Blender OCI image digest in sha256:<digest> form",
    )
    package.add_argument(
        "--parameters-json",
        required=True,
        help="exact JSON object of parameter overrides used by Blender",
    )
    package.add_argument(
        "--platform",
        choices=("linux/amd64", "linux/arm64"),
        default="linux/amd64",
    )
    package.set_defaults(handler=_package)

    registry = commands.add_parser("registry", help="build and inspect static registries")
    registry_commands = registry.add_subparsers(dest="registry_command", required=True)
    registry_build = registry_commands.add_parser("build", help="build a registry snapshot")
    registry_build.add_argument("manifests", nargs="+", help="published asset.json files")
    registry_build.add_argument("--output", required=True, type=Path)
    registry_build.add_argument(
        "--generated-at",
        help="fixed RFC 3339 timestamp; defaults to SOURCE_DATE_EPOCH or now",
    )
    registry_build.set_defaults(handler=_build_registry)

    release = commands.add_parser("release", help="publish or verify a static release")
    release_commands = release.add_subparsers(dest="release_command", required=True)
    release_publish = release_commands.add_parser(
        "publish", help="atomically publish validated packages to a local static root"
    )
    release_publish.add_argument("packages", nargs="+", type=Path)
    release_publish.add_argument("--root", required=True, type=Path)
    release_publish.add_argument("--generated-at", required=True)
    release_publish.set_defaults(handler=_publish_release)
    release_verify = release_commands.add_parser(
        "verify", help="traverse and verify a complete static release"
    )
    release_verify.add_argument("--root", required=True, type=Path)
    release_verify.add_argument("--registry", type=Path)
    release_verify.set_defaults(handler=_verify_release)

    r2 = commands.add_parser("r2", help="plan or execute an optional Cloudflare R2 sync")
    r2_commands = r2.add_subparsers(dest="r2_command", required=True)
    r2_plan = r2_commands.add_parser("plan", help="print the deterministic upload plan")
    r2_plan.add_argument("--root", required=True, type=Path)
    r2_plan.set_defaults(handler=_r2_plan)
    r2_sync = r2_commands.add_parser("sync", help="upload a verified release to R2")
    r2_sync.add_argument("--root", required=True, type=Path)
    r2_sync.add_argument("--bucket", required=True)
    r2_sync.add_argument("--endpoint-url", required=True)
    r2_sync.add_argument(
        "--immutable-only",
        action="store_true",
        help="upload and verify every immutable item, but do not update registry aliases",
    )
    r2_sync.set_defaults(handler=_r2_sync)

    return root


def main(argv: Sequence[str] | None = None) -> int:
    arguments = parser().parse_args(argv)
    return int(arguments.handler(arguments))
