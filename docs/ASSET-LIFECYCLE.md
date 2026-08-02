# Asset lifecycle and contribution flow

NeuralStock separates asset creation from public distribution. A model may be
developed for days in a workshop repository, but an accepted version becomes a
normal public registry entry with individually downloadable source, runtime,
metadata, preview, license, and evidence artifacts.

This separation lets creators iterate freely without turning the canonical
repository into a large-binary staging area. It does not hide successful work
from users.

## Status and rollout boundary

This document defines the target lifecycle and the transition needed for daily
publication at larger scale. It does not claim that every component is deployed
today and does not supersede the current versioned static-registry contract.

During the 15–100 asset phase, GitHub Actions performs trusted builds and R2
holds immutable artifacts while each publication produces a complete static
registry snapshot. The first founder-lane implementation must add quarantine,
incremental per-asset or bounded-batch validation, public per-asset discovery,
and withdrawal without silently changing that contract. Worker/D1 projection,
durable orchestration, registry deltas, one-time prefix retention, and package
decoupling are explicit migrations for later scale phases. Each requires its
own versioned contract and compatibility decision before becoming normative.

## Public result

Every accepted asset version is intended to expose:

- a stable `asset_id@version` and immutable version manifest;
- the authored `.blend` source;
- the exact published GLB;
- `asset.json` semantic and geometry metadata;
- previews and inspection renders;
- collision, anchor, bounds, budget, and validation evidence;
- the CC0 dedication and controlled-input hashes;
- the actual assessment mode and decision record; and
- direct immutable download URLs plus a mutable `latest` discovery pointer.

The website presents searchable collection and per-asset pages for people. The
Worker API, registry snapshots, and client packages expose the same collection
for agents, Three.js applications, engines, mirrors, and training pipelines.
The public registry—not a workshop directory—is the complete accepted
collection.

## Repository and storage boundaries

### [`neuralstock-model-creation`](https://github.com/Neuralstock/neuralstock-model-creation)

The creation repository is the workshop and production queue. It may contain
roadmaps, reference packets, Blender generator scripts, iteration notes, local
render comparisons, and candidate manifests. An asset in this repository is
not accepted merely because it exists there.

Its protected `main` requires signed pull-request history and a machine boundary
check with zero required human approvals. A delivery workflow emits only an
attested compact envelope after the workshop record reaches `delivery_ready`;
canonical ingestion must independently verify that envelope, its exact commit,
and all quarantine and policy receipts before acceptance.

Large candidate files should enter private immutable quarantine storage through
a trusted upload path instead of accumulating in Git history.

### `neuralstock`

The canonical repository is the control plane. It contains governance,
policies, schemas, profiles, validators, release tooling, compact registration
and decision records, and reproducible tests. Candidate pull requests refer to
quarantined bytes by receipt and SHA-256 rather than making Git the large-binary
delivery plane.

### Target Cloudflare data plane

- Private R2 quarantine will store untrusted candidate bytes and immutable
  upload receipts.
- Public R2 stores accepted `.blend`, GLB, previews, manifests, attestations,
  evidence, deltas, and periodic full snapshots.
- D1 will become a query projection for paginated catalog, category, tag,
  capability, dimension, and license searches. It can be rebuilt from immutable
  registry records and is not the sole source of truth.
- A Worker will serve the public API and download routing when Phase 1 begins.
  Durable workflow state will coordinate multi-step ingestion, retries,
  promotion, and projection updates when Phase 2 load warrants it, without
  making a request connection the job boundary.

## Target candidate flow

1. **Register the ID.** Reserve a stable ID in the append-only,
   content-hashed registration ledger. Founder IDs may be registered
   individually or in bounded rolling batches. Registration prevents namespace
   collisions; it does not accept the asset.
2. **Create and inspect.** Develop the Blender source in the workshop. Record
   intended dimensions, category, anchors, interactions, visual references,
   controlled inputs, and applicable profile.
3. **Upload to quarantine.** A trusted path stores the exact source and inputs
   under content hashes and returns an immutable receipt. Pull-request code
   cannot access publication credentials.
4. **Build in isolation.** A pinned, non-root Blender environment with no
   network, no production credentials, read-only inputs, dropped privileges,
   and finite resource limits produces the GLB, metadata, collisions, previews,
   and inspection report.
5. **Validate the candidate.** Outer validators check schema, hashes, geometry,
   transforms, dimensions, budgets, materials, texture limits, anchors,
   collisions, reproducibility, browser loading, and category-specific visual
   expectations. A failure is fail-closed.
6. **Record the applicable human mode.** A founder-controlled candidate records
   Joseph's signed rights attestation and founder self-assessment with
   `independent_human_review: false`. A future external candidate requires its
   conflict-free provenance and release approvals.
7. **Accept the exact bytes.** A protected signed decision binds the asset
   version, all input and output hashes, policies, profiles, toolchain, results,
   and assessment mode. Policy or verifier changes cannot share the candidate
   change that relies on them.
8. **Promote by hash.** The publisher copies the already-validated bytes from
   quarantine to immutable public keys. It never rebuilds or substitutes the
   accepted version during promotion.
9. **Update discovery.** In the current static phase, the publisher creates and
   verifies a complete immutable snapshot before advancing the mutable discovery
   alias and website index. After the separately versioned scaling migration,
   it appends a registry delta and updates the D1 projection atomically and
   idempotently. In both modes, the individual asset page and downloads then
   become visible.
10. **Audit and mirror.** Scheduled jobs verify samples and periodic complete
    snapshots independently of the hot publication path.

A bounded batch may transport several candidates efficiently, but each asset
version still receives its own receipt, attestation, validation verdict,
manifest, and acceptance record. One failed candidate must not erase the audit
records of the others, and promotion is only allowed for passing entries.

## Contribution lanes

### Founder Direct Publication

Joseph Nordqvist may continuously submit qualifying work he originates and
controls through `first-party-founder-controlled`. There is no fixed
model-count or date limit and no second human reviewer is required. Every
version remains publicly marked **founder-attested, machine-validated**, with
the absence of independent human provenance and quality review stated plainly.

Each version also discloses whether its source was manually authored in
Blender, procedurally generated, or tool-assisted.

The lane categorically rejects human-created third-party artistic inputs and
cannot waive any technical, security, evidence, or rights gate. Disclosure,
assignment, permission, or CC0 status does not turn another person's art into
founder-origin work. Tool or generated-reference assistance must be disclosed
under an adopted policy. Copyrightable artistic input or shared authorship from
another human uses the external, import, or a future collaborative lane rather
than Founder Direct Publication.

### External direct contributors

This lane is not open yet. Its intended process adds contributor identity and
rights attestation, conflict-free provenance review, and a distinct release
operator to the same quarantine, build, validation, promotion, and discovery
pipeline. Opening intake requires the lane-aware controls specified in
`GOVERNANCE.md`.

### Existing CC0 source imports

Curating Poly Haven, ambientCG, or another upstream CC0 collection is a
different provenance case from founder-origin work. A future import lane must
preserve the upstream creator, original license evidence, source URL, retrieval
time, hashes, transformation history, and any non-copyright restrictions. It
must not represent Joseph as the original creator or dedicator.

## Corrections, versions, and withdrawal

Accepted bytes are immutable. A changed mesh, material, source, metadata
contract, or controlled input creates a new semantic version and its own full
record. Mutable aliases may point discovery at a newer accepted version, while
old immutable versions remain verifiable.

A credible rights or security concern can remove a version from discovery and
block hosted delivery immediately. Withdrawal preserves hashes, publishes a
non-sensitive tombstone, and appends an immutable incident record; it never
silently replaces the original bytes or changes the meaning of a CC0
dedication.

## Scaling to tens of thousands

The publication hot path must eventually become incremental rather than
rebuilding the entire catalog for each asset. The current complete static
snapshot remains normative through the Phase 0 rollout. The versioned Phase 1
and Phase 2 migrations should:

- build, attest, validate, and publish per asset or bounded batch;
- append immutable registry deltas and atomically update the D1 projection;
- use cursor pagination and server-side filtering instead of loading every
  manifest before applying a limit;
- lock immutable R2 prefixes once instead of creating a retention rule for
  every snapshot;
- keep mutable aliases outside immutable snapshot prefixes;
- run complete-corpus rebuilds and mirror verification as scheduled audits, not
  as the daily publication path;
- virtualize or paginate the human catalog instead of rendering every card;
  and
- keep package releases independent from asset-version publication.

Once adopted, this shape lets the collection grow daily while retaining
per-version evidence, individual downloads, complete snapshots, and a
rebuildable public index.
