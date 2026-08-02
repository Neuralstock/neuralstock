# Founder bootstrap governance reset and continuing direct-publication lane

## Decision record

| Field | Value |
| --- | --- |
| Decision ID | `NS-GOV-RESET-2026-08-02` |
| Adoption mode | Unilateral founder ratification |
| Status | Proposed on branches; effective in the first GitHub-verified signed commit on protected `main` that contains this decision ID |
| Authoritative signature | The activating protected-branch commit |
| Corroborating signed tag | `governance-founder-bootstrap-2026-08-02` |
| Project owner and decision maker | Joseph Nordqvist |
| Authenticated GitHub identity | `@bighippoman` |
| Independent approvals | `0` |
| Pre-reset two-approval process satisfied | **No** |
| Effect | Prospective only |
| Pre-reset policy commit | `306c4f230b572b130db49ee509fc0dc75d68a014` |
| Pre-reset `GOVERNANCE.md` SHA-256 | `23e7f1b3f185fd881751bcd5735ecf71c4a6e192a56bb4169043938a1616f07e` |
| Pre-reset `CONTRIBUTING.md` SHA-256 | `a6374b5391db2c285d50c9bb48977f81e7b17a59425847dea4d2f9d2be23601e` |
| Pre-reset GitHub-governance SHA-256 | `9dcd2b720dbc5a5811739fbc82775f24506e0d43b41a3bf8272b829a49ac7ef2` |

Joseph Nordqvist, as NeuralStock's project owner, unilaterally ratifies this
founder bootstrap governance reset. The pre-reset policy required two approvals
for governance, licensing, schema, profile, registry, and trust-boundary
changes. That process cannot be satisfied while Joseph is the only qualified
maintainer. This reset openly supersedes that rule only for the prospective
scope stated below. It must not be cited as evidence that the former
two-approval rule was followed.

The activating GitHub-verified signature is authoritative. The signed
annotated tag is a discoverable corroborating signature and is not a second
approval or an additional activation condition. The protected commit's
timestamp is the effective timestamp. No independent human review, approval,
or endorsement is claimed.

This is a standalone governance change. It contains no asset candidate,
asset-ID registration, generated-reference policy, schema, profile, verifier,
or release publication.

## Prospective clauses superseded

This decision supersedes the pre-reset requirements that:

- the solo-maintainer exception permit Room Zero publication only;
- every bootstrap governance, licensing, schema, profile, registry, or
  trust-boundary change receive two maintainer approvals while Joseph is the
  only qualified maintainer; and
- every new asset version receive a separate provenance reviewer and second
  maintainer, but only for an eligible founder-controlled asset published
  through the continuing lane defined here.

Those requirements remain historical facts for the pre-reset period. External
asset requirements remain active and are not superseded.

## Purpose and rationale

NeuralStock needs a dense baseline collection before it can materially reduce
the time and token cost of turning a scene idea into a working application.
Joseph intends to add founder-controlled assets regularly—during the Foundation
50 tranche and afterward—so creators and agents can find, inspect, customize,
and download useful CC0 models instead of recreating common objects in code.

Requiring a second person to approve every asset Joseph originates would make
that baseline depend on reviewer availability rather than asset quality. The
honest alternative is an origin-scoped lane that records Joseph's responsibility,
requires every machine and evidence gate, and states publicly that no
independent human reviewed the work. It must remain narrow enough that it
cannot be used to publish another person's contribution.

## Two distinct authorities

This reset deliberately separates a temporary governance condition from a
continuing asset-publication lane.

### Solo bootstrap decision authority

While Joseph is the sole qualified maintainer and external asset intake remains
closed, Joseph Nordqvist / `@bighippoman`, as founding project owner, may adopt
the policy, schema, profile, registry, security-boundary, and release-process
changes required to make the founder lane operational.

Every such change must:

1. use a standalone pull request from a signed commit;
2. pass every protected check applicable to its scope;
3. state that it has zero independent approvals;
4. include a compatibility, migration, or versioning decision; and
5. remain prospective and preserve immutable history.

This authority may strengthen or mechanically adapt the minimum security and
evidence controls in this record. It cannot reduce them without independent
approval. It is governance authority during solo bootstrap, not a waiver of a
failed gate.

Solo bootstrap decision authority ends when reviewer mode is activated with a
qualified second maintainer, external asset intake opens, or Joseph records a
signed decision ending it. Ending that authority does not end the founder
direct-publication lane below.

### Continuing founder direct-publication authority

The `first-party-founder-controlled` lane permits Joseph to register IDs for and
publish qualifying assets without a second human reviewer. It has no
asset-count limit and no calendar expiration. It remains available for future
qualifying assets while Joseph is NeuralStock's founding project owner,
including after reviewer mode or an independently reviewed external-contributor
lane exists.

This is publication authority for Joseph's own controlled work. It is not
independent provenance or quality review, and it does not extend to another
person's contribution.

## Eligible first-party asset lane

A candidate is eligible for `first-party-founder-controlled` only when all of the
following are true:

- controller and CC0 dedicator: `Joseph Nordqvist`;
- authenticated submission and publication identity: `@bighippoman`;
- rights authority: Joseph owns or controls every copyright and related right
  required to dedicate the disclosed work and inputs under CC0-1.0, with no
  external rights holder whose permission is missing;
- origin: direct-original Blender geometry, materials, or procedural work that
  Joseph originates and controls; each version records `manual_blender`,
  `procedural_blender`, or `tool_assisted_blender`, and all tool, automation,
  and generated-reference assistance is truthfully disclosed under the policy
  that applies to it;
- human contribution boundary: no other person supplied copyrightable artistic
  material or shared creative authorship; work with another human uses the
  external or a separately adopted collaborative lane even if Joseph later
  acquires broad rights;
- dependencies: no external human-created model, scan, kitbash, texture,
  material, reference contribution, or other copyrightable artistic input;
  disclosure, assignment, permission, or CC0 status does not convert another
  person's art into founder-origin work, which must use an external or import
  lane;
- permitted assistance: repository-controlled technical tooling and qualifying
  generated references may be used only under the separately adopted policy
  that applies to them, with assistance type and controlled inputs disclosed
  and hash-bound;
- namespace: the asset ID has a prior entry in the append-only,
  content-hashed first-party registration ledger;
- rights status: no unresolved source-origin, trademark, distinctive-design,
  personality, privacy, or dependency flag;
- assessment record: `founder_self_assessment`, with
  `independent_human_review: false`;
- source and candidate bytes: bound to signed attestations and immutable
  SHA-256 identities; and
- every applicable visual, schema, profile, glTF, collision, anchor, parameter,
  reproducibility, security, browser, and release gate: passing without waiver.

The registration ledger has no fixed cardinality. Joseph may reserve new IDs
individually or in bounded batches through a signed, protected change before
the corresponding candidate is evaluated. Registration reserves a namespace;
it is not asset acceptance, a quality claim, or permission to skip a gate. An
entry that follows the already-adopted ledger contract is an administrative
founder-lane action, not a registry-contract change, and does not require a
second human reviewer. Changing the ledger's schema or registration rules is a
separate governance change.

An asset-candidate or bounded-batch pull request cannot alter the policy,
schema, profile, workflow, registration rules, or verifier used to approve that
same candidate. Governing changes must reach protected `main` separately before
evaluation. Every asset in a batch receives its own versioned attestation,
inspection report, validation result, and publication record. There is no
manual `override`, `force`, or `skip` input for a failed asset verdict.

## Entrenched acceptance floor

Solo bootstrap decisions may establish new category profiles and strengthen or
mechanically adapt validation, but they cannot remove or make optional these
gate classes:

1. schema, identifier, and manifest integrity;
2. authenticated rights authority, CC0 assent, controlled-input provenance,
   and dependency disclosure;
3. immutable quarantine receipt and input/output hash binding;
4. isolated-build security and outer output validation;
5. deterministic or policy-defined reproducibility evidence;
6. glTF/runtime validity and real-browser load verification;
7. dimensions, transforms, geometry/material budgets, and applicable category
   constraints;
8. generated visual evidence and a recorded visual assessment;
9. anchor, collision, and parameter validation whenever those capabilities are
   declared;
10. immutable publication, registry/discovery consistency, and public
    assessment-mode disclosure; and
11. executable withdrawal and tombstone support.

A profile may add category-appropriate requirements above this floor. It cannot
contain an asset-ID-specific exception or be weakened solely to admit a
registered or pending candidate. Once used for publication, its version and
meaning are immutable. Any proposed relaxation requires a standalone public
redline, compatibility analysis, accepted-corpus regression results, negative
fixtures proving that known failures still fail, and independent approval.

## Preconditions for first use

Before the first non-Room-Zero asset is published, protected `main` must contain
and enforce:

1. a machine-readable publication-lane and assessment-decision contract;
2. an approved generated-reference policy if ImageGen or another generated
   artistic input is used;
3. immutable quarantine receipts and a generic single-asset and bounded-batch
   candidate runner;
4. category-specific runtime, source, visual, and interaction budgets;
5. the append-only, content-hashed asset-ID registration ledger;
6. a per-version founder rights/CC0 attestation bound to all controlled inputs;
7. public asset-page disclosure of first-party origin and non-independent
   assessment;
8. a founder-lane release checklist and lane-aware protected publication path;
   and
9. a solo-executable, auditable withdrawal and tombstone path.

The release path must continue to work after external intake opens. A future
reviewer-mode configuration may not impose an unintended second-person approval
on eligible founder assets; it must instead enforce external review through a
lane-aware required check or equivalently auditable control.

This decision authorizes those prerequisites to be built. It does not pretend
that they already exist and does not make a draft model publishable by itself.

## Required public disclosure

Every published founder-lane page and release record must state:

> Founder-controlled and founder-self-assessed. Joseph Nordqvist attests that he
> owns or controls the disclosed work and inputs and dedicates this asset under
> CC0-1.0. Automated NeuralStock gates passed. No independent human provenance
> or quality review was performed.

The permitted assurance label is **founder-attested, machine-validated**. The
lane must not display **independently reviewed** or **verified rights** unless a
later, actually independent process records that additional assurance without
replacing the original record.

## Non-bypassable boundaries

Founder authority cannot:

- rewrite or replace an immutable published contract, source, artifact, tag,
  release, attestation, or evidence object;
- suppress a failed check or unresolved rights state;
- publish an external contributor's asset or treat an external input as
  first-party;
- claim a spouse, collaborator, automation run, or founder self-assessment as
  independent human review;
- expose production credentials to untrusted asset, pull-request, or build
  code;
- retroactively relabel Room Zero or any later asset as independently reviewed;
- weaken withdrawal, security-response, provenance, or public-disclosure
  requirements to meet an asset-count target; or
- silently delete or substitute published bytes.

The following minimum build boundary is entrenched and cannot be reduced
without independent approval:

1. asset-supplied executable code, scripts, drivers, and network access are
   prohibited from trusted build execution;
2. production credentials never enter asset, pull-request, or Blender build
   execution;
3. the toolchain is pinned and the build runs non-root with read-only inputs,
   dropped privileges, finite resource limits, and no ambient host access; and
4. outputs receive outer validation before any protected publication job can
   access them.

The following evidence promises are also entrenched:

1. an exact per-version CC0 dedication tied to source and controlled-input
   hashes;
2. immutable published versions, contracts, content-addressed objects, release
   artifacts, and evidence;
3. public source `.blend`, GLB, provenance, inspection, receipt, and validation
   evidence for every accepted version;
4. no publication with an unresolved source-authority, dependency, trademark,
   design, personality, security, or quality state;
5. no publication after a failed technical, visual, provenance, security,
   reproducibility, or release gate;
6. public disclosure of the actual assessment mode;
7. external publication requires its own conflict-free review controls; and
8. withdrawal and tombstone records replace silent deletion or byte
   substitution.

## External contributions and future maintainers

External asset publication remains closed until its independent review lane is
implemented. When it opens, it continues to require distinct, conflict-free
contributor, provenance-review, and release roles. It does not inherit founder
authority.

A second maintainer may independently review a founder asset, but that is not a
publication prerequisite. The asset retains its original founder-assessment
record; any later review is an additional, timestamped record. Adding a second
maintainer or opening external intake does not terminate Joseph's continuing
lane.

## Duration, suspension, and withdrawal

There is no count-based or date-based sunset for the founder direct-publication
lane. Eligibility for a new candidate is suspended whenever Joseph no longer
controls the relevant work or inputs, the authenticated owner identity is in
doubt, a required gate or policy is unavailable, or a rights or security flag
is unresolved.

The lane may be changed or ended prospectively by a later signed governance
decision under the review rules then in force. A later decision cannot alter
the CC0 status, hashes, immutability, or recorded review mode of assets validly
published under this lane.

A credible rights or security report permits immediate founder-operated
withdrawal from discovery and hosted delivery. The action must preserve hashes,
create a public non-sensitive tombstone, and produce an immutable audit record.
An independent follow-up audit is required when a qualified independent
responder exists; lack of one never prevents urgent containment.

## Alternatives considered

- **Wait for a second maintainer before any first-party expansion.** This offers
  independent approval but indefinitely blocks the model-creation phase.
- **Treat an affiliated or family member as independent.** Rejected because a
  close personal relationship is a review conflict and would make the trust
  claim misleading.
- **Cap the lane at the Foundation 50 or a calendar date.** Rejected because it
  would recreate the same deadlock immediately after the first collection and
  would not support a continuously growing public catalog.
- **Create an unrestricted owner bypass.** Rejected because it could waive
  technical gates, blur external and first-party work, or silently replace
  governance promises.
- **Use a continuing, disclosed, authorship-scoped founder lane.** Chosen
  because it supports regular first-party publication while keeping the lack of
  independent review visible and every technical and evidence gate fail-closed.

## Compatibility and historical record

This reset is prospective. It does not modify the v0.1.0 release record,
historical approvals, published schemas or profiles, asset bytes, or CC0
dedications. New schema or profile semantics require new immutable versions.

The Foundation 50 is a production roadmap and first collection, not a
governance ceiling. Successful assets become ordinary public registry entries
under the same immutable artifact and discovery contract as later assets.

The canonical governance and GitHub operations documents incorporate this
decision. Historical release records continue to describe the controls that
existed when those releases were made.

## Limits of enforcement

Joseph currently controls the GitHub organization and production
infrastructure. No repository policy can provide cryptographic independence
from a deliberately malicious project owner or an attacker who controls all of
that owner's accounts. The enforceable promise during solo operation is a
documented path that is fail-closed, tamper-evident, signed, and publicly
auditable. Independent insider resistance begins only when a genuinely
separate, conflict-free controller is appointed.
