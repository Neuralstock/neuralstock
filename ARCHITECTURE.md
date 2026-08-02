# NeuralStock Architecture

**Status:** Accepted for the initial implementation  
**Last updated:** 2026-08-01

## Decision

NeuralStock will use a hybrid architecture:

- **GitHub is the public workshop:** governance, schemas, tooling, reviewed manifests, provenance, and contribution history.
- **Cloudflare is the production data and execution plane:** Workers, R2, D1, Queues, Workflows, Containers, and—only where serialization is required—Durable Objects.
- **Convex is not part of the initial architecture.** It may be reconsidered if a realtime contributor and moderation application becomes a primary product requirement.

Durable Objects are not the registry database. The registry is read-heavy and must support cross-asset filtering and search, so D1 is the canonical runtime index. Durable Objects are reserved for narrowly scoped coordination such as one build lock or live progress stream per job.

This separation keeps the public project transparent and forkable while giving asset delivery and Blender execution a path to production scale.

## Goals

1. Make CC0 Blender assets immediately usable by humans, Three.js applications, game engines, and autonomous agents.
2. Preserve both the editable Blender source and a web-ready GLB for every published version.
3. Make every build reproducible, inspectable, content-addressed, and immutable.
4. Support deterministic structured queries before adding semantic search.
5. Execute Blender ingestion and generation safely without trusting contributor-supplied files or Python.
6. Avoid bandwidth economics that become worse as public adoption grows.
7. Keep the public format and build runner portable enough to migrate away from any hosting vendor.

## Non-goals for the first release

- Realtime collaborative Blender editing.
- Hosting arbitrary always-on agent processes.
- GPU rendering or large cinematic texture baking.
- Supporting every open-content license.
- Building semantic/vector search before structured catalog search is proven insufficient.
- Using blockchain or a custom package protocol for provenance.

## System overview

```text
 Contributor
     |
     |-- source.blend ---------------------------> private R2 staging
     |
     `-- GitHub pull request
           asset.intent.json
           provenance.json
           source SHA-256
                    |
                    v
          GitHub App / Worker webhook
                    |
                    v
             Cloudflare Workflow
          validate -> inspect -> build -> verify
                    |
                    v
                  Queue
                    |
                    v
       isolated Blender Container / Sandbox
          |                              |
          |                              |
          v                              v
    previews, reports              GLB and source artifacts
          |                              |
          `---------------+--------------'
                          |
                          v
             immutable content-addressed R2
                          |
              +-----------+-----------+
              |                       |
              v                       v
       D1 catalog + FTS5       periodic registry snapshot
              |
       optional Vectorize
              |
              v
       Worker REST/MCP API
              |
              v
       direct CDN downloads from R2
```

## Component responsibilities

### GitHub: governance and reviewed intent

GitHub contains:

- JSON Schemas and registry specifications.
- Ingestion, validation, Blender, and export tooling.
- Human-reviewed asset intent and provenance manifests.
- License attestations and contribution history.
- Client packages, examples, documentation, and architectural decisions.
- Pull-request checks and the initial trusted build pipeline.

Large generated binaries do not belong in Git history. The 7.4 MB Room Zero
pilot deliberately versions its 15 accepted `.blend` inputs so a fresh clone
can prove the complete build; this is a bounded bootstrap exception. Generated
GLBs, previews, reports, and future accepted sources are published to R2 once
the collection outgrows that exception. GitHub Releases remain an acceptable
temporary mirror.

### R2: immutable artifact storage

R2 stores:

- Original accepted `.blend` sources.
- Exported `.glb` runtime assets.
- Textures, thumbnails, turntables, collision meshes, and optional LODs.
- Build receipts, inspection reports, and complete registry snapshots.

Published objects are content-addressed by SHA-256 and are never overwritten. Human-readable release paths are aliases or manifest references, not mutable copies of authoritative bytes.

Example keys:

```text
staging/{upload-id}/source.blend
objects/sha256/{first-two-hex}/{sha256}
assets/{asset-id}/{version}/manifest.json
snapshots/{registry-revision}/registry.json
```

Clients download large files directly from an R2 custom domain. Workers must not proxy normal asset downloads or large uploads. Contributor uploads use short-lived presigned multipart URLs into a private staging bucket.

### Workers: stateless edge API

Workers provide:

- Public catalog and resolution endpoints.
- Authentication and authorization for contributor operations.
- Request validation, rate limiting, and upload authorization.
- Presigned R2 upload issuance.
- GitHub webhooks and job submission.
- REST, MCP, and package-client-facing interfaces.

Workers return metadata and immutable artifact URLs. They do not execute Blender or retain authoritative mutable state in process memory.

### D1: rebuildable runtime catalog

D1 stores the queryable projection of approved manifests and build receipts. Expected entities include:

- `assets`
- `asset_versions`
- `artifacts`
- `builds`
- `provenance_records`
- `geometry_node_parameters`
- `anchors`
- `material_and_mesh_metrics`
- `compatibility_profiles`

Dimensions, license status, triangle bands, file sizes, engine compatibility, categories, and publication state are indexed structured fields. Names, aliases, descriptions, tags, materials, and affordances are denormalized into an FTS5 search document.

D1 is a disposable read model: it must be possible to rebuild it from reviewed Git manifests and immutable R2 build receipts. A periodic complete registry snapshot ensures consumers can mirror the catalog without using the hosted API.

### Queues and Workflows: durable ingestion

Workflows own the multi-step ingestion state machine and durable retries. Queues buffer Blender work and allow execution capacity to scale independently.

Queue messages contain identifiers and hashes, not asset binaries. Delivery is treated as at-least-once, so every step must be idempotent.

Initial states:

```text
draft
  -> uploaded
  -> quarantined
  -> validating
  -> building
  -> review_pending
  -> published

Any processing state may transition to failed or rejected.
```

Publication is atomic from a catalog reader's perspective: an asset version becomes discoverable only after every required artifact and report has passed validation.

### Containers and Sandbox: Blender execution

Headless Blender runs in a versioned OCI container, not inside a Worker or Durable Object. Each build has explicit CPU, memory, disk, wall-clock, and output-size limits.

Contributor content is untrusted:

- Blender auto-execution of embedded Python is disabled.
- Only repository-owned ingestion scripts execute automatically.
- Contributor-supplied hooks require separate review and a stronger isolated execution policy.
- Build workers receive no production secrets beyond narrowly scoped job credentials.
- Network egress is disabled unless a specific build step requires an allowlisted destination.
- Staging, quarantine, and published storage are separated.
- A failed or timed-out job cannot publish artifacts.

Cloudflare Containers are suitable for ordinary CPU-based inspection, Geometry Nodes evaluation, GLB export, previews, and lightweight bakes. Jobs requiring GPU rendering or more than the available container resources use an external runner behind the same job interface.

### Durable Objects: narrow coordination only

Durable Objects may be introduced for:

- `build:{build-key}` deduplication and mutual exclusion.
- `publish:{asset-id}` serialization.
- Live job progress and WebSocket log streams.
- A single on-demand generation session.

There will be no global registry Durable Object. Catalog queries, filtering, and search remain in D1.

### Vectorize: optional semantic discovery

Vectorize is a derived index, never an authority. It is added only after catalog usage shows that FTS5 plus structured filtering cannot serve natural-language discovery adequately.

A semantic query returns candidate asset IDs. D1 then applies authoritative constraints such as license, dimensions, polygon budget, parameter ranges, and engine compatibility before results are returned.

## Asset contract

Every published asset version contains or references:

```text
asset.json              semantic metadata and runtime contract
source.blend            editable Blender source
model.glb               web/game-engine runtime artifact
provenance.json         origin, authorship, license evidence
build-receipt.json      reproducibility inputs and output hashes
inspection.json         dimensions, budgets, anchors, materials, validation
toolchain.json          exact package/schema/profile/validator hash inventory
evidence.*              hashed CC0 and independent-build evidence
preview.*               one or more visual previews
```

Optional artifacts include collision meshes, LODs, texture variants, navigation metadata, animation clips, and agent modification hooks.

### Identity and immutability

- `asset-id` is a stable semantic identifier.
- `asset-id@version` identifies an immutable published release.
- `latest` is a mutable alias resolved by the catalog; it is never embedded as an artifact identity.
- SHA-256 identifies the exact bytes of every artifact.
- Deleting or replacing a published version is prohibited except through an explicitly recorded legal or security withdrawal process.

### Reproducible build key

The idempotency and cache key is derived from:

```text
source SHA-256
+ normalized parameter SHA-256
+ Blender image digest
+ build platform
+ asset-intent and authored-provenance SHA-256
+ every legal-evidence SHA-256
+ exact target-profile SHA-256
+ package/schema/validator toolchain SHA-256
+ validator version
```

The build receipt records those values, Blender version, timestamps, validation
results, raw independent-build evidence, output hashes, and any narrowly
allowed nondeterminism.

## Licensing policy

NeuralStock separates asset licensing from software licensing:

- Published 3D content and its bundled textures use **CC0-1.0** or carry reviewed evidence of equivalent public-domain status.
- Repository software and reusable Python tooling use the project's chosen permissive software license, initially **MIT**.
- MIT is not used as a substitute for CC0 on the artistic asset itself because MIT retains a license-notice obligation.
- Every imported source requires durable provenance evidence; a filename or upstream `CC0` tag alone is insufficient.
- Runtime metadata exposes both a normalized SPDX-style license identifier and the underlying provenance record.

This policy protects the central promise: commercial use, modification, redistribution, scene generation, and model-training use without attribution tracking for the asset content.

## Public API shape

The initial public interface should remain small and cacheable:

```text
GET  /v1/assets
GET  /v1/assets/{asset-id}
GET  /v1/assets/{asset-id}/versions/{version}
GET  /v1/resolve/{asset-id}@{version-or-alias}
GET  /v1/search
GET  /v1/snapshots/latest

POST /v1/uploads             authenticated contributor operation
POST /v1/builds              authenticated contributor/agent operation
GET  /v1/builds/{build-id}
```

Structured filters are part of the stable contract. Semantic search may be exposed later without changing deterministic resolution endpoints.

## Scaling plan

### Phase 0: foundation, 15–100 assets

- Store schemas, tooling, manifests, and provenance in GitHub.
- Run reviewed ingestion jobs in GitHub Actions.
- Publish immutable artifacts to R2.
- Generate a static registry snapshot and previews.
- Provide a minimal TypeScript client that reads the snapshot.
- Avoid D1, Durable Objects, Vectorize, and a custom contributor portal until needed.

### Phase 1: public registry, 100–10,000 assets

- Add the Worker API and an R2 custom domain.
- Materialize manifests and receipts into D1.
- Add structured filtering and FTS5 search.
- Add authenticated, direct-to-R2 staging uploads.
- Add bucket retention protections for published objects.

### Phase 2: automated ingestion

- Move ingestion orchestration to Workflows and Queues.
- Run Blender builds in isolated Cloudflare Containers.
- Add quotas, retries, dead-letter handling, observability, and administrative review.
- Keep the GitHub contribution and provenance path intact.

### Phase 3: agent-native generation

- Allow authenticated agents to request parameterized builds.
- Add a Durable Object per build key only when concurrent duplicate work becomes observable.
- Stream live progress when it materially improves agent or contributor behavior.
- Add capability-based quotas and abuse controls.

### Phase 4: large-scale discovery

- Add Vectorize for semantic candidate retrieval.
- Enable D1 read replication and partition the catalog only when measured limits require it.
- Publish regular full snapshots and support third-party mirrors.
- Route exceptional GPU or high-memory builds to compatible external workers.

## Why not GitHub alone?

GitHub is excellent for open governance but is not a low-latency catalog database, semantic registry, job orchestrator, or general large-binary data plane. Git repositories also have a 100 MB object limit and a recommended on-disk size ceiling; Git LFS stores each changed binary revision in full. Releases are useful for bootstrapping but do not provide the complete query and execution plane NeuralStock needs.

GitHub remains essential—it simply has a deliberately narrower responsibility.

## Why not Convex initially?

Convex offers an excellent developer experience for reactive metadata, live dashboards, scheduling, full-text search, and vector search. It is a strong candidate if realtime contributor collaboration becomes the product's differentiator.

It is not selected initially because:

1. Public binary egress is a fundamental NeuralStock workload, and R2 has materially better delivery economics.
2. Convex does not remove the need for object storage or an external containerized Blender runner.
3. Combining GitHub, Convex, and Cloudflare would create two application control planes before the product demonstrates a need for them.
4. D1, Workers, Workflows, and Queues cover the initial registry requirements within the same platform as R2 and Containers.

Reconsider Convex when at least one of these becomes true:

- Realtime moderation and contributor subscriptions are a top-three product capability.
- The team spends more time maintaining realtime application plumbing than building registry value.
- A dedicated collaborative portal becomes more important than the GitHub contribution workflow.
- A measured prototype demonstrates that Convex materially reduces total system complexity even while R2 and an external Blender runner remain.

## Portability and anti-lock-in rules

- Public manifests contain SHA-256 identities and standard URLs, never vendor-internal object IDs.
- R2 access uses S3-compatible operations behind a small storage interface.
- Blender workers are versioned OCI images with a documented stdin/job and output contract.
- D1 and Vectorize are rebuildable derived indexes.
- Complete registry snapshots are published regularly.
- Schemas, provenance rules, and validators remain public in Git.
- A mirror can reconstruct the registry from Git manifests, R2 artifacts, and build receipts.

## Operational invariants

1. Published versions and content-addressed objects are immutable.
2. No asset is discoverable until its required artifacts validate.
3. Every artifact has a verified hash, provenance record, and normalized license.
4. Every build is idempotent for the same build key.
5. Large uploads and downloads bypass Worker bodies.
6. Untrusted Blender content never runs with production credentials.
7. Search indexes can be lost and rebuilt without losing registry truth.
8. Structured constraints are authoritative; semantic similarity is advisory.
9. The hosted service is convenient, but the public registry remains mirrorable.

## Cost model

The architecture is optimized for a workload where downloads greatly exceed writes:

- R2 Standard storage is currently priced at $0.015/GB-month with no Internet egress charge.
- Worker, D1, Queue, Workflow, and Container costs scale primarily with API traffic and actual build work.
- Direct CDN downloads prevent API compute from growing linearly with asset byte volume.
- Content-addressed outputs deduplicate identical builds and enable effectively permanent caching.

Costs and limits must be checked again before production launch; they are inputs to the architecture, not part of the public protocol.

## References

- [Cloudflare R2 pricing](https://developers.cloudflare.com/r2/pricing/)
- [Cloudflare R2 limits](https://developers.cloudflare.com/r2/platform/limits/)
- [Cloudflare Workers limits](https://developers.cloudflare.com/workers/platform/limits/)
- [Cloudflare D1 SQL and FTS5 support](https://developers.cloudflare.com/d1/sql-api/sql-statements/)
- [Cloudflare D1 limits](https://developers.cloudflare.com/d1/platform/limits/)
- [Cloudflare Durable Objects design guidance](https://developers.cloudflare.com/durable-objects/best-practices/rules-of-durable-objects/)
- [Cloudflare Queues delivery guarantees](https://developers.cloudflare.com/queues/reference/delivery-guarantees/)
- [Cloudflare Workflows](https://developers.cloudflare.com/workflows/)
- [Cloudflare Containers limits](https://developers.cloudflare.com/containers/platform-details/limits/)
- [GitHub repository limits](https://docs.github.com/en/repositories/creating-and-managing-repositories/repository-limits)
- [GitHub release limits](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases)
- [Convex pricing](https://www.convex.dev/pricing)
- [Convex execution limits](https://docs.convex.dev/production/state/limits)

## Phase 0 implementation status

The package v0.1 repository now implements the v0.2 contract decisions above: strict public schemas,
the `web-v1` profile, the reviewed Room Zero catalog, a pinned Blender worker,
two-build reproducibility evidence, immutable local and R2-compatible
publication, a TypeScript client, and a real-asset Three.js browser test.

The hosted Cloudflare control plane remains the next scaling phase. R2 sync is
implemented now because it preserves the static contract; D1, Workers,
Workflows, Queues, Containers, Vectorize, and narrowly scoped Durable Objects
should be introduced only when a public hosted registry or automated ingestion
load requires them.
