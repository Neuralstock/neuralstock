# Reproducibility gate

## Container input lock

The Blender environment is locked independently of the per-asset comparison
gate. The container pins its Ubuntu base, Dockerfile frontend, and BuildKit
builder by digest; fixes the Docker archive media type, gzip level, platform,
and timestamp-rewrite exporter controls; uses the official Ubuntu archive
snapshot `20260731T000000Z`; installs every declared APT package at an exact
version from checked-in lock files; and checks Blender's official archive
against a pinned SHA-256. Two clean builder instances must emit the same
manifest and config digests before `container/image.lock.json` is advanced. See
[the container runbook](../container/README.md#locked-build-inputs) for the
lock files, bootstrap trust boundary, update procedure, and verification
commands.

`neuralstock package` can verify a second, independently produced Blender
result before it emits the build receipt:

```sh
uv run neuralstock package \
  --intent catalog/procedural_crate_01/1.0.1/asset.intent.json \
  --provenance catalog/procedural_crate_01/1.0.1/provenance.json \
  --blender-output work/room-zero-blender/procedural_crate_01 \
  --comparison-blender-output work/room-zero-reproduced/procedural_crate_01 \
  --output dist/packages/procedural_crate_01 \
  --generated-at 2026-08-01T00:10:00Z \
  --image-digest sha256:<pinned-image-digest> \
  --parameters-json '{}'
```

The caller is responsible for producing the comparison directory in a clean,
independent invocation. The gate requires the two input and output directory
trees to be separate; a directory path alone cannot prove process
independence. See [the container runbook](../container/README.md) for the
hardened pinned-image commands.

## Evidence and classification

The gate validates both `blender-build.json` summaries and every required file.
It then applies these assertions:

- `model.glb` and `blender-details.json` must have exactly equal byte counts and
  SHA-256 hashes.
- Both inspection documents must pass the public schema. When the accepted
  `source.blend` input is byte-identical, `inspection.json` must also be
  byte-identical.
- When repository generators serialize equivalent `.blend` files differently,
  inspection documents may differ only at `source_sha256`. Exact
  `blender-details.json` and `model.glb` files are the semantic and runtime
  evidence for the generated source.
- Preview PNG encodings may differ, but both files must be valid,
  non-interlaced 8-bit RGBA PNGs and their fully decoded pixels must be exactly
  equal. A perceptual threshold is not used.
- Build summaries must be semantically equal after removing only the output
  descriptors whose byte encodings were accepted as nondeterministic.

A source-based rebuild from the exact accepted `.blend` is recorded as
`reproduced`. If only the lossless preview encoding differs, that exception is
listed explicitly in `allowed_nondeterminism`.

A clean rerun of a repository generator may produce a different `.blend`
serialization because Blender embeds session-dependent data. If all stricter
semantic and runtime checks above pass, the receipt is conservatively recorded
as `known-nondeterminism`; the source, propagated inspection hash, lossless PNG
encoding, and propagated build-summary descriptors are each named in
`allowed_nondeterminism`.

Any other difference fails packaging. Omitting
`--comparison-blender-output` preserves the baseline
`not-yet-reproduced` status.

`comparison_build_id` is deterministic and derived from normalized inspection
and summary documents, the exact GLB and Blender semantic-detail hashes, the
decoded preview pixel hash, and the resulting classification. Filesystem paths
and volatile encodings are excluded.

The receipt graph publishes the raw primary `blender-build.json` and
`blender-details.json`, all six comparison files, the exact runtime profile,
the package/schema/tool hash inventory, the authored provenance record, and
every hashed legal-evidence file. The public provenance copy rewrites evidence
links to content-addressed `/objects/sha256/...` URIs, so verification never
depends on the contributor's original directory layout.

The Python source distribution carries the canonical schema and profile trees,
and CI builds the release wheel from that extracted archive. The resulting
wheel carries those contract files plus the pinned Khronos validator as a
self-contained Node bundle with its Apache-2.0 license and required notices.
Publication and later release verification rerun that bundle against the
actual content-addressed GLB; a stored validator report is evidence, not a
substitute for revalidation.

Runtime vertex, triangle, and material counts in `asset.json` come from this
pinned validator report and are checked against the `web-v1` runtime budgets.
The source-oriented counts in `inspection.json` remain separate Blender
evidence. The Room Zero release gate additionally parses every GLB with Three.js
and cross-checks runtime geometry, bounds, and anchor transforms.

The pinned v0.1 Blender stage removes volatile PNG text/time chunks without
re-encoding pixel data. As a result, the final Room Zero accepted-source runs
reproduced the preview bytes exactly as well as their decoded pixels. The
narrow decoded-pixel allowance remains in the gate for otherwise equivalent
Blender PNG encoders and older accepted outputs.
