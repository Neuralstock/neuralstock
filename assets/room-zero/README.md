# Room Zero accepted Blender sources

This directory contains the 15 immutable `source.blend` inputs for the v0.1
Room Zero collection. Each file is versioned in Git because the complete pilot
set is small; its SHA-256 is pinned by the matching
`catalog/<asset-id>/1.0.1/asset.intent.json` and `provenance.json` records.

Version 1.0.1 preserves the accepted 1.0.0 Blender inputs while publishing the
owned `schemas.neuralstock.ai` document namespace at new immutable manifest
keys. The already-public 1.0.0 keys remain historical and are never replaced.
The byte-for-byte reuse, embedded source version, and per-asset hashes are
pinned in `catalog/room-zero-v1.0.1-source-migration.json`.

These are release inputs, not disposable build output. Generated inspections,
GLBs, previews, receipts, and registry snapshots remain outside Git and are
published through the content-addressed static release.

At larger scale, accepted sources move to immutable object storage while the
same public hashes and release contract remain authoritative.
