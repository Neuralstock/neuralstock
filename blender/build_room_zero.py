"""Build the complete, ordered Room Zero pilot collection in one Blender process."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import bpy
from build_asset import build_package
from ns_common import (
    BlenderArgumentParser,
    ensure_blender_45,
    finish_message,
    generated_at,
    script_arguments,
    stable_json_value,
    write_json,
)
from room_zero_generators import available_generators

ROOM_ZERO_ASSETS = (
    "room_floor_panel_01",
    "room_wall_panel_01",
    "room_door_01",
    "room_window_01",
    "procedural_table_01",
    "chair_01",
    "stool_01",
    "shelf_01",
    "cabinet_01",
    "procedural_crate_01",
    "monitor_01",
    "desk_lamp_01",
    "potted_plant_01",
    "mug_01",
    "book_stack_01",
)


def parser() -> BlenderArgumentParser:
    result = BlenderArgumentParser(
        description="Build all 15 Room Zero source, runtime, preview, and inspection packages."
    )
    result.add_argument("--output-dir", required=True)
    result.add_argument(
        "--source-root",
        help=(
            "Rebuild from accepted <root>/<asset-id>/source.blend inputs instead "
            "of generating new source files."
        ),
    )
    result.add_argument("--asset-version", default="1.0.1")
    result.add_argument("--target-profile", default="web-v1")
    result.add_argument("--generated-at")
    result.add_argument("--include-collision", action="store_true")
    result.add_argument("--preview-resolution", type=int, default=256)
    result.add_argument("--preview-margin", type=float, default=1.20)
    result.add_argument("--skip-preview", action="store_true")
    return result


def _build_arguments(
    arguments: argparse.Namespace,
    *,
    asset_id: str,
    output_dir: Path,
    timestamp: str,
    generate: bool,
) -> argparse.Namespace:
    return argparse.Namespace(
        generate=asset_id if generate else None,
        asset_id=asset_id,
        asset_version=arguments.asset_version,
        target_profile=arguments.target_profile,
        params=None,
        output_dir=str(output_dir),
        generated_at=timestamp,
        include_collision=arguments.include_collision,
        preview_resolution=arguments.preview_resolution,
        preview_margin=arguments.preview_margin,
        skip_preview=arguments.skip_preview,
    )


def main() -> None:
    ensure_blender_45()
    arguments = parser().parse_args(script_arguments())
    registered = tuple(available_generators())
    expected = tuple(sorted(ROOM_ZERO_ASSETS))
    if registered != expected:
        missing = sorted(set(expected) - set(registered))
        unexpected = sorted(set(registered) - set(expected))
        raise ValueError(
            "Room Zero registry mismatch: "
            f"missing={missing or 'none'}, unexpected={unexpected or 'none'}"
        )

    output_root = Path(arguments.output_dir).resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    source_root = Path(arguments.source_root).resolve() if arguments.source_root else None
    timestamp = generated_at(arguments.generated_at)
    assets: list[dict[str, object]] = []

    for asset_id in ROOM_ZERO_ASSETS:
        if source_root is not None:
            source = source_root / asset_id / "source.blend"
            if not source.is_file():
                raise ValueError(f"accepted Room Zero source is missing: {source}")
            bpy.ops.wm.open_mainfile(filepath=str(source), load_ui=False, use_scripts=False)
        package_dir = output_root / asset_id
        summary = build_package(
            _build_arguments(
                arguments,
                asset_id=asset_id,
                output_dir=package_dir,
                timestamp=timestamp,
                generate=source_root is None,
            )
        )
        assets.append(
            {
                "id": asset_id,
                "version": arguments.asset_version,
                "profile_status": summary["profile_status"],
                "package": asset_id,
                "outputs": summary["outputs"],
            }
        )
        finish_message(
            "built Room Zero asset",
            asset=asset_id,
            completed=len(assets),
            total=len(ROOM_ZERO_ASSETS),
        )

    receipt = stable_json_value(
        {
            "schema_version": "0.2",
            "collection": "room-zero",
            "asset_count": len(assets),
            "generated_at": timestamp,
            "preview_resolution": (
                None if arguments.skip_preview else arguments.preview_resolution
            ),
            "assets": assets,
        }
    )
    write_json(output_root / "room-zero-build.json", receipt)
    finish_message("built Room Zero collection", output=output_root, assets=len(assets))


if __name__ == "__main__":
    main()
