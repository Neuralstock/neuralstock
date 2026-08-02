# Rollout plan

## Goal

Move from the 15-asset, first-party Room Zero proof to a trustworthy public
collection of 100 individually downloadable CC0 assets, with a contribution
path that remains useful when the original maintainer is not present.

Asset count is an exit condition only when every accepted version retains the
full source, runtime, provenance, validation, reproducibility, review, and
withdrawal contract. The static registry and R2 remain the production shape
through this rollout. D1, Durable Objects, and semantic search are added only
after measured discovery or coordination needs justify them.

## Eight rollout-critical findings

1. **The public workshop must be made real.** The repository needs an
   authenticated initial history, public remote, protected `main`, review
   ownership, and protected release environments.
2. **Source intake is not yet a contributor product.** Documentation references
   an upload flow, but a private quarantine upload receipt and generic
   per-asset runner are still required.
3. **CC0 assent must bind authority to bytes.** A name and timestamp are not
   enough; external attestations must bind verified identity, source and
   dependency hashes, asset version, and submission ID.
4. **Asset validation must use trusted tooling.** Contributor data must be
   tested with a digest-pinned toolchain from protected `main`, not validator
   code that the same asset pull request can change.
5. **Untrusted Blender needs an outer isolation boundary.** No production
   secret or publication identity may enter the ephemeral VM/sandbox that opens
   a contributor file.
6. **Withdrawal must be executable, not only modeled.** The publisher must
   create notices, recompute aliases, update discovery, and support emergency
   delivery blocks without pretending that a valid CC0 dedication was revoked.
7. **Procedural and visual quality needs broader proof.** Default builds alone
   do not establish safe parameter ranges; standardized multiview review and
   boundary/option tests are required.
8. **A single broad performance ceiling will not scale.** Props, furniture, and
   architecture need immutable category profiles with measured runtime,
   texture-memory, primitive, collision, and source-size budgets.

## Milestones and gates

### R0 — Public repository and policy freeze

Deliver:

- signed initial commit and release tag;
- canonical repository and schema namespace decision;
- verified npm/PyPI namespace control and exact trusted-publisher identities;
- protected `main`, `CODEOWNERS`, issue forms, and pull-request template;
- `release`, `production`, `npm`, and `pypi` environments with exact branch/tag
  policies, plus required reviewers as soon as a second operator exists;
- controlled-beta scope, reviewer roles, and rights/withdrawal policy; and
- a second person appointed for external provenance review.

Bootstrap gate: all named protected checks have completed once on `main` and the
protection script has been applied in the explicitly recorded solo-maintainer
mode. This permits first-party Room Zero work but does not complete the external
intake gate. Full R0 exit additionally requires reviewer mode, administrator
bypass disabled for protected environments, and a dry-run pull request and
deployment that cannot proceed without a non-initiating reviewer.

### R1 — Reproducible candidate and deployment lane

Deliver:

- independently verified Room Zero release candidate archive;
- Room Zero asset version 1.0.1 under the owned schema namespace, with the
  immutable 1.0.0 manifests and attestation object preserved byte-for-byte and
  distinct migration evidence published;
- deterministic checksums and GitHub build-provenance attestation;
- independently attested package candidates plus protected OIDC publication to
  npm and PyPI;
- protected, manual production deploy that consumes a specific workflow run,
  commit, version, and registry revision; and
- scheduled public health verification.

Exit gate: two clean release-candidate runs from the same commit produce the
same registry revision and release archive checksum; a candidate built from a
different commit or revision is rejected by deployment; and clean consumers can
install the exact tagged Python and npm versions from their public registries.

### R2 — Single-asset quarantine intake

Deliver:

- contributor scaffolding and a complete worked example;
- private, size-limited upload with an immutable receipt;
- generic asset ID/version runner rather than Room Zero globbing;
- pre-Blender file, hash, and media checks;
- ephemeral no-secret VM/sandbox build; and
- trusted-base toolchain selection for asset pull requests.

Exit gate: one valid, one malformed, one over-budget, one unauthorized, and one
resource-exhaustion fixture each reach the intended state without a manual
filesystem operation or any path to publication on failure.

### R3 — Review and withdrawal operations

Deliver:

- identity-bound, versioned CC0 attestation;
- separate provenance-review decision and conflict disclosure;
- standardized multiview, wireframe, anchor, and collision evidence;
- numeric min/default/max, all enum options, and bounded pairwise procedural
  tests;
- signed withdrawal notice, alias recomputation, site/client behavior, and
  emergency delivery block; and
- restoration and independent-mirror drill.

Exit gate: a simulated asset can be submitted, rejected, corrected, approved,
published, withdrawn from discovery, and independently mirrored while every
state transition remains auditable.

### R4 — Invite-only external beta

Invite 5–10 creators to contribute 20–30 direct-original assets. Do not waive a
gate to increase the acceptance count.

Exit gate:

- at least five people complete the flow without private step-by-step help;
- every publication has two distinct reviewers and zero unresolved rights
  states;
- 100% of procedural assets pass their declared parameter test matrix;
- median automated feedback is under 15 minutes;
- median accepted submission publishes within three business days;
- median maintainer effort is at most one hour per accepted asset; and
- CI flake rate is below 2%.

### R5 — Public contribution rollout to 100 assets

Open the contribution lane after resolving the beta's dominant rejection and
support causes. Add optimized profiles or search infrastructure only as
separately versioned, measured changes.

Exit gate:

- 100% of published versions have source, GLB, provenance, inspection, receipt,
  preview, checksums, and review decision;
- all published GLBs have zero Khronos errors and warnings and pass their
  declared profile;
- publication accepts no unexplained nondeterminism;
- public origin and site availability is at least 99.9%;
- a complete independent mirror verifies on schedule;
- an emergency withdrawal reaches registry discovery and the site within one
  hour; and
- at least three independent projects consume NeuralStock without private
  repository-specific assistance.

## Measures

Track submission-to-feedback time, submission-to-publication time, maintainer
minutes, build success, reproducibility, parameter-variant failures, profile
violations, review turnaround, withdrawal response, mirror health, download
success, per-asset reuse, and independent consumers.

Track provenance rejection reasons as a diagnostic. Do not optimize for a lower
provenance rejection rate: that would create pressure to weaken the project's
most important promise.
