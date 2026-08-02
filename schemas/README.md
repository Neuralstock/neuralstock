# NeuralStock v0.2 schemas

All schemas use JSON Schema Draft 2020-12, reject unknown fields, and have
canonical identifiers below `https://schemas.neuralstock.ai/v0.2/`. Those
identifiers establish document identity; validators should resolve them from
this checked-in directory rather than requiring network access.

Every standalone schema embeds the complete repository MIT copyright,
permission, and warranty notice in `x-neuralstock-document-license`. The exact
same bytes are published at the indefinitely locked
`https://schemas.neuralstock.ai/v0.2/LICENSE`; its SHA-256 is part of the
metadata. This makes a downloaded schema legally self-describing while keeping
a conventional adjacent license object for tools and mirrors.

## Ownership boundary

| Document | Owner | Purpose |
| --- | --- | --- |
| `asset.intent.json` | contributor | Semantic identity, source hash, expected anchors, and declared safe parameters |
| `provenance.json` | contributor/reviewer | CC0 dedication, origin, dependencies, evidence, and rights review |
| `inspection.json` | build pipeline | Measured source facts and profile/GLB checks |
| `build-receipt.json` | build pipeline | Reproducibility inputs, environment, results, and artifact hashes |
| `asset.json` | build pipeline | Immutable published asset manifest consumed by clients |
| `registry.json` | build pipeline | Portable, query-oriented snapshot of published manifests |
| `neuralstock.json` | project maintainers | Stable endpoint and client discovery at `/.well-known/neuralstock.json` |
| `web-v1.json` | project maintainers | Normative runtime profile, validated by `profile.schema.json` |

Generated documents contain `"generated": true`. They must never be accepted
as contributor assertions or edited to work around inspection failures.

`inspection.json` records measured Blender/source coordinates (meters, Z-up,
-Y-forward). Published `asset.json` and `registry.json` record runtime glTF
coordinates (meters, Y-up, +Z-forward). The package gate performs the explicit
`(X, Y, Z) -> (X, Z, -Y)` basis change for bounds, anchor positions, and anchor
quaternions.

JSON Schema validates document shape. The validator also performs semantic
checks that JSON Schema cannot express directly: numeric parameter
`minimum <= default <= maximum`, enum default membership, matching asset IDs
and versions across documents, counts matching their arrays, bounds arithmetic,
unit-length quaternions, required artifact roles, hash verification, unique
asset/version keys, and reproducible build-key calculation.
