# GitHub repository governance

The canonical repository is
`https://github.com/Neuralstock/neuralstock`, owned by the `Neuralstock`
organization. The bootstrap repository was transferred before release history
was published, and GitHub retains the redirect from the temporary
personal-account location.

## Current v0.1.0 control state

The public repository uses pull-request-only, signed, linear `main` history,
squash-only merges, five required checks, an active `v*` tag ruleset, and the
protected `release`, `production`, `npm`, and `pypi` environments. Repository
release immutability is enabled. The signed `v0.1.0` tag targets
`6a0d8bb5696a24792c606128b016d2fcf3fad6ff`, and its exact six-asset GitHub
Release is public and immutable.

The controls were applied in the explicitly recorded solo-maintainer mode.
That was sufficient for the first-party Room Zero release. Prospectively, the
signed founder reset establishes a continuing lane for qualifying
founder-controlled work after the machine-readable contract and publication
prerequisites are enforced. It is not independent approval and does not open
external contributor publication. The lane is origin-scoped rather than tied
to solo-maintainer mode and may continue after reviewer mode exists.

## Configuration and reconciliation

The deployed configuration was established with the following procedure. The
protection commands remain its idempotent reconciliation path:

1. The empty public bootstrap repository was transferred to the `Neuralstock`
   organization without a rename; both the canonical URL and redirect from its
   temporary personal-account URL were verified.
2. Signed initial history was pushed to `main`.
3. Issues, private vulnerability reporting, the dependency graph, Dependabot
   alerts, and secret scanning with push protection were enabled.
4. Every required workflow ran on `main`, establishing all named check
   contexts.
5. While Joseph Nordqvist remains the only maintainer, inspect the reconciled
   solo-bootstrap plan with:

   ```sh
   tools/configure-github-protection.sh \
     Neuralstock/neuralstock \
     --solo-maintainer
   ```

6. Reapply that exact plan only while the recorded solo-maintainer limitation
   below remains accepted:

   ```sh
   tools/configure-github-protection.sh \
     Neuralstock/neuralstock \
     --solo-maintainer \
     --apply
   ```

The script is dry-run-only without `--apply` and is pinned to the canonical
public, organization-owned repository with default branch `main`. It verifies
that `@bighippoman` retains administrator permission and reconciles
squash-only merge settings; repository release immutability; pull-request-only,
signed, linear `main`; five required checks; an active `v*` tag ruleset; and the
four protected environment ref policies. It reads the immutable-release setting
back after enabling it. It refuses duplicate named rulesets, unexpected
environment ref patterns, the initial maintainer used as the second reviewer,
or reviewer mode before that reviewer appears in `.github/CODEOWNERS`. It never
deletes an unexpected rule.

GitHub has no transaction spanning repository, ruleset, and environment APIs.
An API failure can therefore leave a safe partial application; correct the
reported condition and rerun the same command. The operations are idempotent.

### Solo-maintainer controls and continuing founder lane

GitHub prevents a deployment initiator from self-approving when
`prevent_self_review` is enabled. With only Joseph available, requiring a
reviewer and preventing self-review would deadlock every release. Therefore
`--solo-maintainer` requires pull requests and checks but zero human approvals,
and configures no required deployment reviewer. That is a bootstrap exception,
not independent review. Room Zero used the initial exception. The continuing
asset lane is governed by
[`FOUNDER-BOOTSTRAP-GOVERNANCE-RESET.md`](FOUNDER-BOOTSTRAP-GOVERNANCE-RESET.md)
and permits only candidates that pass the enforced
`first-party-founder-controlled` lane. External contributor publication remains
closed and no audit record may claim a second-person approval.

The reset alone is not a publication gate. Until protected `main` enforces the
lane verdict, generated-reference policy when applicable, quarantine receipt,
category profile, append-only ID registration, founder attestation, public
assessment-mode disclosure, founder release checklist, and auditable withdrawal
path, no new non-Room-Zero asset may use the lane.

The current reconciler's `--reviewer` mode is a legacy global-review plan: it
requires a human approval on every pull request and protected deployment. That
is useful for an all-reviewed repository but would also require a second person
on founder assets. It is therefore not the final dual-lane configuration.

When a second qualified operator exists, add their exact `@LOGIN` to the global
and protected-path entries in `.github/CODEOWNERS`. Before using that event to
open external intake, first land a lane-aware required check and protected
publication design. The following commands may then be used to inspect the
current legacy plan, but must not be applied as the final configuration while
the continuing founder lane is expected to operate without a second approval:

```sh
tools/configure-github-protection.sh \
  Neuralstock/neuralstock \
  --reviewer LOGIN

tools/configure-github-protection.sh \
  Neuralstock/neuralstock \
  --reviewer LOGIN \
  --apply
```

That legacy reviewer mode requires one approval, code-owner review, dismissal
of stale reviews, approval after the latest push, and environment approval by
either the initial maintainer or second reviewer with self-review prevented.
Only one eligible reviewer is required by GitHub, so project policy still
requires two distinct people for external asset publication.

The intended dual-lane mode keeps signatures, pull requests, immutable history,
and required checks global. A protected governance check evaluates the lane and
requires external review records only for external candidates. Protected asset
publication similarly separates an owner-operated founder path from the
non-initiating approval required for external assets. Policy and software
changes retain the review rule appropriate to their change class.

GitHub documents tag restrictions as repository
[rulesets](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/about-rulesets).
The environment ref filters below are a second boundary, not a substitute for
protecting tag creation and movement.

GitHub's [immutable release guidance](https://docs.github.com/en/code-security/how-tos/secure-your-supply-chain/establish-provenance-and-integrity/prevent-release-changes)
states that the setting affects future publications, and its recommended flow
is draft, attach every asset, then publish. NeuralStock therefore enables and
reads back the repository setting before creating the first draft and never
adds, replaces, or deletes an asset after finalization.

The GitHub deployment-policy list response may omit whether an existing pattern
is a branch or tag rule. The reconciler sends the explicit type when creating a
rule but cannot prove that type on every later readback. Inspect the four
environment policies in the GitHub UI after first application. Candidate and
package workflows independently reject non-tag refs. The protected finalizer
and production workflow independently accept only the exact current branch
`main` or tag `v<requested-version>`, while binding release content and
attestations to the separately supplied, signed tag commit.

## Required checks

- `Contract and clients`
- `Pinned Blender smoke test`
- `Dependency review`
- `Analyze (javascript-typescript)`
- `Analyze (python)`

CodeQL and dependency review require the corresponding GitHub security features.
They are available for a public repository; if the repository starts private,
do not apply those required contexts until the account has the required GitHub
Advanced Security capability.

## Protected environments

The reconciler currently creates or updates four GitHub environments. In its
legacy reviewer mode, each requires a non-initiating approval; in solo mode,
each intentionally has no required reviewer for the bootstrap reason above.
The founder asset path required before first use must preserve equally strict
ref, signature, candidate, and credential controls without falsely recording a
human approval.

### `release`

- Require a non-initiating release-operator reviewer in reviewer mode.
- Select only branch `main` and tags matching `v*` as permitted deployment
  refs. The finalizer accepts `main` only when its checked-out commit is the
  freshly read protected-main head, and still requires the exact signed-tag
  commit as an explicit input.
- Do not add Cloudflare or package-registry credentials.
- Store `NEURALSTOCK_GITHUB_ADMIN_READ_TOKEN` only in this environment. It must
  be a fine-grained token restricted to `Neuralstock/neuralstock` with read-only
  repository Administration permission and no write permission. The protected
  finalizer uses it only to fail closed on the repository immutable-releases
  setting before publication, because `GITHUB_TOKEN` has no Administration
  permission.
- Release creation and finalization use the ephemeral `GITHUB_TOKEN`; their only
  write is `contents: write` for the explicitly requested draft or publication.

### `production`

- Require a reviewer who did not initiate the deployment in reviewer mode.
- Select only branch `main` and tags matching `v*` as permitted deployment
  refs.
- Store only the credentials listed below.
- Disable administrator bypass once a second operator exists.

### `npm`

- Require a non-initiating release-operator reviewer in reviewer mode.
- Select only tags matching `v*` as permitted deployment refs.
- Add no secrets or variables. The job receives only job-scoped
  `id-token: write` and publishes through npm trusted publishing.

### `pypi`

- Apply the same reviewer and protected-tag restrictions as `npm`.
- Add no secrets or variables. The PyPA publishing action exchanges the
  job-scoped OIDC identity for a short-lived PyPI credential.

Use GitHub's selected branch/tag policy rather than a similarly named branch;
branch and tag patterns are configured separately.

The REST environment API used by the reconciler does not expose the UI control
for administrator bypass. Once a second operator exists, disable administrator
bypass for all four environments in the GitHub UI and record that check in the
release log. Do not enable this in solo mode: it does not manufacture an
independent reviewer and can deadlock the only operator.

Before any reviewer configuration is used to open external asset intake,
implement the lane-aware required check and protected publication paths above.
They must require the external lane's distinct human roles without requiring a
second-person approval for an eligible founder asset. A global approval rule
that accidentally blocks the continuing founder lane is not the final
dual-lane configuration.

After applying either mode, retain the script's readback and independently
audit the controls with an administrator-authenticated GitHub CLI session:

```sh
gh api repos/Neuralstock/neuralstock/branches/main/protection
gh api repos/Neuralstock/neuralstock/rulesets \
  --jq '.[] | select(.name == "neuralstock-release-tags")'
gh api repos/Neuralstock/neuralstock/environments \
  --jq '.environments[] | [.name, .deployment_branch_policy]'
gh api \
  -H 'X-GitHub-Api-Version: 2026-03-10' \
  repos/Neuralstock/neuralstock/immutable-releases
```

Secrets:

- `CLOUDFLARE_ACCOUNT_ID`
- `CLOUDFLARE_API_TOKEN` scoped to the NeuralStock Pages project
- `CLOUDFLARE_REDIRECT_API_TOKEN` scoped to `neuralstock.ai` with only
  `Zone > Zone > Read` and `Zone > Single Redirect > Edit` (shown as
  `Dynamic URL Redirects Write` by the API)
- `NEURALSTOCK_R2_ACCESS_KEY_ID` scoped to the publication bucket
- `NEURALSTOCK_R2_SECRET_ACCESS_KEY`
- `NEURALSTOCK_R2_ENDPOINT_URL`

Variables:

- `NEURALSTOCK_R2_BUCKET=neuralstock-public`
- `NEURALSTOCK_PAGES_PROJECT=neuralstock`
- `NEURALSTOCK_CLOUDFLARE_ZONE_ID=<neuralstock.ai zone ID>`

Store all of these as protected `production` environment secrets or variables,
not repository-wide configuration. Never add them to a pull-request workflow,
build artifact, log, or Blender container. The zone ID is not confidential, but
environment scoping keeps the production workflow's complete configuration in
one reviewed boundary.

Do not add an R2 bucket-configuration token to any GitHub scope. Cloudflare's
bucket-scoped S3 credentials cover object publication but cannot create or read
bucket-lock rules; the currently available configuration-write capability is
account-wide. Release retention therefore remains a manual gate between the two
deployment phases using local Wrangler OAuth and
`tools/manage-r2-release-lock.sh`. For the fresh v0.2 namespaces, `Production
deploy` phase `immutable-bootstrap` stages
all immutable content without aliases or Pages. The local gate directly verifies
that graph and creates the exact v0.2 schema, profile, and revision-snapshot
locks. Its independent JSON readback is uploaded once, without `--clobber`, as
the deterministic asset `neuralstock-r2-release-lock-<revision>.json` on the
signed-tag draft release. The protected `Finalize release` workflow verifies
the exact six-asset set, candidate checksums and identity, build attestations,
lock evidence, and immutable-releases setting before publishing the draft once.
It then verifies `immutable: true` and GitHub's release attestation. Only after
that does phase `publish` download the asset, verify the operator-supplied
SHA-256 and immutable release attestation, parse all exact rules, and bind the
evidence's plan hash and revision to the candidate before any write. A phase-A
green status or a caller-supplied hash alone is not lock evidence.

## Workflow responsibilities

| Workflow | Trigger | Writes external state |
| --- | --- | --- |
| `CI` | Pull request and `main` | No |
| `Security` | Pull request, `main`, schedule | Security analysis results only |
| `Package candidate` | Tag or manual | GitHub attestation and temporary artifact; no npm/PyPI publication |
| `Publish packages` | Manual on a protected tag | OIDC publication to selected npm/PyPI registries |
| `Release candidate` | Manual on a protected tag | Attestation, temporary artifact, and exact five-asset draft GitHub Release |
| `Finalize release` | Manual on exact current protected `main` or the protected tag, in the protected environment | Binds the controller to protected main and all release content to the supplied signed-tag commit, then verifies the candidate and R2 evidence and publishes the draft once as an immutable six-asset release |
| `Production deploy` | Manual, protected environment | Phase A: immutable R2 objects only; Phase B: aliases, canonical host rule, and Cloudflare Pages only after the immutable GitHub Release verifies |
| `Production health` | Schedule or manual | No |

The release and finalizer workflows receive no Cloudflare credential. The deploy workflow
downloads a candidate from a specific release run and rejects it unless its
source commit, version, checksums, and registry revision match the operator's
request.

Both `assets.neuralstock.ai` and `schemas.neuralstock.ai` are R2 custom domains
on `neuralstock-public`. The production workflow reproduces the candidate plan,
publishes the versioned schemas and profile as immutable R2 keys before either
mutable registry alias, and byte-compares the public contract afterward. It
also reconciles one zone-level Single Redirect with stable ref
`neuralstock_www_to_apex`; a Pages `_redirects` file is not permitted to claim
host-level canonicalization.

## Package trusted publishers

The only authorized package-publishing identity is:

| Registry project | GitHub owner/repository | Workflow | Environment | Action |
| --- | --- | --- | --- | --- |
| npm `@neuralstock/client` | `Neuralstock/neuralstock` | `publish-packages.yml` | `npm` | `npm publish` |
| PyPI `neuralstock` | `Neuralstock/neuralstock` | `publish-packages.yml` | `pypi` | Upload release |

These settings follow the registries' current
[npm trusted-publisher](https://docs.npmjs.com/trusted-publishers/) and
[PyPI trusted-publisher](https://docs.pypi.org/trusted-publishers/) contracts.

The npm publisher uses those exact case-sensitive values and direct
`npm publish`; the workflow requires Node 24 and npm 11.5.1 or newer. The npm
organization enforces 2FA, and `@neuralstock/client` requires 2FA for
publication. Its initial `0.1.0` upload was the one necessary interactive
bootstrap from the exact attested archive, SHA-256
`c18fcf3f0b7f22d15a888d9c5cb0a42bfb350fa0f8b0592d33fb1984b5409ace`.
Trusted publishing for `Neuralstock/neuralstock`, workflow
`publish-packages.yml`, environment `npm`, was configured immediately after
that namespace existed; later versions use the protected OIDC workflow.

PyPI project `neuralstock` was created by its pending trusted publisher and
published `0.1.0` through GitHub OIDC. No PyPI API token was used. Clean
Python 3.12 and npm consumer projects installed and imported the exact public
versions successfully. No long-lived npm or PyPI publishing credential is
stored in GitHub.

For every version after bootstrap:

1. run `Package candidate` on the protected `v<version>` tag;
2. independently verify its checksums and GitHub attestations;
3. dispatch `Publish packages` on that same tag with the candidate run ID and
   exact version;
4. apply the package release approval mode actually configured and record
   whether the operation was independent or owner-operated; and
5. install the exact published versions from clean temporary projects before
   recording the release complete.

The publication workflow rejects a candidate from another workflow, commit,
tag, version, repository URL, or package identity. Only its two small publisher
jobs receive OIDC permission; no long-lived npm or PyPI credential exists.

## Trusted asset-workflow boundary

The current `CI` workflow is suitable for first-party repository development:
it runs pull-request code on an ephemeral GitHub-hosted runner with a read-only
token and no production secret. It is not the final external asset-ingestion
design. An external asset job must load schemas and Blender tooling by protected
release digest from `main`, accept only the contributor's data and authored
manifests, and publish nothing. A separate protected job re-verifies the merge
commit before publication.

Do not use `pull_request_target` to build contributor content, and do not move
untrusted Blender execution onto a persistent self-hosted runner.
