"""Apply bounded parameters, inspect a .blend scene, and export a runtime GLB."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import bpy
from inspection import build_inspection, export_glb
from ns_common import (
    BlenderArgumentParser,
    ensure_blender_45,
    finish_message,
    generated_at,
    read_json_value,
    require_current_blend_path,
    script_arguments,
    sha256_file,
    write_json,
)
from room_zero_generators import apply_declared_parameters


def parser() -> BlenderArgumentParser:
    result = BlenderArgumentParser(
        description="Inspect the loaded NeuralStock source and optionally export GLB."
    )
    result.add_argument("--asset-id", help="Defaults to metadata embedded in the scene.")
    result.add_argument("--asset-version", help="Defaults to metadata embedded in the scene.")
    result.add_argument("--target-profile", default="web-v1")
    result.add_argument("--params", help="Inline JSON, a JSON path, or @path.")
    result.add_argument("--inspection-output", required=True)
    result.add_argument("--details-output")
    result.add_argument("--glb-output")
    result.add_argument("--include-collision", action="store_true")
    result.add_argument("--generated-at")
    result.add_argument(
        "--source-sha256",
        help="Expected source SHA-256; calculated from the loaded .blend when omitted.",
    )
    return result


def run(arguments: object) -> tuple[dict, dict]:
    source_path = require_current_blend_path()
    calculated_hash = sha256_file(source_path)
    expected_hash = getattr(arguments, "source_sha256", None)
    if expected_hash and expected_hash != calculated_hash:
        raise ValueError(
            f"source SHA-256 mismatch: expected {expected_hash}, got {calculated_hash}"
        )

    parameters = read_json_value(getattr(arguments, "params", None), label="parameters")
    apply_declared_parameters(parameters)

    glb_output = getattr(arguments, "glb_output", None)
    if glb_output:
        export_glb(
            glb_output,
            include_collision=bool(getattr(arguments, "include_collision", False)),
        )

    scene = bpy.context.scene
    asset_id = getattr(arguments, "asset_id", None) or scene.get("neuralstock_asset_id")
    asset_version = getattr(arguments, "asset_version", None) or scene.get(
        "neuralstock_asset_version"
    )
    if not asset_id or not asset_version:
        raise ValueError("asset id and version must be arguments or embedded scene metadata")

    inspection, details = build_inspection(
        asset_id=str(asset_id),
        asset_version=str(asset_version),
        source_sha256=calculated_hash,
        target_profile=str(getattr(arguments, "target_profile", "web-v1")),
        generated_timestamp=generated_at(getattr(arguments, "generated_at", None)),
    )
    write_json(arguments.inspection_output, inspection)
    details_output = getattr(arguments, "details_output", None)
    if details_output:
        write_json(details_output, details)
    return inspection, details


def main() -> None:
    ensure_blender_45()
    arguments = parser().parse_args(script_arguments())
    run(arguments)
    finish_message(
        "inspected",
        glb=Path(arguments.glb_output).resolve() if arguments.glb_output else "skipped",
        inspection=Path(arguments.inspection_output).resolve(),
    )


if __name__ == "__main__":
    main()
