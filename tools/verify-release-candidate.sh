#!/bin/sh
set -eu

usage() {
  >&2 echo "usage: $0 CANDIDATE_DIR [EXPECTED_VERSION [EXPECTED_REVISION]]"
  exit 64
}

[ "$#" -ge 1 ] && [ "$#" -le 3 ] || usage

candidate_dir=$1
expected_version=${2:-}
expected_revision=${3:-}

[ -d "$candidate_dir" ] || {
  >&2 echo "candidate directory does not exist: $candidate_dir"
  exit 66
}

for command_name in jq sha256sum tar uv; do
  command -v "$command_name" >/dev/null 2>&1 || {
    >&2 echo "required command is unavailable: $command_name"
    exit 69
  }
done

candidate_dir=$(CDPATH= cd -- "$candidate_dir" && pwd -P)
for required in SHA256SUMS r2-plan.json release-metadata.json worker-image-metadata.json; do
  [ -f "$candidate_dir/$required" ] || {
    >&2 echo "release candidate is missing $required"
    exit 65
  }
done

if ! awk '
  NF != 2 { exit 1 }
  length($1) != 64 || $1 !~ /^[0-9a-f]+$/ { exit 1 }
  $2 !~ /^\*?(neuralstock-release-[0-9A-Za-z.+-]+\.tar\.gz|r2-plan\.json|release-metadata\.json|worker-image-metadata\.json)$/ { exit 1 }
  END { if (NR != 4) exit 1 }
' "$candidate_dir/SHA256SUMS"; then
  >&2 echo "SHA256SUMS must contain exactly the four expected candidate files"
  exit 65
fi

(
  cd "$candidate_dir"
  sha256sum --check --strict SHA256SUMS
)

format_version=$(jq -er '.format_version' "$candidate_dir/release-metadata.json")
version=$(jq -er '.release_version' "$candidate_dir/release-metadata.json")
package_version=$(jq -er '.package_version' "$candidate_dir/release-metadata.json")
release_tag=$(jq -er '.release_tag' "$candidate_dir/release-metadata.json")
revision=$(jq -er '.registry_revision' "$candidate_dir/release-metadata.json")
source_commit=$(jq -er '.source_commit' "$candidate_dir/release-metadata.json")
archive_name=$(jq -er '.release_archive' "$candidate_dir/release-metadata.json")

[ "$format_version" = 1 ] || {
  >&2 echo "candidate metadata format is unsupported: $format_version"
  exit 65
}
if ! printf '%s\n' "$version" \
  | grep -Eq '^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$'; then
  >&2 echo "candidate release version is not a plain semantic version"
  exit 65
fi
if ! printf '%s\n' "$source_commit" | grep -Eq '^[0-9a-f]{40}$'; then
  >&2 echo "candidate source_commit must be 40 lowercase hexadecimal characters"
  exit 65
fi
[ "$package_version" = "$version" ] || {
  >&2 echo "candidate package and release versions differ"
  exit 65
}
[ "$release_tag" = "v$version" ] || {
  >&2 echo "candidate release tag does not match its version"
  exit 65
}
[ "$archive_name" = "neuralstock-release-$version.tar.gz" ] || {
  >&2 echo "candidate release archive name does not match its version"
  exit 65
}

[ -z "$expected_version" ] || [ "$version" = "$expected_version" ] || {
  >&2 echo "candidate version mismatch: expected $expected_version, got $version"
  exit 65
}
[ -z "$expected_revision" ] || [ "$revision" = "$expected_revision" ] || {
  >&2 echo "candidate registry revision mismatch: expected $expected_revision, got $revision"
  exit 65
}
[ -f "$candidate_dir/$archive_name" ] || {
  >&2 echo "candidate release archive is missing: $archive_name"
  exit 65
}

if tar -tzf "$candidate_dir/$archive_name" | awk '
  /^\// { exit 1 }
  /(^|\/)\.\.($|\/)/ { exit 1 }
'; then
  :
else
  >&2 echo "candidate archive contains an unsafe path"
  exit 65
fi

temporary_root=$(mktemp -d)
cleanup() {
  rm -rf "$temporary_root"
}
trap cleanup 0 1 2 15

tar \
  --extract \
  --gzip \
  --file="$candidate_dir/$archive_name" \
  --directory="$temporary_root" \
  --no-same-owner \
  --no-same-permissions

uv run --frozen neuralstock release verify --root "$temporary_root"
actual_revision=$(jq -er '.revision' "$temporary_root/registry.json")
[ "$actual_revision" = "$revision" ] || {
  >&2 echo "extracted registry revision does not match release metadata"
  exit 65
}

uv run --frozen python - \
  "$temporary_root" \
  "$candidate_dir/r2-plan.json" \
  "$revision" <<'PY'
import hashlib
import json
import sys
from pathlib import Path, PurePosixPath

release_root = Path(sys.argv[1]).resolve()
plan_path = Path(sys.argv[2])
expected_revision = sys.argv[3]
plan = json.loads(plan_path.read_text())

if plan.get("revision") != expected_revision:
    raise SystemExit("R2 plan revision does not match release metadata")
items = plan.get("items")
if not isinstance(items, list) or len(items) < 3:
    raise SystemExit("R2 plan must contain immutable content and two aliases")
if [item.get("key") for item in items[-2:]] != [
    "registry.json",
    "snapshots/latest.json",
]:
    raise SystemExit("R2 plan aliases are missing or not last")

seen: set[str] = set()
by_key: dict[str, dict[str, object]] = {}
alias_phase = False
for item in items:
    if not isinstance(item, dict):
        raise SystemExit("R2 plan item must be an object")
    key = item.get("key")
    digest = item.get("sha256")
    size = item.get("bytes")
    content_type = item.get("content_type")
    immutable = item.get("immutable")
    if not isinstance(key, str) or not key:
        raise SystemExit("R2 plan item has no key")
    path = PurePosixPath(key)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise SystemExit(f"R2 plan contains unsafe key: {key!r}")
    if "\\" in key:
        raise SystemExit(f"R2 plan contains unsafe key: {key!r}")
    if key in seen:
        raise SystemExit(f"R2 plan contains duplicate key: {key}")
    seen.add(key)
    if not isinstance(immutable, bool):
        raise SystemExit(f"R2 plan immutable flag is invalid: {key}")
    if immutable:
        if alias_phase:
            raise SystemExit("R2 plan places immutable content after an alias")
    else:
        alias_phase = True
        if key not in {"registry.json", "snapshots/latest.json"}:
            raise SystemExit(f"R2 plan contains unsupported mutable key: {key}")
    if (
        not isinstance(digest, str)
        or len(digest) != 64
        or any(character not in "0123456789abcdef" for character in digest)
    ):
        raise SystemExit(f"R2 plan digest is invalid: {key}")
    if not isinstance(size, int) or isinstance(size, bool) or size < 0:
        raise SystemExit(f"R2 plan byte count is invalid: {key}")
    if not isinstance(content_type, str) or not content_type:
        raise SystemExit(f"R2 plan content type is invalid: {key}")
    local_path = release_root.joinpath(*path.parts)
    if not local_path.is_file() or local_path.is_symlink():
        raise SystemExit(f"R2 plan key is absent from release archive: {key}")
    payload = local_path.read_bytes()
    if len(payload) != size or hashlib.sha256(payload).hexdigest() != digest:
        raise SystemExit(f"R2 plan descriptor does not match release file: {key}")
    by_key[key] = item

schema_names = {
    "asset.intent.schema.json",
    "asset.schema.json",
    "build-receipt.schema.json",
    "common.schema.json",
    "discovery.schema.json",
    "inspection.schema.json",
    "profile.schema.json",
    "provenance.schema.json",
    "registry.schema.json",
}
license_digest = "db925e3df4ed5c6de89e903dd30ecb004f6ba4ae63d9aa98d8570ef50be87200"
schema_license_key = "v0.2/LICENSE"
profile_license_key = "profiles/v0.2/LICENSE"
schema_license_bytes = (release_root / schema_license_key).read_bytes()
if hashlib.sha256(schema_license_bytes).hexdigest() != license_digest:
    raise SystemExit("R2 schema license companion has the wrong SHA-256")
if (release_root / profile_license_key).read_bytes() != schema_license_bytes:
    raise SystemExit("R2 profile license companion differs from the schema license")
try:
    license_text = schema_license_bytes.decode("utf-8")
except UnicodeDecodeError as error:
    raise SystemExit("R2 license companion is not UTF-8") from error
for license_key in (schema_license_key, profile_license_key):
    item = by_key.get(license_key)
    if item is None or item["immutable"] is not True:
        raise SystemExit(f"R2 plan is missing immutable license: {license_key}")
    if item["content_type"] != "text/plain":
        raise SystemExit(f"R2 license has the wrong content type: {license_key}")

def expected_notice(license_uri: str) -> dict[str, str]:
    return {
        "spdx_id": "MIT",
        "copyright": "Copyright (c) 2026 NeuralStock contributors",
        "license_uri": license_uri,
        "license_sha256": license_digest,
        "license_text": license_text,
    }

for schema_name in sorted(schema_names):
    key = f"v0.2/{schema_name}"
    item = by_key.get(key)
    if item is None or item["immutable"] is not True:
        raise SystemExit(f"R2 plan is missing immutable schema: {key}")
    if item["content_type"] != "application/schema+json":
        raise SystemExit(f"R2 schema has the wrong content type: {key}")
    document = json.loads((release_root / key).read_text())
    expected_id = f"https://schemas.neuralstock.ai/{key}"
    if document.get("$id") != expected_id:
        raise SystemExit(f"R2 schema has the wrong $id: {key}")
    if document.get("x-neuralstock-document-license") != expected_notice(
        "https://schemas.neuralstock.ai/v0.2/LICENSE"
    ):
        raise SystemExit(f"R2 schema has incomplete MIT license metadata: {key}")

profile_key = "profiles/v0.2/web-v1.json"
profile_item = by_key.get(profile_key)
if profile_item is None or profile_item["immutable"] is not True:
    raise SystemExit(f"R2 plan is missing immutable profile: {profile_key}")
if profile_item["content_type"] != "application/json":
    raise SystemExit(f"R2 profile has the wrong content type: {profile_key}")
profile = json.loads((release_root / profile_key).read_text())
if profile.get("$schema") != "https://schemas.neuralstock.ai/v0.2/profile.schema.json":
    raise SystemExit("R2 web-v1 profile has the wrong $schema")
if profile.get("x-neuralstock-document-license") != expected_notice(
    "https://schemas.neuralstock.ai/profiles/v0.2/LICENSE"
):
    raise SystemExit("R2 web-v1 profile has incomplete MIT license metadata")
PY

echo "Verified NeuralStock $version candidate at revision $revision"
