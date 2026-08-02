# Static registry and mirror contract

NeuralStock's v0.2 contract is a directory of ordinary HTTP objects. It can be hosted on
an R2 custom domain, another S3-compatible service, a static web server, or a
local directory without changing asset identities.

## Layout

```text
registry.json                                  mutable convenience alias
v0.2/*.schema.json                             immutable schema contracts
v0.2/LICENSE                                   immutable schema MIT notice
profiles/v0.2/web-v1.json                      immutable runtime profile
profiles/v0.2/LICENSE                          immutable profile MIT notice
objects/sha256/ab/<64-hex-sha256>              immutable artifact bytes
assets/<asset-id>/<version>/manifest.json      immutable version manifest
snapshots/<revision>/registry.json             immutable registry snapshot
snapshots/latest.json                          mutable snapshot alias
```

Artifact and manifest URIs in public documents are root-relative. A mirror
therefore preserves the paths above at the root of its asset origin while
changing only the origin hostname.

## Publication transaction

Writers publish in two phases:

1. Verify every standalone schema/profile, its embedded complete MIT notice,
   both adjacent `LICENSE` companions, and every package artifact against the
   declared bytes and hashes.
2. Create the versioned schema/profile contracts and license companions with
   create-only semantics.
3. Create content-addressed objects with create-only semantics.
4. Create immutable `asset-id@version` manifests.
5. Create the content-addressed registry object and immutable revision
   snapshot.
6. Stop before aliases; verify every Phase A byte publicly and directly in R2,
   then indefinitely lock both v0.2 contract prefixes and the exact revision
   snapshot prefix.
7. In Phase B, re-verify all immutable bytes and replace `registry.json`, then
   the canonical `snapshots/latest.json` alias.

If a create-only destination already exists, the writer accepts it only when
the recorded SHA-256 and byte count match. A failure before step 5 may leave
unreachable immutable objects, but cannot expose an incomplete registry.

## HTTP metadata

Use the artifact descriptor's media type. Serve schemas as
`application/schema+json`, profiles as `application/json`, and license
companions as `text/plain`. Immutable contract, object, version-manifest, and
revision-snapshot responses should use:

```text
Cache-Control: public, max-age=31536000, immutable
```

The two aliases use revalidation or a short cache lifetime. Hosts serving a
browser client must allow public `GET` and `HEAD` requests and expose normal
range and ETag behavior for large files.

## Mirroring

A complete mirror needs no search API:

1. Download `snapshots/latest.json` or a pinned revision snapshot.
2. Validate it against `registry.schema.json`.
3. For every entry, fetch the version manifest and verify its descriptor.
4. Validate each manifest and fetch every artifact URI.
5. Verify SHA-256 and byte length before making the mirror discoverable.

A contract-complete mirror also preserves both versioned schema/profile paths
and their adjacent license companions. It verifies that every embedded notice
matches the companion bytes before exposing the mirror.

The registry snapshot is the traversal root. D1, Vectorize, Worker APIs, and
other hosted indexes are rebuildable conveniences and are not needed to retain
or consume the commons.

## Immutability and withdrawals

`latest` is an alias, never an artifact identity. Consumers that need stable
builds pin both the asset version and registry revision. If an asset must be
withdrawn, a future snapshot adds a withdrawal record; old hashes remain facts
about the historical release and are not repointed to different bytes.
