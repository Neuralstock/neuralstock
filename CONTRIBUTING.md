# Contributing to NeuralStock

NeuralStock accepts software improvements under MIT and asset content under
CC0-1.0. By submitting a contribution, you confirm that you have the authority
to provide it on those terms. Asset pull requests must also include the
machine-readable CC0 attestation in `provenance.json`.

## Before creating an asset

Public asset intake is not open during the infrastructure bootstrap. Start with
the Asset proposal issue form; do not attach or commit a `.blend`. The first
invite-only beta accepts only direct-original, generic, static assets with
creator-authored packed inputs. Imports, third-party artistic dependencies,
recognizable people or brands, animations, and ambiguous AI-derived inputs need
a separately approved policy before submission.

Use a stable lower-snake-case asset ID such as `procedural_crate_01`. Versions
use semantic versioning and are immutable after publication.

## Asset contribution package

An asset pull request authors exactly two contract documents:

```text
catalog/<asset-id>/<version>/
  asset.intent.json
  provenance.json
```

When enabled, the Blender source is uploaded through the private quarantine
flow. Its immutable upload receipt, the intent, and the rights-holder attestation
must record the same SHA-256. Until that flow is announced, an asset proposal is
not authorization to send a source file. Room Zero's small accepted source set is the
explicit pilot exception and lives under `assets/room-zero`; larger `.blend`,
`.glb`, texture, and preview files must not be committed to Git history.

The build pipeline, never the contributor, creates:

```text
inspection.json
build-receipt.json
asset.json
registry.json
model.glb
previews
```

Generated documents are evidence. Editing one by hand is not a way to fix a
failed build; change the source or authored manifest and rebuild it.

## Rights and provenance

For v0.2, asset content must be original work that the contributor can dedicate
under CC0-1.0, or already-CC0 content with a complete, reviewable chain of
evidence. Equivalent public-domain statuses require a future versioned schema
and policy and are not accepted by the v0.2 contribution contract.
For every dependency, disclose its source, exact license status, and evidence.
This includes textures, HDRIs, fonts, reference scans, kitbash components,
Geometry Node groups, and generated or AI-assisted inputs.

Do not submit:

- marketplace models, ripped game content, or files whose chain of title is
  uncertain;
- attribution, non-commercial, share-alike, editorial-use, or no-derivatives
  content;
- recognizable brands or distinctive protected product designs without an
  explicit rights review;
- images or scans of people without the required releases; or
- a claim based only on an upstream filename or `CC0` tag.

Credits are welcome as historical metadata, but cannot be a condition of use.
See [`ASSET-LICENSE.md`](ASSET-LICENSE.md) for the scope of the dedication.

The dedication must identify a real person or legal entity with authority over
the contribution and be tied to an authenticated pull request/commit. A generic
project label, generated hash, or unsigned statement proves bytes but does not
by itself prove authority. Maintainers must retain that authenticated record as
part of the provenance review.

For an external contribution, affirmative assent must bind the authenticated
contributor identity, exact asset version, source SHA-256, included-dependency
hashes, and quarantine submission ID. Pull-request checkboxes support review but
do not replace that versioned record. The contributor cannot approve their own
rights review. Publication requires two distinct reviewers under
[`GOVERNANCE.md`](GOVERNANCE.md).

## `web-v1` authoring rules

The normative machine-readable profile is [`profiles/web-v1.json`](profiles/web-v1.json).
In summary:

- author in meters, Z-up, right-handed coordinates, with -Y as object forward;
- put renderable asset objects in exactly one top-level `ASSET` collection;
- place the asset origin at the horizontal center of its evaluated bounds and
  its lowest Z point;
- use lower-snake-suffixed empties such as `ANCHOR_top_surface` for stable
  interaction and attachment points;
- put non-rendered collision proxies in the `COLLISION` collection and name
  them with lower-snake suffixes such as `COLLISION_box`; the v0.2 profile
  accepts only exact asset-local axis-aligned boxes, whose eight corners and
  twelve triangles must match their positive-volume bounds;
- pack every resource into the `.blend`; linked libraries, absolute paths, and
  network resources are forbidden;
- expose agent-safe customization only through the declared Geometry Nodes
  group; and
- use only bounded floats, bounded integers, booleans, and finite string enums.

Numeric parameter defaults must lie within their inclusive minimum and maximum.
Enum defaults must be listed in their options. Strings, paths, object handles,
collections, geometry sockets, shaders, arbitrary expressions, and executable
hooks are not agent-safe parameters.

Do not rely on runtime code to repair scale, pivots, transforms, missing
resources, or collisions that belong in the asset.

## Embedded code and build safety

Contributor-supplied Blender files are untrusted. Embedded Python, auto-run
scripts, drivers that execute arbitrary expressions, network access, and
undeclared external programs are forbidden in `web-v1`. Only repository-owned,
versioned build scripts execute automatically. A future reviewed hook system
will require a separate profile and sandbox policy.

## Pull-request acceptance checklist

An asset is ready for review when:

- both authored JSON documents validate against JSON Schema 2020-12;
- the source hash matches the uploaded bytes;
- every dependency and material rights question is disclosed;
- the headless build runs in the pinned Blender image;
- inspection reports correct scale, bounds, resources, anchors, collisions,
  and declared procedural inputs;
- the GLB passes the Khronos validator and a Three.js smoke test;
- all required artifacts have SHA-256 hashes;
- the build receipt contains the complete reproducibility key; and
- visual review confirms that the preview and metadata describe the asset.

Procedural assets must also pass the declared boundary matrix: default values,
each numeric minimum and maximum, every enum option, and the bounded pairwise
cases selected by the profile. A passing default build alone does not establish
that an input is agent-safe.

Publication remains atomic: an asset version is not discoverable until all
required checks pass.

## Software contributions

Keep public behavior covered by tests, update schemas and fixtures together,
and avoid coupling manifests to Cloudflare-specific identifiers. Storage URLs
may change; content hashes and the public schema are the portable authority.
Run the repository's formatter, tests, and schema checks before requesting
review.
