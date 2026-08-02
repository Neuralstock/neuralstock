# NeuralStock governance

NeuralStock is a public technical and asset commons. Governance protects three
promises: published asset bytes are identifiable and reproducible, the recorded
rights basis is reviewable, and no maintainer can silently replace history.

This document governs the repository and hosted public registry. It does not
change the CC0 status of accepted asset content or the MIT license for software.

## Roles

### Founding project owner

Joseph Nordqvist, GitHub account `@bighippoman`, is NeuralStock's founding
project owner. This role may publish qualifying founder-controlled assets
through the continuing direct-publication lane established by the signed reset
in
[`docs/FOUNDER-BOOTSTRAP-GOVERNANCE-RESET.md`](docs/FOUNDER-BOOTSTRAP-GOVERNANCE-RESET.md).
The lane has no count or calendar limit. It may not claim independent review or
bypass a failed policy, quality, security, reproducibility, or immutability
gate. Separate solo-bootstrap authority governs policy changes while Joseph is
the only qualified maintainer.

### Maintainer

A maintainer may review software and documentation, triage reports, and merge
ordinary changes after required checks and reviews pass. The initial maintainer
is Joseph Nordqvist, GitHub account `@bighippoman`.

### Provenance reviewer

A provenance reviewer evaluates the declared rights holder, source origin,
dependencies, evidence, and trademark, design, and personality-rights flags.
They record a review decision; they do not merely edit the contributor's
assertion. A reviewer with a personal or commercial conflict must recuse.

### Release operator

A release operator may approve the protected `release`, `production`, `npm`,
and `pypi` environments. The role can publish bytes already accepted under the
applicable assessment mode but cannot waive a failed build, validation,
provenance, or assessment gate.

### Security and withdrawal responder

A responder may quarantine a submission, stop a release, remove a version from
discovery, or block hosted delivery during a credible rights or security event.
Emergency action must be followed by a public, non-sensitive notice and normal
review as soon as it is safe.

One person may hold multiple roles during bootstrap. While Joseph Nordqvist is
the only operator, GitHub is configured in the documented `--solo-maintainer`
mode: checks, pull requests, ref restrictions, attestations, and immutable
publication rules remain enforced, but no human approval is represented as
independent. Room Zero used the original exception. Prospectively, the signed
reset establishes a continuing `first-party-founder-controlled` lane after its
machine-readable contract and all prerequisites are enforced. That origin-based
lane is separate from GitHub's temporary solo-maintainer configuration and may
continue if reviewer mode is later enabled. External asset publication still
requires two distinct, conflict-free people: one provenance reviewer and one
maintainer or release operator. Public external intake must not open until that
lane and its lane-aware protected controls are implemented.

## Change classes

| Change | Required review |
| --- | --- |
| Documentation with no policy effect | One maintainer |
| Software with no public-contract effect | One maintainer and required CI |
| Schema, profile, registry-contract, licensing, or governance change | Two maintainers, compatibility note, and required CI; while solo-bootstrap decision authority applies, the founding project owner may act prospectively with explicit zero-independent-approval disclosure |
| Founder asset-ID registration under the existing ledger contract | Signed founder registration, namespace and ledger-integrity checks; no second-person approval required or claimed |
| Eligible `first-party-founder-controlled` asset version | Founder source/rights attestation, generated lane verdict, founder-self-assessment disclosure, and all asset gates; no second-person approval required or claimed |
| External asset or other new asset version | Contributor attestation, conflict-free provenance reviewer, second maintainer, and all asset gates |
| Release publication | Lane-aware protected environment or equivalently auditable control; independent approval for external assets, founder attestation and machine gates for an eligible founder candidate |
| Withdrawal or emergency block | One responder immediately, with a public non-sensitive tombstone and immutable audit record; independent follow-up when a qualified responder exists |

GitHub branch protection enforces pull requests, signatures, history, and the
checks applicable to both modes. Before external intake opens, reviewer mode
must enforce its human-review requirements without imposing them on an eligible
founder asset, using a lane-aware required check or an equivalently auditable
control. Ordinary branch protection cannot express the distinct review rules
for both asset lanes by path and metadata alone.

### Founder decision and publication process

The prospective founder reset was unilaterally ratified by Joseph Nordqvist
with zero independent approvals. It explicitly does not satisfy the pre-reset
two-approval rule. While solo-bootstrap decision authority applies, every
founder policy or public-contract decision must:

1. identify the exact policy, contract, or release-process scope;
2. use a signed commit and pull request against protected `main`;
3. pass all protected checks applicable to that scope;
4. record compatibility, versioning, and migration consequences;
5. state `independent_human_review: false`; and
6. remain prospective and preserve all immutable history.

The continuing asset lane, including conforming ID registrations, is not
limited by the end of solo-bootstrap decision authority. Every eligible founder
asset requires prior ID registration, the machine-generated lane verdict, a
per-version founder attestation, and the public disclosure defined by the
reset. Until that enforcement exists, the reset authorizes implementation work
but not publication of a new non-Room-Zero asset.

## Controlled contributor scope

The first external beta accepts only generic, static assets that are original
work of the direct dedicator. All resources must be creator-authored and packed
inside the Blender source. The beta does not accept:

- imported meshes, scans, kitbash components, or third-party textures;
- recognizable people, brands, or distinctive product designs;
- AI-generated or AI-derived artistic inputs without a separately approved
  rights policy;
- animations, embedded scripts, drivers, executable hooks, or network inputs;
  or
- a public-domain assertion that depends only on an upstream label or filename.

Expanding scope requires a recorded policy decision, schema support, tests, and
review guidance before the first affected contribution is accepted.

## Decision process

Ordinary implementation choices are made in pull requests. Changes that alter
the public contract, licensing policy, trust boundary, namespace, or withdrawal
semantics require:

1. a written decision in `docs/` describing context, alternatives, and
   compatibility;
2. a pull request linked to that decision;
3. two approvals and passing protected checks, except for an explicitly
   disclosed prospective decision made while solo-bootstrap decision authority
   applies; and
4. a migration or versioning plan when published clients can be affected.

Published schema and profile versions are immutable. A correction creates a new
version; it does not rewrite the meaning of an existing identifier.

## Conflicts, appeals, and conduct

Reviewers disclose conflicts and recuse. A contributor may request a second
review of a rejection, but no one is entitled to publication and quality or
provenance gates are not relaxed to meet an asset-count target. Good-faith
rights and security reports must not be retaliated against.

Repository participation requires professional, specific, and respectful
communication. Harassment, threats, doxxing, discriminatory conduct, and
deliberate submission of stolen or hostile content are not accepted. A
maintainer may restrict participation to protect contributors or the project.

## Release and audit record

Every production release is tied to a protected commit, deterministic candidate
archive, checksums, GitHub artifact attestation, registry revision, build
receipt graph, and deployment workflow run. Credentials are scoped to the
protected job that needs them and never enter pull-request validation.

The current operational runbooks in `docs/GITHUB-GOVERNANCE.md` and
`docs/OPERATIONS.md` are normative companions to this policy.
`docs/RELEASE-CHECKLIST-v0.1.md` is the historical Room Zero v0.1.0 checklist;
it is not a generic founder-lane release checklist.
`docs/FOUNDER-BOOTSTRAP-GOVERNANCE-RESET.md` is the signed decision record that
establishes the continuing founder lane. A generic founder-lane release
checklist is required before the first non-Room-Zero publication.
