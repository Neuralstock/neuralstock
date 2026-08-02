# NeuralStock governance

NeuralStock is a public technical and asset commons. Governance protects three
promises: published asset bytes are identifiable and reproducible, the recorded
rights basis is reviewable, and no maintainer can silently replace history.

This document governs the repository and hosted public registry. It does not
change the CC0 status of accepted asset content or the MIT license for software.

## Roles

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
and `pypi` environments. The role can publish already-reviewed bytes but cannot
waive a failed build, validation, provenance, or review gate.

### Security and withdrawal responder

A responder may quarantine a submission, stop a release, remove a version from
discovery, or block hosted delivery during a credible rights or security event.
Emergency action must be followed by a public, non-sensitive notice and normal
review as soon as it is safe.

One person may hold multiple roles during bootstrap. While Joseph Nordqvist is
the only operator, GitHub is configured in the documented `--solo-maintainer`
mode: checks, pull requests, ref restrictions, attestations, and immutable
publication rules remain enforced, but no human approval is represented as
independent. This exception permits only first-party Room Zero publication.
External asset publication still requires two distinct people: one provenance
reviewer and one maintainer or release operator. Public external intake must not
open until a second qualified reviewer is appointed and GitHub has been moved
to reviewer mode.

## Change classes

| Change | Required review |
| --- | --- |
| Documentation with no policy effect | One maintainer |
| Software with no public-contract effect | One maintainer and required CI |
| Schema, profile, registry, licensing, or governance | Two maintainers, compatibility note, required CI |
| External asset or new asset version | Contributor attestation, provenance reviewer, second maintainer, all asset gates |
| Release publication | Protected environment; independent approval in reviewer mode, or a recorded sole-maintainer exception for first-party bootstrap only |
| Withdrawal or emergency block | One responder immediately; second-person review and notice afterward |

GitHub branch protection enforces the baseline approval and `CODEOWNERS` review.
The two-person external-asset rule is a project policy because ordinary branch
protection cannot express it by path.

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
3. two approvals and passing protected checks; and
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

The runbooks in `docs/GITHUB-GOVERNANCE.md`, `docs/OPERATIONS.md`, and
`docs/RELEASE-CHECKLIST-v0.1.md` are normative operational companions to this
policy.
