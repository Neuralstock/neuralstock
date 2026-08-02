#!/bin/sh
set -eu

BLENDER_BIN="/opt/blender/blender"
SCRIPT_ROOT="/opt/neuralstock/blender"

task_home="${NEURALSTOCK_CONTAINER_HOME:-/tmp/neuralstock-home}"
export XDG_CONFIG_HOME="${XDG_CONFIG_HOME:-$task_home/.config}"
export XDG_CACHE_HOME="${XDG_CACHE_HOME:-$task_home/.cache}"
export XDG_DATA_HOME="${XDG_DATA_HOME:-$task_home/.local/share}"
export TMPDIR="${TMPDIR:-/tmp/neuralstock-tmp}"
export PYTHONNOUSERSITE=1

mkdir -p "$task_home" "$XDG_CONFIG_HOME" "$XDG_CACHE_HOME" "$XDG_DATA_HOME" "$TMPDIR"
unset HOME
umask 027

usage() {
  >&2 echo "usage: neuralstock-blender <generate|inspect-export|preview|build|batch> [--source FILE] [arguments]"
  >&2 echo "  generate       create a repository-owned Room Zero .blend"
  >&2 echo "  inspect-export inspect a loaded source and export GLB"
  >&2 echo "  preview        render a deterministic PNG preview"
  >&2 echo "  build          create source.blend, model.glb, preview.png, and JSON reports"
  >&2 echo "  batch          build the complete 15-asset Room Zero collection"
  exit 64
}

[ "$#" -gt 0 ] || usage
command_name="$1"
shift

case "$command_name" in
  generate)
    script="$SCRIPT_ROOT/generate_room_zero.py"
    source_file=""
    ;;
  inspect-export)
    script="$SCRIPT_ROOT/inspect_export.py"
    [ "${1:-}" = "--source" ] || usage
    [ "$#" -ge 2 ] || usage
    source_file="$2"
    shift 2
    ;;
  preview)
    script="$SCRIPT_ROOT/render_preview.py"
    [ "${1:-}" = "--source" ] || usage
    [ "$#" -ge 2 ] || usage
    source_file="$2"
    shift 2
    ;;
  build)
    script="$SCRIPT_ROOT/build_asset.py"
    source_file=""
    if [ "${1:-}" = "--source" ]; then
      [ "$#" -ge 2 ] || usage
      source_file="$2"
      shift 2
    fi
    ;;
  batch)
    script="$SCRIPT_ROOT/build_room_zero.py"
    source_file=""
    ;;
  -h|--help|help)
    usage
    ;;
  *)
    usage
    ;;
esac

if [ -n "$source_file" ]; then
  [ -f "$source_file" ] || {
    >&2 echo "source .blend does not exist: $source_file"
    exit 66
  }
  exec "$BLENDER_BIN" \
    --background \
    --factory-startup \
    --disable-autoexec \
    --python-exit-code 1 \
    "$source_file" \
    --python "$script" \
    -- "$@"
fi

exec "$BLENDER_BIN" \
  --background \
  --factory-startup \
  --disable-autoexec \
  --python-exit-code 1 \
  --python "$script" \
  -- "$@"
