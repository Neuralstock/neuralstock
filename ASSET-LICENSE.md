# NeuralStock asset licensing

NeuralStock intentionally separates the license for its software from the
legal status of its asset commons.

## Asset content: CC0-1.0

The v0.2 registry accepts asset content only when its provenance records a
dedication under
[Creative Commons CC0 1.0 Universal](https://creativecommons.org/publicdomain/zero/1.0/legalcode).
Its SPDX identifier is `CC0-1.0`.

A future version may define an equivalent reviewed public-domain status, but
doing so requires an explicit versioned schema and policy change. A v0.2
contribution cannot rely on that future extension.

For an accepted asset version, "asset content" includes:

- Blender source files and procedural modeling content;
- exported meshes, materials, textures, previews, and collision geometry;
- authored asset intent and provenance facts;
- generated inspection data, build receipts, manifests, and registry records
  describing that asset; and
- bundled dependencies whose provenance record confirms that they may be
  included without attribution or commercial-use restrictions.

CC0 is the project requirement because it permits copying, modification,
redistribution, commercial use, automated scene generation, and use in model
training without downstream attribution tracking. NeuralStock may preserve
voluntary creator credits in provenance records, but consumers are not
required to reproduce those credits.

CC0 is not a trademark clearance, patent license, privacy release, or warranty.
Every contribution must separately disclose relevant trademarks, distinctive
product designs, people, fonts, HDRIs, textures, kitbash parts, and other
dependencies. Publication means the recorded review passed; it is not legal
advice to downstream users.

## Software and specifications: MIT

Repository-owned software, automation, reusable Python and TypeScript code,
JSON Schemas, runtime profiles, tests, and general documentation are licensed
under the MIT License in [`LICENSE`](LICENSE). Vendored and generated
third-party components retain their own terms and notices as documented in
[`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).

Every standalone v0.2 schema and profile embeds the complete MIT notice and
points to an identical, immutable adjacent `LICENSE` object on the canonical
schema origin. Release tooling compares all copies byte-for-byte.

MIT is not used for artistic asset content because its notice-preservation
condition conflicts with NeuralStock's zero-attribution asset promise.

## Per-version authority

`provenance.json` is the authority for the origin and rights evidence of one
asset version. `asset.intent.json` and the generated `asset.json` repeat the
normalized license identifier so clients can filter deterministically. A
filename, repository topic, upstream search filter, or statement that an item
is merely "free" is not sufficient evidence.

Published asset versions are immutable. If a material rights or security issue
is discovered, NeuralStock records a withdrawal instead of silently replacing
the bytes or their provenance history.

Room Zero demonstrates this rule: the 1.0.1 owned-schema migration has its own
versioned provenance and attestation while the exact 1.0.0 attestation,
manifests, and content-addressed evidence object remain historical. New evidence
may supplement an earlier dedication; it never rewrites that dedication's
bytes.

The Room Zero records bind the project name and `neuralstock.ai` domain to the
dedication, but that public URL is corroborative. The authenticated commit/tag
history and exact evidence hash provide the durable identity and byte binding.

A withdrawal changes NeuralStock discovery and hosting behavior; it does not
purport to revoke an otherwise valid and irrevocable CC0 dedication. When legal,
privacy, or security obligations require delivery to be blocked, NeuralStock
may stop serving the affected binary while retaining a non-sensitive tombstone,
hash, notice, and historical registry fact. Mutable aliases must not resolve to
a withdrawn version.
