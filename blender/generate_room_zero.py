"""Generate a Room Zero Blender source without loading contributor Python."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ns_common import (
    BlenderArgumentParser,
    ensure_blender_45,
    finish_message,
    read_json_value,
    save_blend,
    script_arguments,
)
from room_zero_generators import available_generators, generate_asset


def parser() -> BlenderArgumentParser:
    result = BlenderArgumentParser(
        description="Generate a repository-owned NeuralStock Room Zero .blend source."
    )
    result.add_argument("--asset", required=True, choices=available_generators())
    result.add_argument("--asset-version", default="1.0.1")
    result.add_argument("--params", help="Inline JSON, a JSON path, or @path.")
    result.add_argument("--output", required=True, help="Destination .blend path.")
    return result


def main() -> None:
    ensure_blender_45()
    arguments = parser().parse_args(script_arguments())
    output = Path(arguments.output).resolve()
    if output.suffix.lower() != ".blend":
        raise ValueError("--output must end in .blend")
    parameters = read_json_value(arguments.params, label="parameters")
    generate_asset(
        arguments.asset,
        version=arguments.asset_version,
        parameters=parameters,
    )
    save_blend(output)
    finish_message("generated", asset=arguments.asset, output=output)


if __name__ == "__main__":
    main()
