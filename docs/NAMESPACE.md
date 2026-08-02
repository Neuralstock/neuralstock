# Namespace and schema-domain decision

**Status:** Implemented by the canonical package v0.1.0 release

**Decision date:** 2026-08-01

**Implementation verified:** 2026-08-02

## Decision

NeuralStock-controlled internet names use the owned `neuralstock.ai` domain:

- project site: `https://neuralstock.ai`;
- public immutable-asset origin: `https://assets.neuralstock.ai`;
- canonical schema origin: `https://schemas.neuralstock.ai`;
- Python distribution: `neuralstock`; and
- npm package: `@neuralstock/client`.

Every canonical v0.2 JSON Schema identifier and document `$schema` value uses:

```text
https://schemas.neuralstock.ai/v0.2/<document>.schema.json
```

The versioned runtime profile is served at:

```text
https://schemas.neuralstock.ai/profiles/v0.2/web-v1.json
```

The complete MIT notice accompanying these standalone contracts is served at:

```text
https://schemas.neuralstock.ai/v0.2/LICENSE
https://schemas.neuralstock.ai/profiles/v0.2/LICENSE
```

Every schema and profile also embeds those exact notice bytes and their SHA-256
in `x-neuralstock-document-license` so copying an individual JSON document does
not separate it from the required notice.

Pre-release drafts first used an unowned domain. A later infrastructure preview
published owned-domain v0.1 schema and profile bytes and locked both prefixes
indefinitely. Those public bytes remain valid historical preview contracts, but
they predate the requirement that every standalone contract carry the complete
MIT notice and an adjacent immutable `LICENSE`. Immutability forbids correcting
the existing JSON at the same key. Canonical rollout therefore advances the
schema/profile namespace to v0.2; it never overwrites, redirects, relabels, or
unlocks v0.1. No canonical v0.2 source, fixture, catalog record, generated
artifact, package, or client may reference the historical v0.1 contract.

## Migration implementation and gate

The schema-domain change altered authored-document hashes, tool inventories,
build receipts, manifests, content-addressed object keys, and the registry
revision even though the accepted Blender source and GLB geometry were
unchanged. The v0.1.0 migration completed all of these gates:

1. schemas, profiles, catalog documents, generators, fixtures, clients, and
   packaged contract data were updated together;
2. all schema, package, release, and real-runtime tests were rerun;
3. Room Zero was rebuilt from the accepted source hashes;
4. a new release candidate and registry revision were created;
5. Phase A published every immutable object, including v0.2 schemas, the
   profile, both adjacent MIT license companions, and the exact revision
   snapshot, without updating either alias or the site;
6. Phase A bytes were verified through the public origin and direct R2 reads,
   then indefinite locks for `v0.2/`, `profiles/v0.2/`, and the exact
   `snapshots/<revision>/` prefix were added and read back;
7. that exact readback was attached to the candidate draft before the exact
   six-asset GitHub Release was finalized under repository release
   immutability; and
8. Phase B verified the immutable release and immutable graph again before
   updating aliases and the site.

The previously deployed preview revision is retained as immutable historical
bytes and is no longer the mutable canonical registry. Its versioned Room Zero
`assets/*/1.0.0/manifest.json` keys are also retained unchanged. The
owned-schema rebuild published those same accepted Blender inputs as asset
version 1.0.1, so no immutable 1.0.0 manifest was overwritten. The canonical
revision is
`744accaa3f9efcd053d8e589b2bb7e966753b070004f7c78ef00c3431cbbe391`;
the historical 1.0.0 revision remains
`a3e851194d092bf1a06452a62ae98ba8687462ea0cbca668a9b9cc2385768523`.
The release and deploy workflows fail if an unowned draft or historical v0.1
schema reference remains in canonical contract-bearing source trees.

Provenance continuity is explicit and byte-bound:

- the historical 1.0.0 attestation remains
  `catalog/evidence/room-zero-v1.0.0-author-attestation.md`, SHA-256
  `e687b259dabc8080a610dd2de11be347e444d8f4a7a9a3df8548d92d9e77d58f`,
  and the indefinitely locked public object
  `/objects/sha256/e6/e687b259dabc8080a610dd2de11be347e444d8f4a7a9a3df8548d92d9e77d58f`;
- the 1.0.1 provenance records reference a distinct migration attestation,
  `catalog/evidence/room-zero-v1.0.1-migration-attestation.md`, SHA-256
  `95531e49b5da7616fa769cdbd7d97a84e51beb8798d5180fb3abfbb2a074c32e`,
  published at its own content-addressed object; and
- `catalog/room-zero-v1.0.1-source-migration.json` pins every unchanged
  accepted `.blend` input by SHA-256 and explains why its embedded historical
  version remains 1.0.0 while the new immutable publication is 1.0.1.

The migration attestation supplements the historical evidence; it never edits,
replaces, redirects, or deletes the 1.0.0 evidence object. Integration tests pin
both attestation hashes and all 15 accepted-source hashes.

## Repository and package names

The canonical source repository is
`https://github.com/Neuralstock/neuralstock`, owned by the `Neuralstock`
GitHub organization. The temporary personal-account repository was transferred
before initial source history and release provenance were published; GitHub's
redirect from that bootstrap location must remain intact.

The package-publication identity is fixed to repository
`Neuralstock/neuralstock`, workflow `publish-packages.yml`, and the protected
`npm` or `pypi` environment. The workflow publishes only a separately attested
candidate from the same protected tag and uses OIDC rather than stored registry
credentials. Initial namespace control and package availability were verified
by publishing `neuralstock==0.1.0` on PyPI and
`@neuralstock/client@0.1.0` on npm, followed by clean consumer installs.

## Immutability

After a schema version is canonical, its host, path, meaning, and adjacent
license bytes are immutable. A correction creates a new schema version.
Versioned schemas, profiles, and license companions are indefinitely locked R2
prefixes served with one-year immutable caching, and every release keeps an
offline bundled copy so validation and license inspection never depend on
network availability.

## Worker image metadata

The Blender OCI source and documentation labels use the canonical
`Neuralstock/neuralstock` repository. The canonical v0.2 migration reproduced
both image exports and the checked-in image lock after that metadata change.
The published worker manifest is
`sha256:e458059a9a783f8e54ac746361494a1b64d892f66a9f797f498bd11351531298`
with config
`sha256:dbf4c5a833b81b63bbec7eb04121056ccc5242aaa5561e3ce7680117d9181eed`;
the preview image digest was not reused.
