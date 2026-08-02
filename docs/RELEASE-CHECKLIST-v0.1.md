# NeuralStock v0.1 release checklist

Use this checklist for a Room Zero v0.1 release or exact rebuild. It complements
`docs/RELEASE.md`; it does not replace the executable validation gates.

The first-party bootstrap may run under the recorded solo-maintainer exception
in `GOVERNANCE.md`. Where this checklist calls for an independent operator, the
release record must say that independent review was unavailable and record a
separate clean verification by the owner; it must not claim two-person review.
No external contributor asset may use that exception.

The checked items below record the initial `v0.1.0` publication. Joseph
Nordqvist was the sole maintainer and release operator, so every owner-performed
clean verification is recorded as a solo-bootstrap check, not independent human
review. A later exact rebuild must use a fresh copy of this checklist.

## 1. Authority and source freeze

- [x] Release commit is reviewed, signed, pushed, and protected.
- [x] Working tree contains no unexplained or untracked release input.
- [x] Version matches the Python and npm package metadata and intended tag.
- [x] Every active contract-bearing source uses the owned canonical v0.2 prefix
      `https://schemas.neuralstock.ai/v0.2/`; no draft unowned-domain reference
      remains.
- [x] Every catalog entry has an accepted direct-dedicator CC0 attestation,
      exact source hash, evidence hash, and no unresolved rights-review state.
- [x] The Room Zero author attestation still identifies Joseph Nordqvist and the
      exact 15 assets at asset version 1.0.1.
- [x] Historical 1.0.0 attestation bytes still hash to
      `e687b259dabc8080a610dd2de11be347e444d8f4a7a9a3df8548d92d9e77d58f`
      and remain at their original indefinitely locked content-addressed object.
- [x] The distinct 1.0.1 migration attestation hashes to
      `95531e49b5da7616fa769cdbd7d97a84e51beb8798d5180fb3abfbb2a074c32e`,
      and every 1.0.1 provenance record references that evidence rather than
      rewriting the historical object.
- [x] Every 1.0.1 dedication names `NeuralStock Open Asset Engine`, binds
      `https://neuralstock.ai/` and `https://neuralstock.ai/#mission`, and the
      migration attestation explicitly preserves the historical 1.0.0 bytes.
- [x] `catalog/room-zero-v1.0.1-source-migration.json` matches all 15 accepted
      `.blend` hashes and records byte-for-byte reuse of the locked 1.0.0 inputs.
- [x] No generated GLB, preview, report, registry, or receipt was edited by hand.

## 2. GitHub rollout controls

- [x] `main` requires pull requests, the five named checks, signed commits,
      linear history, conversation resolution, and blocks force-push/deletion.
- [x] The active `neuralstock-release-tags` ruleset covers `refs/tags/v*` and
      restricts creation, movement, and deletion to `@bighippoman`.
- [x] `release` and `production` allow only branch `main` and tag pattern `v*`;
      `npm` and `pypi` allow only tag pattern `v*`.
- [x] The environment policy types were inspected in the GitHub UI because the
      REST list response may omit whether an existing pattern is a branch or tag.
- [x] The applied protection mode and exact reconciler command are in the release
      record. Reviewer mode is required for external assets; any first-party
      solo-mode use records the bootstrap exception explicitly.
- [x] Repository release immutability is enabled and the reconciler's readback
      reports `enabled: true` before the draft is created.
- [x] The protected `release` environment contains only the narrowly scoped
      `NEURALSTOCK_GITHUB_ADMIN_READ_TOKEN` needed to read that setting; release
      writes continue to use the ephemeral `GITHUB_TOKEN`.

## 3. Locked checks

- [x] `uv sync --frozen --extra dev` succeeds.
- [x] `pnpm install --frozen-lockfile` succeeds.
- [x] Python format, lint, schema, unit, and integration tests pass.
- [x] TypeScript type checks, unit tests, package dry-run, and build pass.
- [x] Pinned Blender image reproduces its locked manifest and config digests.
- [x] Two independent accepted-source builds are byte-identical under the
      documented v0.1 reproducibility rules.
- [x] All 15 GLBs report zero Khronos errors and zero warnings.
- [x] Real-release Three.js and desktop/narrow browser checks pass.

## 4. Candidate construction

- [x] Run `Release candidate` on the intended commit/tag with reviewed UTC build
      and publication timestamps.
- [x] `tools/release-room-zero.sh` completes without an override of a failed gate.
- [x] `tools/package-release-candidate.sh` creates a deterministic archive,
      R2 plan, image metadata, release metadata, and `SHA256SUMS`.
- [x] `tools/verify-release-candidate.sh` validates checksums, archive paths,
      release graph, immutable schema/profile/license plan, complete embedded
      MIT notices, version, and registry revision.
- [x] Record source commit, release workflow run ID, candidate SHA-256, registry
      revision, and entry/artifact counts.

## 5. Attestation and draft GitHub Release

- [x] GitHub build-provenance attestation exists for every candidate subject.
- [x] In reviewer mode, a second operator downloads the workflow artifact and
      verifies it with the command below; in solo bootstrap, the owner repeats
      it from a clean
      checkout and records that it was not independent:

  ```sh
  gh attestation verify <candidate-file> --repo Neuralstock/neuralstock
  ```

- [x] Candidate checksums verify outside the producing job.
- [x] The workflow ref is the existing protected tag `v<version>`, the protected
      `release` environment is approved, and the resulting release is still a
      draft with exactly the five attested candidate assets.
- [x] No npm, PyPI, OCI, R2, Pages, or published GitHub Release is inferred from
      creating the candidate draft.

Release-candidate run `30727857692` produced five attested subjects at tagged
commit `6a0d8bb5696a24792c606128b016d2fcf3fad6ff`. Joseph repeated checksum and
attestation verification from the downloaded candidate; this was a clean
owner-operated verification, not a second-person review.

## 6. Package publication

- [x] `@neuralstock/client` and `neuralstock` names are still controlled by the
      intended maintainer; a not-found response alone is not proof of control.
- [x] The package candidate ran on the protected `v<version>` tag and its run
      ID, commit, checksums, identities, and attestations verify independently.
- [x] npm trusts only `Neuralstock/neuralstock`, `publish-packages.yml`,
      environment `npm`, and action `npm publish`.
- [x] PyPI trusts only `Neuralstock/neuralstock`, `publish-packages.yml`, and
      environment `pypi` for project `neuralstock`.
- [x] GitHub environments `npm` and `pypi` require a non-initiating release
      operator in reviewer mode and contain no registry token. Any solo
      first-party bootstrap is identified as the documented exception.
- [x] If npm needs a one-time namespace bootstrap, Joseph publishes the exact
      attested archive interactively with 2FA, configures trusted publishing,
      and removes any temporary token without putting it in GitHub.
- [x] `Publish packages` is dispatched from the same tag and candidate run;
      each selected protected environment runs under the recorded reviewer or
      first-party solo-bootstrap mode.
- [x] Clean temporary projects install and smoke-test exact versions
      `@neuralstock/client@<version>` and `neuralstock==<version>`.

Package-candidate run `30727842644` attested all four subjects. PyPI publication
used the protected OIDC publisher in run `30727997525`. The first npm upload was
the exact attested archive, performed interactively by Joseph with 2FA and
`--provenance=false`; npm trusted publishing and publish MFA were configured
immediately afterward. No independent package approver is claimed.

## 7. Production asset publication

- [x] Start `Production deploy` phase `immutable-bootstrap` from the exact
      candidate source commit; enter the recorded run ID, version, and revision.
- [x] In reviewer mode, a release operator who did not initiate the deployment
      approves production. Any solo first-party bootstrap is identified as the
      documented exception and does not claim independent approval.
- [x] Both `assets.neuralstock.ai` and `schemas.neuralstock.ai` are active
      custom domains on `neuralstock-public`.
- [x] Phase A accepts only all-twelve-absent or all-twelve-byte-identical state
      for the fresh v0.2 contracts, stages every immutable plan item with
      `--immutable-only`, reports no alias updates, and proves both aliases are
      byte-identical before and after staging.
- [x] Every v0.2 schema, the v0.2 `web-v1` profile, and both adjacent `LICENSE`
      companions are byte-identical through the public schema origin after
      Phase A; the immutable-bootstrap workflow evidence artifact is retained.
- [x] Signed tag `v0.1.0` already has its exact five-asset draft release; that
      draft is the only accepted destination for the deterministic lock evidence.
- [x] R2 scoped publication credentials and Pages token are present only in the
      protected environment.
- [x] A separate `CLOUDFLARE_REDIRECT_API_TOKEN` has only `Zone > Zone > Read`
      and `Zone > Single Redirect > Edit` (`Dynamic URL Redirects Write` in the
      API) for `neuralstock.ai`; the protected environment also holds the exact
      `NEURALSTOCK_CLOUDFLARE_ZONE_ID` variable.
- [x] The zone-level rule with ref `neuralstock_www_to_apex` is enabled, returns
      301, preserves path and query, and has passed API readback. The Pages
      `_redirects` file contains no unsupported domain-level rule.
- [x] Do not dispatch phase `publish` until Section 8 is complete and its
      independent JSON readback is a deterministic draft asset and the protected
      finalizer has made that exact six-asset release immutable.

Successful immutable-bootstrap run `30729693309` staged 227 immutable plan
items, updated no alias, preserved both historical alias byte streams, and
retained artifact `8827536775`. Joseph approved the protected production gate
under the solo-maintainer exception; no independent production approver is
claimed. Protected Phase B retry `30730929891` completed successfully from
protected-main commit `181e0d661e0e9f6d662e1bc18ecdc37dc38d9cff`.

- [x] Phase `publish` downloads that asset, verifies its caller-supplied SHA-256,
      verifies the GitHub release and asset attestations, binds its revision and
      release-plan SHA-256 to the candidate, and validates all eight exact
      enabled-indefinite baseline/target rules before any write.
- [x] Immutable objects and version manifests are reverified before aliases.
- [x] `registry.json` updates before `snapshots/latest.json`, with the latter last.
- [x] Live registry revision equals the approved revision.
- [x] `registry.json`, `snapshots/latest.json`, and the immutable
      `snapshots/<revision>/registry.json` are byte-identical, and the semantic
      registry revision recomputes to the approved SHA-256.
- [x] The exact checked-in machine-discovery document and sitemap are live with
      the intended content types and CORS/cache headers; the sitemap has exactly
      one stable route per registry entry and a registry-derived route returns
      the application shell.
- [x] Site, exact `www` redirect, full manifest/GLB/Blender source hashes and byte
      counts, GLB range content, and browser CORS behavior are verified by
      `sh tools/verify-production.sh <revision> dist/production-release`.
- [x] `registry.json` and `snapshots/latest.json` return
      `public, max-age=60, must-revalidate`; the zone Browser Cache TTL remains
      **Respect Existing Headers**.
- [x] Content-addressed objects, asset-version manifests, and revision snapshots
      return `public, max-age=31536000, immutable` and support byte ranges where
      applicable.

## 8. Retention protection

Historical indefinite locks must remain present and retain their original names:

- [x] `immutable-objects` on `objects/sha256/`.
- [x] `immutable-manifests` on `assets/`.
- [x] `schema-v0.1` on `v0.1/`.
- [x] `profile-v0.1` on `profiles/v0.1/`.
- [x] `room-zero-snapshot` on
      `snapshots/a3e851194d092bf1a06452a62ae98ba8687462ea0cbca668a9b9cc2385768523/`.
- [x] `registry.json` and `snapshots/latest.json` remain outside indefinite locks.
- [x] `schema-v0.2` is enabled indefinitely on exactly `v0.2/`.
- [x] `profile-v0.2` is enabled indefinitely on exactly `profiles/v0.2/`.
- [x] `snapshot-<first-16-revision-hex>` is enabled indefinitely on exactly
      `snapshots/<revision>/`.
- [x] No R2 bucket-configuration token is stored in GitHub; the account-wide
      configuration-write permission is not accepted for release automation.
- [x] From the protected release checkout, an interactively authenticated
      operator runs `tools/manage-r2-release-lock.sh <revision> --release-root
      <release-root> --apply` only after Phase A stages the complete immutable
      graph and its strict public v0.2 contract check passes.
- [x] The helper preserves every baseline lock, rejects mutable-alias coverage,
      reproduces the candidate plan, directly byte-verifies every immutable R2
      item, recomputes the snapshot revision, and reads back all three new rules.
- [x] For newly created rules, all 12 contract objects and the snapshot are
      byte-identical before and after locking; their keys, SHA-256 values, and
      byte counts are present in the JSON evidence.
- [x] A fresh check-only invocation reports `mode: already-present`; its JSON
      and the apply JSON are hashed and linked from the release record with the
      operator and UTC timestamp.
- [x] Copy the check-only JSON to
      `neuralstock-r2-release-lock-<revision>.json`; confirm that name is absent
      from draft release `v0.1.0`, upload it once without `--clobber`, and record
      its SHA-256.
- [x] Dispatch `Finalize release` from exact current protected `main` (or the
      same signed tag before main advances) with the signed-tag commit, revision,
      and SHA-256. It accepts exactly five attested candidate assets plus this
      one evidence file, verifies candidate and lock content, publishes once,
      and reads back `immutable: true`.
- [x] `gh release verify v0.1.0` and `gh release verify-asset` succeed for all six
      local files. Phase B must retrieve the exact immutable evidence asset.
- [x] The Cloudflare dashboard independently shows all three exact prefixes and
      indefinite conditions. Until this evidence exists and Phase B passes, the
      release remains incomplete.

Joseph's OAuth apply at `2026-08-02T03:04:21Z` created the three target rules;
the check-only readback at `2026-08-02T03:11:11Z` reported
`mode: already-present`. Their SHA-256 values are recorded in the release record.
Finalizer run `30730205780` published immutable release `v0.1.0` with exactly six
assets. Its hosted runner verified the release attestation and every asset after
GitHub propagation. Local `gh 2.82.1` did not discover that release attestation,
so no local-CLI verification claim is made beyond the hosted-run evidence.

At `2026-08-02T03:33Z`, Joseph independently inspected the authenticated
Cloudflare dashboard for `neuralstock-public`. **Settings > Bucket Lock Rules**
visibly showed all eight rules enabled with **Indefinite** retention, including
the two v0.2 contract prefixes and exact `snapshot-744accaa3f9efcd0` prefix.
This was a separate UI check from the API readback, not second-person review.

## 9. Closeout

- [x] A post-deployment `Production health` run passes after caches settle.
- [x] Release record links the source commit, candidate workflow, attestation,
      draft, finalizer, immutable release attestation, production deployment,
      registry revision, and snapshot lock evidence.
- [x] Restore and withdrawal contacts are assigned for the release window.
- [x] Any known limitation is documented without weakening the published gates.

Joseph Nordqvist is the bootstrap restore operator and security/withdrawal
responder for this release window under the governance policy's multi-role solo
exception. That assignment does not authorize external contributor publication.

Known limitation: `cabinet_01@1.0.1` has authored coplanar decorative door faces
that can z-fight in the Three.js viewer. Artifact hashes, downloads, provenance,
dimensions, anchors, collision data, and the immutable graph remain valid, so
the visual issue does not weaken a release gate. Version 1.0.1 remains immutable;
the correction is a future `1.0.2` with at least 1 mm face separation and a
coplanar-overlap regression test.

Post-deployment health run `30731015545` passed on protected controller
`181e0d661e0e9f6d662e1bc18ecdc37dc38d9cff` at
`2026-08-02T03:40:23Z`, verifying canonical revision
`744accaa3f9efcd053d8e589b2bb7e966753b070004f7c78ef00c3431cbbe391`
with the complete fifteen-entry registry and sitemap plus representative
first-entry route/artifact/range delivery. The separately recorded read-only
audit covered all 227 immutable plan items and all fifteen GLB ranges.
`docs/releases/v0.1.0.md` contains the complete linked evidence record.
