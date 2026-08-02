#!/bin/sh
set -eu

usage() {
  >&2 echo "usage: $0 VERSION RELEASE_ROOT R2_PLAN IMAGE_METADATA OUTPUT_DIR"
  >&2 echo "requires NEURALSTOCK_RELEASE_TAG=vVERSION and NEURALSTOCK_SOURCE_COMMIT"
  exit 64
}

[ "$#" -eq 5 ] || usage

version=$1
release_root=$2
r2_plan=$3
image_metadata=$4
output_dir=$5
source_commit=${NEURALSTOCK_SOURCE_COMMIT:-}
release_tag=${NEURALSTOCK_RELEASE_TAG:-}

if ! printf '%s\n' "$version" | grep -Eq '^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$'; then
  >&2 echo "release version must be a semantic version without a v prefix: $version"
  exit 65
fi

if ! printf '%s\n' "$source_commit" | grep -Eq '^[0-9a-f]{40}$'; then
  >&2 echo "NEURALSTOCK_SOURCE_COMMIT must contain exactly 40 lowercase hexadecimal characters"
  exit 65
fi
if [ "$release_tag" != "v$version" ]; then
  >&2 echo "NEURALSTOCK_RELEASE_TAG must equal v$version"
  exit 65
fi

[ -d "$release_root" ] || {
  >&2 echo "release root does not exist: $release_root"
  exit 66
}
[ -f "$release_root/registry.json" ] || {
  >&2 echo "release root has no registry.json: $release_root"
  exit 66
}
[ -f "$r2_plan" ] || {
  >&2 echo "R2 plan does not exist: $r2_plan"
  exit 66
}
[ -f "$image_metadata" ] || {
  >&2 echo "image metadata does not exist: $image_metadata"
  exit 66
}

if [ -d "$output_dir" ] && [ -n "$(find "$output_dir" -mindepth 1 -print -quit)" ]; then
  >&2 echo "refusing to overwrite non-empty candidate directory: $output_dir"
  exit 73
fi

for command_name in cmp grep jq sha256sum uv; do
  command -v "$command_name" >/dev/null 2>&1 || {
    >&2 echo "required command is unavailable: $command_name"
    exit 69
  }
done

uv run --frozen neuralstock release verify --root "$release_root"

calculated_plan=$(mktemp)
cleanup() {
  rm -f "$calculated_plan"
}
trap cleanup 0 1 2 15
uv run --frozen neuralstock r2 plan --root "$release_root" >"$calculated_plan"
if ! cmp "$calculated_plan" "$r2_plan"; then
  >&2 echo "provided R2 plan is not reproducible from the release root"
  exit 65
fi

mkdir -p "$output_dir"
output_dir=$(CDPATH= cd -- "$output_dir" && pwd -P)
release_root=$(CDPATH= cd -- "$release_root" && pwd -P)
archive_name="neuralstock-release-$version.tar.gz"

uv run --frozen python tools/build-release-archive.py \
  "$release_root" \
  "$output_dir/$archive_name"

cp "$r2_plan" "$output_dir/r2-plan.json"
cp "$image_metadata" "$output_dir/worker-image-metadata.json"

registry_revision=$(jq -er '.revision' "$release_root/registry.json")
generated_at=$(jq -er '.generated_at' "$release_root/registry.json")
entry_count=$(jq -er '.entries | length' "$release_root/registry.json")

jq -n \
  --arg version "$version" \
  --arg release_tag "$release_tag" \
  --arg source_commit "$source_commit" \
  --arg registry_revision "$registry_revision" \
  --arg generated_at "$generated_at" \
  --arg archive "$archive_name" \
  --argjson entry_count "$entry_count" \
  '{
    format_version: "1",
    release_version: $version,
    package_version: $version,
    release_tag: $release_tag,
    source_commit: $source_commit,
    registry_revision: $registry_revision,
    registry_generated_at: $generated_at,
    registry_entries: $entry_count,
    release_archive: $archive
  }' >"$output_dir/release-metadata.json"

(
  cd "$output_dir"
  sha256sum \
    "$archive_name" \
    r2-plan.json \
    release-metadata.json \
    worker-image-metadata.json >SHA256SUMS
  sha256sum --check --strict SHA256SUMS
)

cleanup
trap - 0 1 2 15
echo "Release candidate created at $output_dir"
