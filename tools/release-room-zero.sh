#!/bin/sh
set -eu

usage() {
  >&2 echo "usage: $0 [ACCEPTED_SOURCE_ROOT [WORK_ROOT] [RELEASE_ROOT]]"
  exit 64
}

[ "$#" -le 3 ] || usage

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
project_root=$(dirname -- "$script_dir")
caller_root=$(pwd -P)
source_root=${1:-"$project_root/assets/room-zero"}
work_root=${2:-"$project_root/work/room-zero-release"}
release_root=${3:-"$project_root/dist/release"}
build_time=${NEURALSTOCK_BUILD_TIME:-"2026-08-01T00:00:00Z"}
publish_time=${NEURALSTOCK_PUBLISH_TIME:-"2026-08-01T21:00:00Z"}
image_tag=${NEURALSTOCK_BLENDER_IMAGE:-"neuralstock-blender:4.5.12"}
build_wall_seconds=${NEURALSTOCK_BUILD_WALL_SECONDS:-1800}
build_output_bytes=${NEURALSTOCK_BUILD_OUTPUT_BYTES:-536870912}
buildkit_image="moby/buildkit:v0.30.0@sha256:0168606be2315b7c807a03b3d8aa79beefdb31c98740cebdffdfeebf31190c9f"

case "$build_wall_seconds" in *[!0-9]* | "") usage ;; esac
case "$build_output_bytes" in *[!0-9]* | "") usage ;; esac
[ "$build_wall_seconds" -gt 0 ] || usage
[ "$build_output_bytes" -gt 0 ] || usage

case "$source_root" in /*) ;; *) source_root="$caller_root/$source_root" ;; esac
case "$work_root" in /*) ;; *) work_root="$caller_root/$work_root" ;; esac
case "$release_root" in /*) ;; *) release_root="$caller_root/$release_root" ;; esac

[ -d "$source_root" ] || {
  >&2 echo "accepted source root does not exist: $source_root"
  exit 66
}
source_root=$(CDPATH= cd -- "$source_root" && pwd -P)

for target in "$work_root" "$release_root"; do
  if [ -d "$target" ] && [ -n "$(find "$target" -mindepth 1 -print -quit)" ]; then
    >&2 echo "refusing to overwrite non-empty output directory: $target"
    exit 73
  fi
done

for command_name in docker jq node pnpm tar uv; do
  command -v "$command_name" >/dev/null 2>&1 || {
    >&2 echo "required command is unavailable: $command_name"
    exit 69
  }
done

cd "$project_root"
uv sync --frozen --extra dev
pnpm install --frozen-lockfile
mkdir -p "$work_root" "$release_root"
work_root=$(CDPATH= cd -- "$work_root" && pwd -P)
release_root=$(CDPATH= cd -- "$release_root" && pwd -P)
image_archive="$work_root/neuralstock-blender.docker.tar"
image_metadata="$work_root/neuralstock-blender.metadata.json"
builder_name="neuralstock-v01-$$"
cleanup_builder() {
  docker buildx rm "$builder_name" >/dev/null 2>&1 || :
}
trap cleanup_builder 0 1 2 15
docker buildx create \
  --name "$builder_name" \
  --driver docker-container \
  --driver-opt "image=$buildkit_image" \
  --bootstrap >/dev/null
docker buildx build \
  --builder "$builder_name" \
  --no-cache \
  --provenance=false \
  --build-arg SOURCE_DATE_EPOCH=1785542400 \
  --platform linux/amd64 \
  --file container/Dockerfile \
  --tag "$image_tag" \
  --metadata-file "$image_metadata" \
  --output "type=docker,dest=$image_archive,rewrite-timestamp=true,compression=gzip,compression-level=6,oci-mediatypes=false" \
  .
image_digest=$(jq -r '."containerimage.digest"' "$image_metadata")
config_digest=$(jq -r '."containerimage.config.digest"' "$image_metadata")
expected_image_digest=$(jq -r '.manifest_digest' container/image.lock.json)
expected_config_digest=$(jq -r '.config_digest' container/image.lock.json)
if [ "$image_digest" != "$expected_image_digest" ] || \
  [ "$config_digest" != "$expected_config_digest" ]; then
  >&2 echo "rebuilt image does not match container/image.lock.json"
  exit 65
fi
docker load --input "$image_archive"
loaded_id=$(docker image inspect "$image_tag" --format '{{.Id}}')
case "$loaded_id" in
  "$image_digest" | "$config_digest") ;;
  *)
    >&2 echo "loaded image identity does not match the exported manifest or config"
    exit 65
    ;;
esac
cleanup_builder
trap - 0 1 2 15

build_a="$work_root/build-a"
build_b="$work_root/build-b"
packages_root="$work_root/packages"
mkdir -p "$build_a" "$build_b" "$packages_root"
build_a=$(CDPATH= cd -- "$build_a" && pwd -P)
build_b=$(CDPATH= cd -- "$build_b" && pwd -P)

active_container=""
active_archive=""
cleanup_runtime() {
  if [ -n "$active_container" ]; then
    docker rm --force "$active_container" >/dev/null 2>&1 || :
  fi
  if [ -n "$active_archive" ]; then
    rm -f "$active_archive"
  fi
}
trap cleanup_runtime 0 1 2 15

run_batch() {
  output_root=$1
  label=$2
  active_container="neuralstock-v01-${label}-$$"
  active_archive="$work_root/${label}-output.tar"
  docker create \
    --name "$active_container" \
    --platform linux/amd64 \
    --network none \
    --read-only \
    --cap-drop ALL \
    --security-opt no-new-privileges \
    --pids-limit 1024 \
    --cpus 4 \
    --memory 12g \
    --tmpfs /tmp:rw,nosuid,nodev,size=2g \
    --tmpfs "/output:rw,nosuid,nodev,size=$build_output_bytes,mode=1777" \
    --mount "type=bind,src=$source_root,dst=/input,readonly" \
    --env "NEURALSTOCK_JOB_BUILD_TIME=$build_time" \
    --entrypoint /bin/sh \
    "$image_tag" \
    -c '
      set -eu
      /usr/local/bin/neuralstock-blender batch \
        --source-root /input \
        --asset-version 1.0.1 \
        --generated-at "$NEURALSTOCK_JOB_BUILD_TIME" \
        --preview-resolution 192 \
        --output-dir /output >&2
      tar --create --file=- --directory=/output .
    ' >/dev/null

  set +e
  uv run --frozen python tools/run-with-timeout.py \
    "$build_wall_seconds" docker start --attach "$active_container" \
    >"$active_archive"
  build_status=$?
  set -e
  if [ "$build_status" -ne 0 ]; then
    docker rm --force "$active_container" >/dev/null 2>&1 || :
    active_container=""
    return "$build_status"
  fi
  tar --extract --file "$active_archive" --directory "$output_root"
  rm "$active_archive"
  active_archive=""
  docker rm "$active_container" >/dev/null
  active_container=""
}

run_batch "$build_a" build-a
run_batch "$build_b" build-b
trap - 0 1 2 15

for first in "$build_a"/*/*; do
  relative=${first#"$build_a"/}
  second="$build_b/$relative"
  [ -f "$second" ] || {
    >&2 echo "comparison build is missing: $relative"
    exit 65
  }
  cmp "$first" "$second"
done
cmp "$build_a/room-zero-build.json" "$build_b/room-zero-build.json"

for intent in catalog/*/1.0.1/asset.intent.json; do
  asset_id=$(basename "$(dirname "$(dirname "$intent")")")
  uv run --frozen neuralstock package \
    --intent "$intent" \
    --provenance "catalog/$asset_id/1.0.1/provenance.json" \
    --blender-output "$build_a/$asset_id" \
    --comparison-blender-output "$build_b/$asset_id" \
    --output "$packages_root/$asset_id" \
    --generated-at "$publish_time" \
    --image-digest "$image_digest" \
    --parameters-json '{}'
done

uv run --frozen neuralstock release publish "$packages_root"/* \
  --root "$release_root" \
  --generated-at "$publish_time"
uv run --frozen neuralstock release verify --root "$release_root"
uv run --frozen neuralstock r2 plan --root "$release_root" > "$work_root/r2-plan.json"

echo "Room Zero release is verified at $release_root"
echo "R2 upload plan: $work_root/r2-plan.json"
