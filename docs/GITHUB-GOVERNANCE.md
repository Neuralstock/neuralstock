# GitHub repository setup

The canonical repository is
`https://github.com/Neuralstock/neuralstock`, owned by the `Neuralstock`
organization. Transferring the empty bootstrap repository, pushing the initial
history, changing account settings, and provisioning reviewers are intentional
operator actions; repository files alone cannot perform them. The transfer must
retain GitHub's redirect from the temporary personal-account location.

## Initial setup

1. Transfer the empty public bootstrap repository to the `Neuralstock`
   organization without changing its name, then verify the canonical URL and
   the redirect from its temporary personal-account URL.
2. Push a signed initial commit to `main`.
3. Enable Issues, private vulnerability reporting, the dependency graph,
   Dependabot alerts, and secret scanning with push protection.
4. Run every required workflow once on `main` so all named check contexts exist.
5. While Joseph Nordqvist is the only maintainer, inspect the bootstrap plan:

   ```sh
   tools/configure-github-protection.sh \
     Neuralstock/neuralstock \
     --solo-maintainer
   ```

6. Apply that exact plan only if the solo-maintainer limitation below is
   accepted and recorded:

   ```sh
   tools/configure-github-protection.sh \
     Neuralstock/neuralstock \
     --solo-maintainer \
     --apply
   ```

The script is dry-run-only without `--apply` and is pinned to the canonical
public, organization-owned repository with default branch `main`. It verifies
that `@bighippoman` retains administrator permission and reconciles
squash-only merge settings; pull-request-only, signed, linear `main`; five
required checks; an active `v*` tag ruleset; and the four protected environment
ref policies. It refuses duplicate named rulesets, unexpected environment ref
patterns, the initial maintainer used as the second reviewer, or reviewer mode
before that reviewer appears in `.github/CODEOWNERS`. It never deletes an
unexpected rule.

GitHub has no transaction spanning repository, ruleset, and environment APIs.
An API failure can therefore leave a safe partial application; correct the
reported condition and rerun the same command. The operations are idempotent.

### Solo-maintainer limitation and transition

GitHub prevents a deployment initiator from self-approving when
`prevent_self_review` is enabled. With only Joseph available, requiring a
reviewer and preventing self-review would deadlock every release. Therefore
`--solo-maintainer` requires pull requests and checks but zero human approvals,
and configures no required deployment reviewer. That is a bootstrap exception,
not independent review. It permits the first-party Room Zero rollout only;
external contributor publication remains closed and no audit record may claim
a second-person approval.

As soon as a second qualified operator exists, add their exact `@LOGIN` to the
global and protected-path entries in `.github/CODEOWNERS`, then inspect and
apply reviewer mode:

```sh
tools/configure-github-protection.sh \
  Neuralstock/neuralstock \
  --reviewer LOGIN

tools/configure-github-protection.sh \
  Neuralstock/neuralstock \
  --reviewer LOGIN \
  --apply
```

Reviewer mode requires one approval, code-owner review, dismissal of stale
reviews, approval after the latest push, and environment approval by either the
initial maintainer or second reviewer with self-review prevented. Only one
eligible reviewer is required by GitHub, so project policy still requires two
distinct people for external asset publication.

GitHub documents tag restrictions as repository
[rulesets](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/about-rulesets).
The environment ref filters below are a second boundary, not a substitute for
protecting tag creation and movement.

The GitHub deployment-policy list response may omit whether an existing pattern
is a branch or tag rule. The reconciler sends the explicit type when creating a
rule but cannot prove that type on every later readback. Inspect the four
environment policies in the GitHub UI after first application. The release and
package workflows independently reject non-tag refs; the production workflow
independently accepts only branch `main` or tag `v<requested-version>`.

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

The reconciler creates or updates four GitHub environments. In reviewer mode,
each requires a non-initiating approval; in solo mode, each intentionally has no
required reviewer for the bootstrap reason above.

### `release`

- Require a non-initiating release-operator reviewer in reviewer mode.
- Select only tags matching `v*` as permitted deployment refs.
- Do not add Cloudflare or package-registry credentials.
- The only write granted by the release job is `contents: write` for the
  explicitly requested GitHub Release.

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

After applying either mode, retain the script's readback and independently
audit the controls with an administrator-authenticated GitHub CLI session:

```sh
gh api repos/Neuralstock/neuralstock/branches/main/protection
gh api repos/Neuralstock/neuralstock/rulesets \
  --jq '.[] | select(.name == "neuralstock-release-tags")'
gh api repos/Neuralstock/neuralstock/environments \
  --jq '.environments[] | [.name, .deployment_branch_policy]'
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
signed-tag GitHub Release. Phase `publish` downloads that asset, verifies the
operator-supplied SHA-256, parses all exact rules, and binds the evidence's plan
hash and revision to the candidate before any write. A phase-A green status or
a caller-supplied hash alone is not lock evidence.

## Workflow responsibilities

| Workflow | Trigger | Writes external state |
| --- | --- | --- |
| `CI` | Pull request and `main` | No |
| `Security` | Pull request, `main`, schedule | Security analysis results only |
| `Package candidate` | Tag or manual | GitHub attestation and temporary artifact; no npm/PyPI publication |
| `Publish packages` | Manual on a protected tag | OIDC publication to selected npm/PyPI registries |
| `Release candidate` | Manual | Attestation and temporary artifact; optional protected GitHub Release |
| `Production deploy` | Manual, protected environment | Phase A: immutable R2 objects only; Phase B: aliases, canonical host rule, and Cloudflare Pages after verified lock evidence |
| `Production health` | Schedule or manual | No |

The release workflow receives no Cloudflare credential. The deploy workflow
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

Configure npm with those exact case-sensitive values and allow `npm publish`,
not staged publication, for v0.1. The workflow requires Node 24 and npm 11.5.1
or newer. After trusted publishing succeeds, set the package's publishing
access to require two-factor authentication and disallow tokens.

Configure a [PyPI pending publisher](https://docs.pypi.org/trusted-publishers/creating-a-project-through-oidc/)
with project name `neuralstock` and the
exact identity above. A pending publisher can create the project on its first
OIDC publication, so no PyPI API token is required. If the project already
exists under the maintainer's control, configure the same identity in the
project's Publishing settings instead.

As of 2026-08-01, unauthenticated registry checks returned not found for both
names; that indicates no public release, not ownership or reservation. The npm
scope and first package release must therefore be bootstrapped interactively by
Joseph Nordqvist if npm will not allow a trusted publisher before the package
exists. Publish the already attested archive from a protected tag with account
2FA, immediately configure the trusted publisher, and remove any temporary
automation token. Never copy a bootstrap token into GitHub. PyPI should use its
pending-publisher flow instead of a manual upload.

For every version after bootstrap:

1. run `Package candidate` on the protected `v<version>` tag;
2. independently verify its checksums and GitHub attestations;
3. dispatch `Publish packages` on that same tag with the candidate run ID and
   exact version;
4. in reviewer mode, approve the `npm` and `pypi` environments independently
   (or record the first-party solo-bootstrap exception); and
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
