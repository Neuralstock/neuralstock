# Production operations

## Production inventory

| Surface | Production value |
| --- | --- |
| Website | `https://neuralstock.ai` |
| Canonical website redirect | `https://www.neuralstock.ai/*` -> `https://neuralstock.ai/*` |
| Asset origin | `https://assets.neuralstock.ai` |
| Schema origin | `https://schemas.neuralstock.ai` |
| Cloudflare Pages project | `neuralstock` |
| Current Pages production deployment | `de6d320c-7d34-42f9-a344-87daf5b36df7` from protected commit `181e0d661e0e9f6d662e1bc18ecdc37dc38d9cff` |
| R2 bucket | `neuralstock-public` |
| Canonical Room Zero 1.0.1 registry revision | `744accaa3f9efcd053d8e589b2bb7e966753b070004f7c78ef00c3431cbbe391` |
| Historical Room Zero 1.0.0 preview revision | `a3e851194d092bf1a06452a62ae98ba8687462ea0cbca668a9b9cc2385768523` |
| Last protected publish / health runs | `30730929891` / `30731015545`, both successful on `2026-08-02` |

Both origins are custom domains on the same R2 bucket. `r2.dev` remains
disabled. Normal downloads and schema reads go directly to R2 and do not pass
through Pages or a Worker. On 2026-08-01, Cloudflare resolvers `1.1.1.1`,
Google `8.8.8.8`, and Quad9 `9.9.9.9` all returned the Cloudflare apex
addresses. The initial apex and `www` HTTP 200 responses established DNS and
Pages attachment only; an HTTP 200 from `www` is not accepted as
canonical-host behavior for the public rollout. Later that day, the zone-level
rule was enabled and an external probe of `/test/path?x=1` returned HTTP 301
with exact `Location: https://neuralstock.ai/test/path?x=1`.

## Canonical website host

Cloudflare Pages does not support a host-level rule in a Pages `_redirects`
file. The checked-in file therefore contains only the supported `/asset/*` SPA
rewrite. Configure the host redirect as a zone-level Cloudflare Single Redirect
with this exact contract:

| Setting | Required value |
| --- | --- |
| Rule ref | `neuralstock_www_to_apex` |
| Match | `http.host eq "www.neuralstock.ai"` |
| Target expression | `concat("https://neuralstock.ai", http.request.uri.path)` |
| Status | `301` |
| Preserve query string | `true` |

The protected production environment stores
`CLOUDFLARE_REDIRECT_API_TOKEN` with only `Zone > Zone > Read` and
`Zone > Single Redirect > Edit` (API permission: `Dynamic URL Redirects Write`)
for `neuralstock.ai`, plus the non-secret
`NEURALSTOCK_CLOUDFLARE_ZONE_ID` variable. Reconcile the rule manually before
the first promotion, or run the same idempotent helper used by the deployment
workflow:

```sh
export CLOUDFLARE_REDIRECT_API_TOKEN='<scoped token>'
export NEURALSTOCK_CLOUDFLARE_ZONE_ID='<32-character zone ID>'
sh tools/configure-cloudflare-www-redirect.sh
```

The helper verifies the active zone identity, refuses to add a rule when a
different `www` redirect could conflict, safely adopts a single host-only rule
created in the dashboard, creates or updates only that rule under the stable ref
above, and reads the result back. It never replaces the full redirect ruleset.
Cloudflare documents why domain-level Pages `_redirects`
rules are unsupported in the
[Pages redirect reference](https://developers.cloudflare.com/pages/configuration/redirects/#advanced-redirects)
and documents the zone Rulesets API in the
[Single Redirect API guide](https://developers.cloudflare.com/rules/url-forwarding/single-redirects/create-api/).

`sh tools/verify-production.sh` sends a non-following request through `www`
and requires an exact 301 `Location` at the apex with the same path and query.
A successful `HEAD`, a followed 200, or a redirect that drops either component
does not pass.

During a deployment, `NEURALSTOCK_VERIFY_ATTEMPTS` applies to the exact
machine-discovery document, sitemap, and registry alias so independently
propagating Pages and R2 cache entries can converge. Every successful read is
still checked byte-for-byte and then subjected to the complete header and
semantic contract; a persistent mismatch fails closed.

## Historical preview evidence

The preview revision and its `assets/*/1.0.0/manifest.json` keys are immutable
history, not a slot to reuse for the owned-schema migration. The historical CC0
attestation remains byte-for-byte at
`/objects/sha256/e6/e687b259dabc8080a610dd2de11be347e444d8f4a7a9a3df8548d92d9e77d58f`.
Its SHA-256 is the filename digest. The canonical migration publishes asset
version 1.0.1, a new registry revision, and a distinct migration-attestation
object with SHA-256
`95531e49b5da7616fa769cdbd7d97a84e51beb8798d5180fb3abfbb2a074c32e`.
Record the verified 1.0.1 revision in the deployment and release records; never
replace the historical value in evidence intended to describe the preview.

## R2 immutability policy

The production bucket has eight indefinite object-lock rules:

| Rule | Prefix |
| --- | --- |
| `immutable-objects` | `objects/sha256/` |
| `immutable-manifests` | `assets/` |
| `schema-v0.1` | `v0.1/` |
| `profile-v0.1` | `profiles/v0.1/` |
| `room-zero-snapshot` | `snapshots/a3e851194d092bf1a06452a62ae98ba8687462ea0cbca668a9b9cc2385768523/` |
| `schema-v0.2` | `v0.2/` |
| `profile-v0.2` | `profiles/v0.2/` |
| `snapshot-744accaa3f9efcd0` | `snapshots/744accaa3f9efcd053d8e589b2bb7e966753b070004f7c78ef00c3431cbbe391/` |

At `2026-08-02T03:33Z`, Joseph Nordqvist independently inspected Cloudflare's
`neuralstock-public` **Settings > Bucket Lock Rules** view in an authenticated
browser session. The dashboard visibly showed all eight rules above as enabled
with an **Indefinite** retention condition. This UI readback supplements the
credential-sanitized apply and check-only JSON evidence; it does not replace the
byte, prefix, or plan-hash verification in that evidence. “Independently” here
means a separate UI surface from the API readback; it is not a second-person
review.

`registry.json` and `snapshots/latest.json` intentionally remain mutable aliases.
They are updated last and must always reference a complete immutable graph.

The writers in `src/neuralstock/r2.py` and the reviewed bootstrap uploader set
both aliases to `public, max-age=60, must-revalidate`. Content-addressed objects,
version manifests, and revision snapshots are set to
`public, max-age=31536000, immutable`.

The 2026-08-01 production check verified that an immutable GLB object returned
the one-year immutable policy, `Accept-Ranges`, and changed from Cloudflare
`MISS` to `HIT`. An initial four-hour alias header was traced to the zone-wide
Browser Cache TTL. Setting that control to **Respect Existing Headers** restored
the exact 60-second policy for both aliases without weakening immutable paths.
Subsequent checks verified the schema host changing from `MISS` to `HIT` with
the one-year immutable policy. The deploy and health workflows guard these
values against regression.

The existing `schema-v0.1`, `profile-v0.1`, and Room Zero snapshot rules are
historical locks. Never rename, weaken, or reinterpret them as v0.2 protection.
The first v0.2 publication used the following two-phase R2 bootstrap with an
immutable GitHub Release boundary between the phases; future fresh contract
namespaces must preserve the same ordering:

1. dispatch `Production deploy` with phase `immutable-bootstrap`; it accepts an
   all-absent or exact-byte v0.2 namespace, stages every immutable plan item and
   the exact revision snapshot, and proves that neither alias changed;
2. run the local OAuth gate below, which verifies the public v0.2 contracts and
   every immutable item directly from R2 before creating `schema-v0.2` on
   `v0.2/`, `profile-v0.2` on `profiles/v0.2/`, and the exact revision-snapshot
   rule, all indefinitely;
3. independently rerun the gate, hash its check-only JSON, upload that JSON once
   under its deterministic name to the signed-tag draft release, and confirm
   all three rules in the Cloudflare dashboard;
4. dispatch protected `Finalize release` on that tag with the revision and
   evidence SHA-256; it verifies exactly five candidate assets plus the evidence,
   all candidate and R2 gates, repository release immutability, and both GitHub
   attestation layers before the draft becomes immutable; and
5. only after `gh release verify v<version>` succeeds, dispatch phase `publish`
   with the evidence SHA-256. The workflow verifies the immutable release and
   asset, binds it to the candidate plan, then re-verifies immutable content
   before publishing aliases and the site.

Cloudflare exposes bucket-lock configuration through its account-level R2
configuration API. The bucket-scoped S3 object credentials used by deployment
cannot manage locks, while the available configuration-write permission is
broader than this one bucket. Do not store an R2 configuration-write token in
GitHub. The retention gate deliberately uses an operator's short-lived local
Wrangler OAuth session between immutable staging and alias publication.

From the exact protected release checkout, with no `CLOUDFLARE_API_TOKEN` or
global API key in the environment, authenticate interactively and run:

```sh
revision='<64-character verified registry revision>'
release_root='<extracted, verified release root>'
mkdir -p work/retention
pnpm wrangler login
tools/manage-r2-release-lock.sh "$revision" --release-root "$release_root" --apply \
  | tee "work/retention/$revision-apply.json"
tools/manage-r2-release-lock.sh "$revision" --release-root "$release_root" \
  | tee "work/retention/$revision-readback.json"
pnpm wrangler logout
sha256sum "work/retention/$revision-apply.json" \
  "work/retention/$revision-readback.json"
evidence="work/retention/neuralstock-r2-release-lock-$revision.json"
cp "work/retention/$revision-readback.json" "$evidence"
if gh release view v0.1.0 --json assets --jq '.assets[].name' \
  | grep -Fx "$(basename "$evidence")"; then
  echo 'deterministic retention-evidence asset already exists' >&2
  exit 1
fi
gh release upload v0.1.0 "$evidence"
```

Do not use `--clobber`: an existing deterministic release asset is an audit
conflict that must stop publication. The helper refuses CI and all Wrangler
environment-credential paths. It preserves the five historical rules, rejects
any indefinite rule that covers a mutable alias, reproduces the release plan,
verifies the public v0.2 contract, directly byte-verifies every staged immutable
R2 item, and recomputes the snapshot's semantic revision. It creates only the
three exact target rules and performs fresh rule and target-object readbacks.
When it creates any rule, all 12 contract objects and the snapshot must have
identical pre/post bytes. Its credential-free JSON includes the plan hash,
complete direct-R2 key/hash/size evidence, and all lock rules.

The independent invocation must report `mode: already-present` and no created
rules. After the upload, dispatch `Finalize release` from tag `v0.1.0` with the
exact revision and check-only hash. It rejects an extra or missing asset, a
byte/API-digest mismatch, an unattested candidate, invalid lock evidence,
disabled repository release immutability, or any published mutable release. If
a prior finalizer run published successfully but failed during post-publication
checks, a rerun accepts only that exact already-immutable six-asset release,
performs no publication mutation, and repeats every verification. Record its run
and verify `gh release verify v0.1.0` before Phase B. Phase `publish` accepts
neither a caller assertion nor a placeholder hash: it downloads the
deterministic asset from immutable GitHub Release `v0.1.0`, checks the release
and asset attestations, exact SHA-256 and JSON contract, and binds its revision
and plan hash before any external write. Record Phase A, finalizer, and Phase B
runs, operator, UTC time, both local JSON hashes, release-asset link/hash,
immutable-release verification, and dashboard confirmation in
`docs/releases/<tag>.md`.
Cloudflare's
[bucket-lock documentation](https://developers.cloudflare.com/r2/buckets/bucket-locks/)
confirms that rules protect both existing and future objects and that the
strictest matching rule wins.

Never create an indefinite rule over `registry.json` or
`snapshots/latest.json`. Never delete or weaken an existing immutable-prefix
rule as part of an ordinary release.

## Routine health

The scheduled `Production health` workflow checks:

- the exact `www` 301 preserves path and query at the apex;
- the website shell, checked-in machine-discovery document, sitemap, and a
  registry-derived stable asset route are live with the intended content types;
- the live website CSP exactly matches the checked-in Pages policy, including
  the `blob:` connection source required by the verified-byte Three.js loader;
- `registry.json`, `snapshots/latest.json`, and
  `snapshots/<revision>/registry.json` are byte-identical;
- the registry's semantic revision recomputes to its declared SHA-256;
- the first version manifest, GLB, and Blender source match their full SHA-256
  and byte descriptors;
- the GLB serves an exact HTTP 206 byte range matching the full verified file;
- every declared preview for every current entry matches its hash and byte
  descriptor and carries the required cache and browser CORS headers;
- browser CORS and exposed download headers are present on the representative
  manifest, GLB, and Blender source; and
- aliases and discovery expose their short revalidating policies while
  immutable snapshots, manifests, objects, schemas, and profiles expose the
  one-year immutable policy.

Preview verification fails closed if the registry has more than
`NEURALSTOCK_VERIFY_PREVIEW_LIMIT` entries; the default is 100 and therefore
covers Room Zero plus the first planned expansion. Raise the limit deliberately
in the protected deploy and health workflows before crossing that boundary,
after confirming the workflow timeout and egress remain appropriate. The limit
never permits sampling or a silent partial pass.

The full GLB response must advertise `Accept-Ranges: bytes`. The partial
response is proven by its 206 status, exact `Content-Range`, byte count, and
content; it need not repeat the advisory `Accept-Ranges` field, consistent with
[RFC 9110 section 14.3](https://www.rfc-editor.org/rfc/rfc9110.html#section-14.3).

Daily, review failed scheduled runs and Cloudflare service alerts. Weekly:

- verify a complete snapshot into an independent temporary directory or mirror;
- compare the public alias revision with the most recent approved deployment;
- review R2/Pages error rates and unusual egress;
- confirm GitHub Dependabot and security alerts have an owner;
- review npm and PyPI trusted-publisher identities for unexpected entries; and
- confirm the production and release reviewer lists are current.

Monthly, test a release-candidate download and `gh attestation verify`, review
credential usage, and confirm a second operator can execute the runbook.

## Production deployment

The procedure below records the existing Room Zero v0.1.0 and v0.2 contract
bootstrap. `docs/RELEASE-CHECKLIST-v0.1.md` is historical and must not be reused
as the generic checklist for a new founder asset. Before the first non-Room-Zero
publication, protected `main` must contain a generic founder-lane checklist and
incremental per-asset or bounded-batch release path.

1. Complete the release checklist applicable to the exact release scope. For
   the historical Room Zero release, that was
   `docs/RELEASE-CHECKLIST-v0.1.md`.
2. Run `Release candidate` on the intended protected tag. It creates an
   unpublished draft with exactly the five attested candidate assets.
3. Record its workflow run ID, release version, source commit, registry revision,
   candidate checksums, and attestation URL.
4. Start `Production deploy` phase `immutable-bootstrap` on that exact commit
   and enter the recorded run ID, version, and revision. Leave the retention
   evidence SHA empty.
5. Apply the protected approval control for the recorded lane. An external
   asset requires a different operator; an eligible founder asset uses the
   owner-operated protected path. Record the actual mode and never characterize
   owner-only action as independent.
6. Phase A verifies the candidate, reproduces its R2 plan, stages every
   immutable object with no alias or Pages update, confirms alias bytes did not
   change, and verifies all twelve public v0.2 contract files after cache
   convergence.
7. Complete the manual OAuth retention gate and upload the deterministic
   evidence to the draft described above. Record independent dashboard
   confirmation.
8. Run protected `Finalize release` on the same tag with the exact revision and
   evidence SHA-256. Record its exact asset/digest checks, build attestations,
   R2 evidence verification, `immutable: true` readback, and release attestation.
9. Start phase `publish` on the same commit and candidate with the exact SHA-256
   of the now-immutable evidence. Apply the protected review control for the
   recorded lane: an independent protected-environment reviewer for external
   assets, or founder attestation plus all lane-aware checks for an eligible
   founder asset.
10. Phase B verifies the immutable release and asset, hashes, parses, and
    candidate-binds the evidence before any write; then it re-verifies immutable
    content, publishes both aliases, optionally deploys Pages, and runs the
    complete production verifier.

This two-phase namespace bootstrap is required because v0.2 is fresh while the
existing v0.1 prefixes are immutable historical records. Once v0.2 is already
locked, later release procedures should drop the fresh-namespace exception
rather than treating v0.1 or v0.2 as mutable. Any future new schema/profile
namespace must repeat the same immutable-stage, lock, evidence, then alias
sequence.

## Incident actions

### Website failure with healthy assets

Stop new Pages deployments. Redeploy the last known-good Pages artifact or use
the Pages deployment rollback control. Do not change R2 aliases when the asset
graph is healthy.

If previews load but the Three.js viewer reports a blocked `blob:` connection,
compare the live `Content-Security-Policy` with
`examples/room-zero/public/_headers`. The verified-byte loader requires
`connect-src blob:`; preview images separately require `img-src blob:`. The
Cloudflare Insights beacon being blocked by `script-src 'self'` affects
telemetry only and is not evidence of an asset failure.

### Asset CORS failure with valid immutable bytes

First fetch each reported object with `Origin: https://neuralstock.ai` and
verify its SHA-256, response CORS headers, content type, and cache policy. Read
back `cloudflare/r2-cors.json` with Wrangler. If the control-plane rule is exact
but a custom-domain response is stale, purge only the
`assets.neuralstock.ai` and `schemas.neuralstock.ai` hostnames, rerun
`tools/verify-production.sh`, and hard-refresh the affected browser after the
origin passes. Cloudflare documents that cached R2 custom-domain objects can
retain headers from before a CORS change. Do not mutate content-addressed
objects, manifests, snapshots, or aliases to repair response-header cache state.

### Bad mutable registry alias

Stop publication. Select a previously verified immutable revision snapshot,
verify its full graph, then restore only `registry.json` and
`snapshots/latest.json` to that approved state. Record both old and restored
revisions. Do not replace content-addressed objects or version manifests.

### Suspected malicious or rights-encumbered asset

Stop new builds and publication, preserve logs and hashes, and open a private
security advisory when execution or credential impact is possible. Remove the
affected version from discovery and prevent `latest` from resolving to it.
Blocking hosted delivery may be necessary for security or legal reasons; retain
a non-sensitive tombstone and hash record. A withdrawal changes NeuralStock's
hosting and discovery state, not the legal meaning of an otherwise valid CC0
dedication.

The current registry schema and client understand withdrawals, but the
publisher does not yet generate them. Until automation is complete, Joseph may
perform an emergency withdrawal as a solo manual operation for immediate
containment. He must preserve the affected hashes, remove the version from
discovery, block hosted delivery when required, publish a non-sensitive
tombstone, and append an immutable incident record. Independent follow-up is
recorded when a qualified responder exists; its absence never delays urgent
containment. Public external intake remains closed until the external lane's
response controls are operational.

### Credential exposure

Cancel the active workflow, revoke the affected Cloudflare or R2 credential,
inspect audit logs, verify aliases and immutable objects, and issue a new
least-privilege credential. Rotating a credential does not require rebuilding
asset artifacts.

### Build-system compromise

Suspend releases, preserve the candidate and workflow attestations, rotate
publication credentials, and rebuild from the last trusted commit with newly
verified toolchain inputs. Do not “repair” an immutable release in place; create
a new version or withdrawal record.

## Recovery evidence

For every incident retain the UTC timeline, reporter channel, affected asset or
revision, hashes, workflow and deployment IDs, decisions, responders, restored
revision, and follow-up owner. Never place credentials, private identity
evidence, or hostile binaries in a public issue.
