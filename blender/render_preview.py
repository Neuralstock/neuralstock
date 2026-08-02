"""Render a deterministic PNG preview from the currently loaded .blend file."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ns_common import (
    BlenderArgumentParser,
    ensure_blender_45,
    finish_message,
    read_json_value,
    require_current_blend_path,
    script_arguments,
    write_json,
)
from preview import render_preview
from room_zero_generators import apply_declared_parameters


def parser() -> BlenderArgumentParser:
    result = BlenderArgumentParser(description="Render a NeuralStock asset preview.")
    result.add_argument("--output", required=True)
    result.add_argument("--params", help="Inline JSON, a JSON path, or @path.")
    result.add_argument("--resolution", type=int, default=512)
    result.add_argument("--margin", type=float, default=1.20)
    result.add_argument("--metadata-output")
    return result


def main() -> None:
    ensure_blender_45()
    arguments = parser().parse_args(script_arguments())
    require_current_blend_path()
    parameters = read_json_value(arguments.params, label="parameters")
    apply_declared_parameters(parameters)
    metadata = render_preview(
        arguments.output,
        resolution=arguments.resolution,
        margin=arguments.margin,
    )
    if arguments.metadata_output:
        write_json(arguments.metadata_output, metadata)
    finish_message("previewed", output=Path(arguments.output).resolve())


if __name__ == "__main__":
    main()
