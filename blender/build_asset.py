"""One-shot golden-path build for a NeuralStock Blender asset package."""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import bpy
from inspect_export import run as inspect_and_export
from ns_common import (
    BlenderArgumentParser,
    ensure_blender_45,
    finish_message,
    generated_at,
    read_json_value,
    require_current_blend_path,
    save_blend,
    script_arguments,
    sha256_file,
    stable_json_value,
    write_json,
)
from preview import render_preview
from room_zero_generators import available_generators, generate_asset


def parser() -> BlenderArgumentParser:
    result = BlenderArgumentParser(
        description="Generate or process one NeuralStock source into a local asset package."
    )
    result.add_argument(
        "--generate",
        choices=available_generators(),
        help="Generate this repository-owned asset instead of processing the loaded .blend.",
    )
    result.add_argument("--asset-id", help="Defaults to --generate or embedded metadata.")
    result.add_argument("--asset-version", default="1.0.0")
    result.add_argument("--target-profile", default="web-v1")
    result.add_argument("--params", help="Inline JSON, a JSON path, or @path.")
    result.add_argument("--output-dir", required=True)
    result.add_argument("--generated-at")
    result.add_argument("--include-collision", action="store_true")
    result.add_argument("--preview-resolution", type=int, default=512)
    result.add_argument("--preview-margin", type=float, default=1.20)
    result.add_argument("--skip-preview", action="store_true")
    return result


def _inspection_arguments(
    arguments: argparse.Namespace,
    *,
    asset_id: str,
    timestamp: str,
    output_dir: Path,
) -> argparse.Namespace:
    return argparse.Namespace(
        asset_id=asset_id,
        asset_version=arguments.asset_version,
        target_profile=arguments.target_profile,
        params=arguments.params,
        inspection_output=str(output_dir / "inspection.json"),
        details_output=str(output_dir / "blender-details.json"),
        glb_output=str(output_dir / "model.glb"),
        include_collision=arguments.include_collision,
        generated_at=timestamp,
        source_sha256=None,
    )


def build_package(arguments: argparse.Namespace) -> dict[str, object]:
    """Build one package from parsed arguments and return its receipt."""

    output_dir = Path(arguments.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    parameters = read_json_value(arguments.params, label="parameters")

    if arguments.generate:
        asset_id = arguments.asset_id or arguments.generate
        if asset_id != arguments.generate:
            raise ValueError("--asset-id must match --generate for repository-owned assets")
        generate_asset(
            arguments.generate,
            version=arguments.asset_version,
            parameters=parameters,
        )
        source_output = output_dir / "source.blend"
        save_blend(source_output)
    else:
        source_path = require_current_blend_path().resolve()
        asset_id = arguments.asset_id or bpy.context.scene.get("neuralstock_asset_id")
        if not asset_id:
            raise ValueError("--asset-id or embedded neuralstock_asset_id metadata is required")
        source_output = output_dir / "source.blend"
        if source_path != source_output:
            shutil.copyfile(source_path, source_output)

    timestamp = generated_at(arguments.generated_at)
    inspection, _ = inspect_and_export(
        _inspection_arguments(
            arguments,
            asset_id=str(asset_id),
            timestamp=timestamp,
            output_dir=output_dir,
        )
    )

    preview_metadata = None
    preview_path = output_dir / "preview.png"
    if not arguments.skip_preview:
        preview_metadata = render_preview(
            preview_path,
            resolution=arguments.preview_resolution,
            margin=arguments.preview_margin,
        )

    outputs = {
        "source.blend": {
            "sha256": sha256_file(source_output),
            "bytes": source_output.stat().st_size,
        },
        "model.glb": {
            "sha256": sha256_file(output_dir / "model.glb"),
            "bytes": (output_dir / "model.glb").stat().st_size,
        },
        "inspection.json": {
            "sha256": sha256_file(output_dir / "inspection.json"),
            "bytes": (output_dir / "inspection.json").stat().st_size,
        },
        "blender-details.json": {
            "sha256": sha256_file(output_dir / "blender-details.json"),
            "bytes": (output_dir / "blender-details.json").stat().st_size,
        },
    }
    if preview_metadata is not None:
        outputs["preview.png"] = {
            "sha256": sha256_file(preview_path),
            "bytes": preview_path.stat().st_size,
        }

    summary = {
        "schema_version": "0.2",
        "tool": "neuralstock-blender",
        "blender_version": bpy.app.version_string,
        "asset": {"id": str(asset_id), "version": arguments.asset_version},
        "generated_at": timestamp,
        "parameters": parameters,
        "profile_status": inspection["profile_validation"]["status"],
        "preview": preview_metadata,
        "outputs": outputs,
        "limitations": [
            "Khronos glTF validation is intentionally performed by the outer build pipeline.",
            "GLB compression and texture transcoding are intentionally outside Blender v0.2.",
        ],
    }
    write_json(output_dir / "blender-build.json", stable_json_value(summary))
    return stable_json_value(summary)


def main() -> None:
    ensure_blender_45()
    arguments = parser().parse_args(script_arguments())
    summary = build_package(arguments)
    finish_message(
        "built",
        asset=summary["asset"]["id"],
        output=Path(arguments.output_dir).resolve(),
    )


if __name__ == "__main__":
    main()
