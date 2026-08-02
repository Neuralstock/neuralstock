# NeuralStock v0.1 release checklist

Use this checklist for a Room Zero v0.1 release or exact rebuild. It complements
`docs/RELEASE.md`; it does not replace the executable validation gates.

The first-party bootstrap may run under the recorded solo-maintainer exception
in `GOVERNANCE.md`. Where this checklist calls for an independent operator, the
release record must say that independent review was unavailable and record a
separate clean verification by the owner; it must not claim two-person review.
No external contributor asset may use that exception.

## 1. Authority and source freeze

- [ ] Release commit is reviewed, signed, pushed, and protected.
- [ ] Working tree contains no unexplained or untracked release input.
- [ ] Version matches the Python and npm package metadata and intended tag.
- [ ] Every active contract-bearing source uses the owned canonical v0.2 prefix
      `https://schemas.neuralstock.ai/v0.2/`; no draft unowned-domain reference
      remains.
- [ ] Every catalog entry has an accepted direct-dedicator CC0 attestation,
      exact source hash, evidence hash, and no unresolved rights-review state.
- [ ] The Room Zero author attestation still identifies Joseph Nordqvist and the
      exact 15 assets at asset version 1.0.1.
- [ ] Historical 1.0.0 attestation bytes still hash to
      `e687b259dabc8080a610dd2de11be347e444d8f4a7a9a3df8548d92d9e77d58f`
      and remain at their original indefinitely locked content-addressed object.
- [ ] The distinct 1.0.1 migration attestation hashes to
      `95531e49b5da7616fa769cdbd7d97a84e51beb8798d5180fb3abfbb2a074c32e`,
      and every 1.0.1 provenance record references that evidence rather than
      rewriting the historical object.
- [ ] Every 1.0.1 dedication names `NeuralStock Open Asset Engine`, binds
      `https://neuralstock.ai/` and `https://neuralstock.ai/#mission`, and the
      migration attestation explicitly preserves the historical 1.0.0 bytes.
- [ ] `catalog/room-zero-v1.0.1-source-migration.json` matches all 15 accepted
      `.blend` hashes and records byte-for-byte reuse of the locked 1.0.0 inputs.
- [ ] No generated GLB, preview, report, registry, or receipt was edited by hand.

## 2. GitHub rollout controls

- [ ] `main` requires pull requests, the five named checks, signed commits,
      linear history, conversation resolution, and blocks force-push/deletion.
- [ ] The active `neuralstock-release-tags` ruleset covers `refs/tags/v*` and
      restricts creation, movement, and deletion to `@bighippoman`.
- [ ] `release`, `npm`, and `pypi` allow only tag pattern `v*`; `production`
      allows only branch `main` and tag pattern `v*`.
- [ ] The environment policy types were inspected in the GitHub UI because the
      REST list response may omit whether an existing pattern is a branch or tag.
- [ ] The applied protection mode and exact reconciler command are in the release
      record. Reviewer mode is required for external assets; any first-party
      solo-mode use records the bootstrap exception explicitly.

## 3. Locked checks

- [ ] `uv sync --frozen --extra dev` succeeds.
- [ ] `pnpm install --frozen-lockfile` succeeds.
- [ ] Python format, lint, schema, unit, and integration tests pass.
- [ ] TypeScript type checks, unit tests, package dry-run, and build pass.
- [ ] Pinned Blender image reproduces its locked manifest and config digests.
- [ ] Two independent accepted-source builds are byte-identical under the
      documented v0.1 reproducibility rules.
- [ ] All 15 GLBs report zero Khronos errors and zero warnings.
- [ ] Real-release Three.js and desktop/narrow browser checks pass.

## 4. Candidate construction

- [ ] Run `Release candidate` on the intended commit/tag with reviewed UTC build
      and publication timestamps.
- [ ] `tools/release-room-zero.sh` completes without an override of a failed gate.
- [ ] `tools/package-release-candidate.sh` creates a deterministic archive,
      R2 plan, image metadata, release metadata, and `SHA256SUMS`.
- [ ] `tools/verify-release-candidate.sh` validates checksums, archive paths,
      release graph, immutable schema/profile/license plan, complete embedded
      MIT notices, version, and registry revision.
- [ ] Record source commit, release workflow run ID, candidate SHA-256, registry
      revision, and entry/artifact counts.

## 5. Attestation and optional GitHub Release

- [ ] GitHub build-provenance attestation exists for every candidate subject.
- [ ] In reviewer mode, a second operator downloads the workflow artifact and
      verifies it with the command below; in solo bootstrap, the owner repeats
      it from a clean
      checkout and records that it was not independent:

  ```sh
  gh attestation verify <candidate-file> --repo Neuralstock/neuralstock
  ```

- [ ] Candidate checksums verify outside the producing job.
- [ ] If a GitHub Release is requested, workflow ref is the existing protected
      tag `v<version>` and the protected `release` environment is approved.
- [ ] No npm, PyPI, OCI, R2, or Pages publication is inferred from creating a
      candidate or GitHub Release.

## 6. Package publication

- [ ] `@neuralstock/client` and `neuralstock` names are still controlled by the
      intended maintainer; a not-found response alone is not proof of control.
- [ ] The package candidate ran on the protected `v<version>` tag and its run
      ID, commit, checksums, identities, and attestations verify independently.
- [ ] npm trusts only `Neuralstock/neuralstock`, `publish-packages.yml`,
      environment `npm`, and action `npm publish`.
- [ ] PyPI trusts only `Neuralstock/neuralstock`, `publish-packages.yml`, and
      environment `pypi` for project `neuralstock`.
- [ ] GitHub environments `npm` and `pypi` require a non-initiating release
      operator in reviewer mode and contain no registry token. Any solo
      first-party bootstrap is identified as the documented exception.
- [ ] If npm needs a one-time namespace bootstrap, Joseph publishes the exact
      attested archive interactively with 2FA, configures trusted publishing,
      and removes any temporary token without putting it in GitHub.
- [ ] `Publish packages` is dispatched from the same tag and candidate run;
      each selected protected environment is approved separately.
- [ ] Clean temporary projects install and smoke-test exact versions
      `@neuralstock/client@<version>` and `neuralstock==<version>`.

## 7. Production asset publication

- [ ] Start `Production deploy` phase `immutable-bootstrap` from the exact
      candidate source commit; enter the recorded run ID, version, and revision.
- [ ] In reviewer mode, a release operator who did not initiate the deployment
      approves production. Any solo first-party bootstrap is identified as the
      documented exception and does not claim independent approval.
- [ ] Both `assets.neuralstock.ai` and `schemas.neuralstock.ai` are active
      custom domains on `neuralstock-public`.
- [ ] Phase A accepts only all-twelve-absent or all-twelve-byte-identical state
      for the fresh v0.2 contracts, stages every immutable plan item with
      `--immutable-only`, reports no alias updates, and proves both aliases are
      byte-identical before and after staging.
- [ ] Every v0.2 schema, the v0.2 `web-v1` profile, and both adjacent `LICENSE`
      companions are byte-identical through the public schema origin after
      Phase A; the immutable-bootstrap workflow evidence artifact is retained.
- [ ] Signed tag `v0.1.0` already has its non-draft GitHub Release; that release
      is the sole durable location accepted for the deterministic lock evidence.
- [ ] R2 scoped publication credentials and Pages token are present only in the
      protected environment.
- [ ] A separate `CLOUDFLARE_REDIRECT_API_TOKEN` has only `Zone > Zone > Read`
      and `Zone > Single Redirect > Edit` (`Dynamic URL Redirects Write` in the
      API) for `neuralstock.ai`; the protected environment also holds the exact
      `NEURALSTOCK_CLOUDFLARE_ZONE_ID` variable.
- [ ] The zone-level rule with ref `neuralstock_www_to_apex` is enabled, returns
      301, preserves path and query, and has passed API readback. The Pages
      `_redirects` file contains no unsupported domain-level rule.
- [ ] Do not dispatch phase `publish` until Section 8 is complete and its
      independent JSON readback is a deterministic GitHub Release asset.
- [ ] Phase `publish` downloads that asset, verifies its caller-supplied SHA-256,
      binds its revision and release-plan SHA-256 to the candidate, and validates
      all eight exact enabled-indefinite baseline/target rules before any write.
- [ ] Immutable objects and version manifests are reverified before aliases.
- [ ] `registry.json` updates before `snapshots/latest.json`, with the latter last.
- [ ] Live registry revision equals the approved revision.
- [ ] `registry.json`, `snapshots/latest.json`, and the immutable
      `snapshots/<revision>/registry.json` are byte-identical, and the semantic
      registry revision recomputes to the approved SHA-256.
- [ ] The exact checked-in machine-discovery document and sitemap are live with
      the intended content types and CORS/cache headers; the sitemap has exactly
      one stable route per registry entry and a registry-derived route returns
      the application shell.
- [ ] Site, exact `www` redirect, full manifest/GLB/Blender source hashes and byte
      counts, GLB range content, and browser CORS behavior are verified by
      `sh tools/verify-production.sh <revision> dist/production-release`.
- [ ] `registry.json` and `snapshots/latest.json` return
      `public, max-age=60, must-revalidate`; the zone Browser Cache TTL remains
      **Respect Existing Headers**.
- [ ] Content-addressed objects, asset-version manifests, and revision snapshots
      return `public, max-age=31536000, immutable` and support byte ranges where
      applicable.

## 8. Retention protection

Historical indefinite locks must remain present and retain their original names:

- [ ] `immutable-objects` on `objects/sha256/`.
- [ ] `immutable-manifests` on `assets/`.
- [ ] `schema-v0.1` on `v0.1/`.
- [ ] `profile-v0.1` on `profiles/v0.1/`.
- [ ] `room-zero-snapshot` on
      `snapshots/a3e851194d092bf1a06452a62ae98ba8687462ea0cbca668a9b9cc2385768523/`.
- [ ] `registry.json` and `snapshots/latest.json` remain outside indefinite locks.
- [ ] `schema-v0.2` is enabled indefinitely on exactly `v0.2/`.
- [ ] `profile-v0.2` is enabled indefinitely on exactly `profiles/v0.2/`.
- [ ] `snapshot-<first-16-revision-hex>` is enabled indefinitely on exactly
      `snapshots/<revision>/`.
- [ ] No R2 bucket-configuration token is stored in GitHub; the account-wide
      configuration-write permission is not accepted for release automation.
- [ ] From the protected release checkout, an interactively authenticated
      operator runs `tools/manage-r2-release-lock.sh <revision> --release-root
      <release-root> --apply` only after Phase A stages the complete immutable
      graph and its strict public v0.2 contract check passes.
- [ ] The helper preserves every baseline lock, rejects mutable-alias coverage,
      reproduces the candidate plan, directly byte-verifies every immutable R2
      item, recomputes the snapshot revision, and reads back all three new rules.
- [ ] For newly created rules, all 12 contract objects and the snapshot are
      byte-identical before and after locking; their keys, SHA-256 values, and
      byte counts are present in the JSON evidence.
- [ ] A fresh check-only invocation reports `mode: already-present`; its JSON
      and the apply JSON are hashed and linked from the release record with the
      operator and UTC timestamp.
- [ ] Copy the check-only JSON to
      `neuralstock-r2-release-lock-<revision>.json`; confirm that name is absent
      from GitHub Release `v0.1.0`, upload it once without `--clobber`, and record
      its SHA-256. Phase B must retrieve this exact asset.
- [ ] The Cloudflare dashboard independently shows all three exact prefixes and
      indefinite conditions. Until this evidence exists and Phase B passes, the
      release remains incomplete.

## 9. Closeout

- [ ] Scheduled production health passes after caches settle.
- [ ] Release record links the source commit, candidate workflow, attestation,
      production deployment, registry revision, and snapshot lock evidence.
- [ ] Restore and withdrawal contacts are assigned for the release window.
- [ ] Any known limitation is documented without weakening the published gates.
