# Room Zero release runbook

> **Published package v0.1.0:** the canonical Room Zero graph was rebuilt as
> asset version 1.0.1 under the fresh
> `https://schemas.neuralstock.ai/v0.2/` namespace and published as registry
> revision
> `744accaa3f9efcd053d8e589b2bb7e966753b070004f7c78ef00c3431cbbe391`.
> The immutable 1.0.0 preview revision and every locked v0.1 contract remain
> separate historical evidence. `docs/NAMESPACE.md` is authoritative.

Room Zero v0.1 is released from accepted, immutable `.blend` sources—not from
a fresh procedural-generator serialization. Blender can serialize an
equivalent generated scene with session-dependent bytes; once a source is
accepted by hash, rebuilding from those exact bytes is deterministic.

The release helper performs the complete local transaction:

```sh
tools/release-room-zero.sh
```

The default accepted source root is the versioned `assets/room-zero`
collection. An alternate first argument may point to any root containing
`<asset-id>/source.blend` for every catalog entry. Optional second and third
arguments select the work and release targets. Output targets must be absent or
empty; the helper will not overwrite a populated directory.
The accepted `.blend` inputs intentionally retain embedded version 1.0.0 bytes;
`catalog/room-zero-v1.0.1-source-migration.json` pins those exact inputs while
the release helper emits new 1.0.1 assets and manifests.
It then:

1. installs locked Python and Node dependencies;
2. builds the Blender 4.5.12 image with the digest-pinned BuildKit builder,
   reproducible Docker-archive exporter, and checked-in image lock;
3. rebuilds all 15 assets twice with networking and privileges disabled, a
   30-minute wall-clock deadline per batch, and a 512 MiB output filesystem;
4. requires all files in both builds to be byte-identical;
5. packages every asset through JSON Schema, profile, provenance, budget, and
   Khronos glTF validation gates;
6. emits `reproduced` receipts using the second build as evidence;
7. publishes and traverses a complete content-addressed static registry; and
8. writes a deterministic R2 upload plan without changing remote state.

`NEURALSTOCK_BUILD_TIME`, `NEURALSTOCK_PUBLISH_TIME`,
`NEURALSTOCK_BLENDER_IMAGE`, `NEURALSTOCK_BUILD_WALL_SECONDS`, and
`NEURALSTOCK_BUILD_OUTPUT_BYTES` can override the fixed release timestamps,
local image tag, and job limits. Publication timestamps must not precede build
timestamps; both limit overrides must be positive integers.

## Verify and exercise a release

```sh
uv run neuralstock release verify --root dist/release
uv run neuralstock r2 plan --root dist/release
pnpm --filter @neuralstock/room-zero test:e2e:install
NEURALSTOCK_RELEASE_DIR="$PWD/dist/release" pnpm test:e2e
```

The browser test serves the viewer and release from one origin, loads a real
GLB, checks exact metadata, enables bounds, anchors, and collision boxes, resizes the renderer,
forces WebGL context loss and recovery, rejects browser/network errors, and
captures desktop and narrow screenshots under ignored `output/playwright/`.

## Create an attested release candidate

The manual `Release candidate` GitHub workflow must be dispatched from the
existing protected tag `v<version>`. Before any build, it verifies that the tag
targets the workflow commit, that the commit is an ancestor of current protected
`main`, and that the active release-tag ruleset protects `v*`. It then runs the
complete release gate and invokes:

```sh
NEURALSTOCK_RELEASE_TAG='v0.1.0' \
NEURALSTOCK_SOURCE_COMMIT='<40-character tagged commit>' \
  tools/package-release-candidate.sh \
    0.1.0 \
    dist/release \
    work/release-candidate/r2-plan.json \
    work/release-candidate/neuralstock-blender.metadata.json \
    dist/release-candidate

tools/verify-release-candidate.sh dist/release-candidate 0.1.0 '<registry-revision>'
```

The candidate contains a deterministic release archive, ordered R2 plan,
worker-image metadata, protected tag and package identity, and `SHA256SUMS`.
GitHub attests all five subjects, stores the candidate temporarily, verifies the
attestations, and creates an unpublished draft release containing exactly those
five files. This does not publish a GitHub Release, R2, Pages, npm, PyPI, or an
OCI registry.

The protected `Production deploy` workflow accepts a specific candidate run ID,
version, commit, and revision. It reproduces the candidate's R2 plan, writes
immutable objects—including versioned schemas, the profile, and both complete
MIT license companions—before aliases,
reconciles the zone-level `www` 301, deploys Pages when requested, and runs the
same complete public-contract verifier as scheduled health. That verifier
recomputes the registry revision, compares both aliases with the immutable
revision snapshot, hashes every declared preview plus a live manifest, GLB, and
Blender source, and checks the deployed CSP, CORS, ranges, cache policy,
discovery, sitemap, and a stable asset route. The first v0.2 publication is
explicitly two-phase. Phase A uses
`neuralstock r2 sync --immutable-only` to create or exact-byte verify the entire
immutable graph without updating aliases or the site. An operator then verifies
public and direct-R2 bytes and indefinitely locks `v0.2/`, `profiles/v0.2/`, and
the exact revision-snapshot prefix. Phase B requires that recorded lock evidence,
re-verifies the immutable graph, and only then updates aliases and the site.
Before Phase A, `tools/verify-contract-origin.sh --allow-absent dist/release`
accepts only one of two safe states: all 12 v0.2 contract keys are absent, or
all 12 already match exactly. It rejects a partial namespace and any byte,
content-type, or cache-policy mismatch. After Phase A, the same verifier without
`--allow-absent` requires every public key.

The workflow deliberately does not receive R2 bucket-configuration authority.
Cloudflare's bucket-lock endpoint cannot currently be delegated through the
bucket-scoped S3 publication credential, and the available configuration-write
token would be account-wide. Between Phase A and Phase B, an operator uses local
Wrangler OAuth and `tools/manage-r2-release-lock.sh` with the exact extracted
release root. The helper preserves all historical locks, verifies every staged
immutable object directly from R2, recomputes the snapshot revision, and creates
or reads back only `schema-v0.2`, `profile-v0.2`, and the exact snapshot rule.

The independent check-only JSON is uploaded once, without replacement, under
the deterministic `neuralstock-r2-release-lock-<revision>.json` name on the
signed-tag draft release. Dispatch `Finalize release` from exact current
protected `main` (or from that same signed tag before `main` advances), supplying
the exact signed-tag commit, revision, and evidence SHA-256. The protected
finalizer requires
repository release immutability, downloads every draft asset by its API ID,
accepts exactly the five attested candidate files plus that one evidence file,
re-verifies checksums, source commit, version, revision, build attestations, and
the complete R2 evidence, then publishes the draft exactly once. A main-based
run must equal the freshly read protected-main head; all release subjects remain
bound to the supplied signed-tag commit. It requires a
fresh API readback with `immutable: true` and verifies GitHub's automatically
generated release attestation and all six assets. If publication succeeds but a
later check fails, the finalizer can be rerun: it accepts only the exact already-
immutable release, skips the publication mutation, and repeats all checks. It
never accepts a published mutable release. Phase B retrieves the now-
immutable evidence asset, verifies its supplied SHA-256 and release attestation,
parses all eight historical/target rules, and binds its revision and release-
plan hash to the candidate before any write. A Phase A green status or a hex-
looking caller input is not retention evidence. A release remains incomplete
until immutable GitHub finalization, Phase B, both JSON records, the release
asset, an independent authenticated R2 lock readback, and dashboard confirmation
are recorded.

## Publish package distributions

`Package candidate` builds, tests, checksums, and attests the Python
`neuralstock` distributions and npm `@neuralstock/client` archive without
registry credentials. Both candidate and publication workflows require the
exact `v<version>` tag target to be on current protected `main`. On that tag,
dispatch `Publish packages` with the candidate's run ID and exact version. The
workflow rejects any candidate from another workflow, commit, tag, repository
identity, or version before the protected `npm` and `pypi` jobs can run.

The two publisher jobs use GitHub OIDC only. Configure their exact identities
as documented in `docs/GITHUB-GOVERNANCE.md`; never create a GitHub npm or PyPI
token. PyPI can use a pending publisher for its first upload. npm required the
scoped package to exist before trusted publishing could be enabled, so v0.1.0
used the single interactive 2FA bootstrap from the exact already-attested
archive:

```sh
npm publish ./dist/package-candidate/npm/neuralstock-client-0.1.0.tgz \
  --access public \
  --provenance=false
```

That public archive has SHA-256
`c18fcf3f0b7f22d15a888d9c5cb0a42bfb350fa0f8b0592d33fb1984b5409ace`.
npm trusted publishing is now configured for `Neuralstock/neuralstock`,
workflow `publish-packages.yml`, environment `npm`; package publication and the
npm organization require 2FA. All later versions go through the protected OIDC
workflow. PyPI project `neuralstock` was created and published through its
pending trusted publisher with no API token.

Record the complete release evidence in
[`docs/releases/v0.1.0.md`](releases/v0.1.0.md). Package version `0.1.0`, schema
version `v0.2`, Room Zero asset version `1.0.1`, and the content-derived registry
revision are independent identifiers and must occupy separate fields.

## Publish or update Cloudflare R2

Create an R2 S3 API token that is scoped to the destination bucket. Install
the optional adapter, inspect the plan, and then sync:

```sh
uv sync --frozen --extra r2
export NEURALSTOCK_R2_ACCESS_KEY_ID='<scoped access key>'
export NEURALSTOCK_R2_SECRET_ACCESS_KEY='<scoped secret key>'

uv run neuralstock r2 plan --root dist/release
uv run neuralstock r2 sync \
  --root dist/release \
  --bucket neuralstock-public \
  --endpoint-url 'https://<account-id>.r2.cloudflarestorage.com' \
  --immutable-only
```

That is Phase A and must report no alias updates. After the exact contract and
revision locks are independently verified, Phase B repeats the command without
`--immutable-only`; the ordinary sync rechecks all immutable keys before writing
the two aliases.

The adapter creates immutable objects with `If-None-Match: *`, accepts an
existing object only when its recorded SHA-256 and byte count match, applies
year-long immutable caching to content-addressed paths, and updates
`registry.json` followed by `snapshots/latest.json` last. Credentials are read
only from the two environment variables above. A custom-domain origin should
serve the resulting keys directly; normal binary downloads do not need a
Worker proxy.

The v0.2 contract intentionally forbids an R2 key prefix: all published URIs
are root-relative. Use a dedicated bucket/custom domain, or add a separately
specified origin rewrite in a future profile. The client validates HTTPS
Cloudflare R2 endpoints and requires both scoped NeuralStock credentials; it
never falls back to ambient AWS credentials.

## Current Cloudflare publication

Room Zero revision
`744accaa3f9efcd053d8e589b2bb7e966753b070004f7c78ef00c3431cbbe391`
is canonical in the `neuralstock-public` bucket and contains all 15 Room Zero
assets at version 1.0.1. Its active public origin is
`https://assets.neuralstock.ai`; the `r2.dev` development URL is disabled.
Public `GET` and `HEAD` CORS, exposed range headers, and R2 byte-range responses
allow browsers and download clients to fetch large artifacts directly.

All 227 immutable v0.1.0 plan items were created or verified before either
alias changed. The `v0.2/`, `profiles/v0.2/`, and exact
`snapshots/744accaa3f9efcd053d8e589b2bb7e966753b070004f7c78ef00c3431cbbe391/`
prefixes are indefinitely locked. The five historical lock rules, the complete
asset 1.0.0 graph, and historical registry revision
`a3e851194d092bf1a06452a62ae98ba8687462ea0cbca668a9b9cc2385768523`
remain unchanged.

The object writers assign one-year immutable caching to content-addressed
objects, schemas, profiles, their license companions, asset-version manifests,
and revision snapshots.
They assign a 60-second revalidating policy to `registry.json` and
`snapshots/latest.json`. The zone Browser Cache TTL is **Respect Existing
Headers**. Live v0.1.0 verification confirmed both aliases have the exact
60-second policy while the schema host and immutable objects retain one-year
immutable caching; see `docs/OPERATIONS.md`.

The Cloudflare Pages project `neuralstock` has preview and production
deployments. Its `neuralstock.ai` and `www.neuralstock.ai` custom domains are
active. A zone-level Single Redirect, managed under stable ref
`neuralstock_www_to_apex`, returns 301 from `www` to the apex while
preserving path and query; domain-level redirects are not supported in the
Pages `_redirects` file. The deployed viewer offers a GLB, accepted `.blend`
source, and version manifest download for each asset. All three links resolve
directly to the R2 origin rather than streaming binaries through Pages or a
Worker.

## v0.1.0 release evidence

The canonical release produced:

- signed tag `v0.1.0` at commit
  `6a0d8bb5696a24792c606128b016d2fcf3fad6ff` and an exact six-asset immutable
  GitHub Release;
- 15 CC0-declared Room Zero assets at version 1.0.1, all built twice from the
  accepted source bytes with byte-identical results;
- registry revision
  `744accaa3f9efcd053d8e589b2bb7e966753b070004f7c78ef00c3431cbbe391`,
  225 traversed artifacts, and 9,694,572 verified release bytes;
- a 229-item R2 plan with 227 immutable items and two aliases, SHA-256
  `2355bb10f6f6efb8e330bc7e905f58404dc18afb1fe000066b41598e0a59fcd9`;
- deterministic release archive SHA-256
  `c005f6c59ff066641844580dd8813045da026b93e69688b0c409e22eadcd9187`
  and `SHA256SUMS` SHA-256
  `0f2f65b11f307885a86baa3d3a9a5430fc019241ecbe1043a1b13fe452e2a054`;
- Blender worker manifest
  `sha256:e458059a9a783f8e54ac746361494a1b64d892f66a9f797f498bd11351531298`
  with config
  `sha256:dbf4c5a833b81b63bbec7eb04121056ccc5242aaa5561e3ce7680117d9181eed`;
- independently read-back indefinite locks for the v0.2 schemas, v0.2 profile,
  and exact canonical revision snapshot, with check-only evidence SHA-256
  `2f293a79dd5740109436ad032b89581741ec30282db6be9d814adbe796825d9f`;
- successful protected
  [Phase B run 30730929891](https://github.com/Neuralstock/neuralstock/actions/runs/30730929891)
  and separate
  [production-health run 30731015545](https://github.com/Neuralstock/neuralstock/actions/runs/30731015545)
  on verified deployment controller
  `181e0d661e0e9f6d662e1bc18ecdc37dc38d9cff`; and
- public `neuralstock==0.1.0` and `@neuralstock/client@0.1.0` packages whose
  exact distributions passed clean install and import checks.

The authoritative workflow identities, artifact checksums, lock readbacks,
publication chronology, and documented limitations are recorded in
[`docs/releases/v0.1.0.md`](releases/v0.1.0.md).

### Historical 1.0.0 preview evidence

The separate 2026-08-01 infrastructure-readiness run produced:

- 15 CC0-declared assets and 15 `latest` aliases;
- seven bounded procedural assets;
- 15/15 GLBs with zero Khronos errors and zero warnings;
- 37,928 runtime vertices and 19,268 runtime triangles checked against public
  manifests, plus 25 exact metadata-renderable box colliders;
- 91/91 collection-build files byte-identical across independent rebuilds;
- 15/15 build receipts classified `reproduced` with no allowed
  nondeterminism;
- a twice-exported, timestamp-normalized `linux/amd64` Blender worker manifest
  at `sha256:4ecb8521f9299f1cee400584b2f5eb91386082e11e0386019500a77438532647`
  with config `sha256:b17353ce7c91cc3864cae51062c542ae413b8bbb2bbbf4b91b5b590cf0fdec2a`;
- 15 content-addressed legal-evidence descriptors and 150 build-evidence
  descriptors (30 pinned inputs and 120 comparison-build outputs);
- registry revision
  `a3e851194d092bf1a06452a62ae98ba8687462ea0cbca668a9b9cc2385768523`;
- 225 traversed artifacts totaling 9,655,482 verified bytes; and
- 217 ordered R2 publication operations, with the latest-snapshot alias last.

The verified `dist/release` directory and reproducible worker archive under
`work/final-room-zero-v01-current/` are intentionally ignored by Git. Public
R2 publication was completed as a separate credentialed operation. An external
OCI-registry publication is not assumed by the local release process.

The historical Room Zero 1.0.0 attestation records Joseph Nordqvist as the
individual CC0 dedicator and records the explicit affirmation of ownership or
control of the inputs and authority to make the dedication. Its immutable bytes
have SHA-256
`e687b259dabc8080a610dd2de11be347e444d8f4a7a9a3df8548d92d9e77d58f`.
The 1.0.1 provenance records pin the separate migration-attestation SHA-256
`95531e49b5da7616fa769cdbd7d97a84e51beb8798d5180fb3abfbb2a074c32e`.
The migration evidence supplements rather than modifies the historical
attestation, binds the project and `neuralstock.ai` verification URL, and the
source-migration ledger pins all 15 reused `.blend` inputs. The domain is
corroborative; authenticated repository history remains the durable authority.
Retain both records in authenticated history when publishing; tooling verifies
evidence consistency but cannot independently establish legal authority.

These last evidence counts describe only the historical 1.0.0 preview revision.
The completed schema-domain migration changed contract and receipt hashes and
therefore produced the distinct canonical revision above even though accepted
Blender sources and runtime geometry remained unchanged.
