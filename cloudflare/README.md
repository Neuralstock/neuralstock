# Cloudflare production origin

The initial NeuralStock rollout uses a dedicated R2 bucket and custom domain for the public,
root-relative static registry:

- account resource: `neuralstock-public`
- asset origin: `https://assets.neuralstock.ai`
- schema origin: `https://schemas.neuralstock.ai`
- R2 development URL: disabled
- public access: read-only through the custom domain
- browser access: wildcard `GET` and `HEAD` CORS, because third-party games and
  agents are first-class registry consumers

## Current launch state

The `neuralstock-public` bucket is populated with Room Zero registry revision
`a3e851194d092bf1a06452a62ae98ba8687462ea0cbca668a9b9cc2385768523`.
Both R2 custom domains are active, the `r2.dev` development URL is disabled,
and the CORS policy permits public `GET` and `HEAD` access while exposing the
headers needed for byte-range downloads. Versioned schema and profile prefixes
are indefinite-lock, one-year-cache content; they are not a separate Pages
project.

The Cloudflare Pages project `neuralstock` has both preview and production
deployments. The `neuralstock.ai` and `www.neuralstock.ai` Pages custom domains
are active. Production canonicalizes `www` to the apex with a zone-level Single
Redirect; Pages does not support a domain-level `_redirects` entry. The site
exposes per-asset GLB, `.blend`, and manifest downloads directly from
`assets.neuralstock.ai`, without proxying the files through Pages or a Worker.

## Canonical website redirect

Use a dedicated API token restricted to `neuralstock.ai` with `Zone > Zone >
Read` and `Zone > Single Redirect > Edit` (`Dynamic URL Redirects Write` in the
API), then reconcile the one managed rule:

```sh
export CLOUDFLARE_REDIRECT_API_TOKEN='<scoped token>'
export NEURALSTOCK_CLOUDFLARE_ZONE_ID='<32-character zone ID>'
sh tools/configure-cloudflare-www-redirect.sh
```

The rule ref is `neuralstock_www_to_apex`. It matches only
`www.neuralstock.ai`, returns 301 to `https://neuralstock.ai` with the original
path, and preserves the query string. The helper can adopt one exact host-only
rule created in the dashboard, refuses broader or duplicate `www` rules, and
reads its exact configuration back after create or update. The protected
production workflow runs it before publication and
`tools/verify-production.sh` checks the external status and `Location` without
following the redirect.

## R2 configuration

The custom domain must belong to an active Cloudflare zone in the same account
as the bucket. Do not point a CNAME at an `r2.dev` hostname. Wrangler attaches
the domain and creates the managed DNS record:

```sh
pnpm wrangler r2 bucket domain add neuralstock-public \
  --domain assets.neuralstock.ai \
  --zone-id "$NEURALSTOCK_CLOUDFLARE_ZONE_ID" \
  --min-tls 1.2 \
  --force

pnpm wrangler r2 bucket domain add neuralstock-public \
  --domain schemas.neuralstock.ai \
  --zone-id "$NEURALSTOCK_CLOUDFLARE_ZONE_ID" \
  --min-tls 1.2 \
  --force
```

Apply and inspect the versioned CORS policy:

```sh
pnpm wrangler r2 bucket cors set neuralstock-public \
  --file cloudflare/r2-cors.json \
  --force
pnpm wrangler r2 bucket cors list neuralstock-public
```

Publish content with the repository's ordered R2 adapter rather than a loop of
Wrangler object uploads. The adapter verifies the complete release, writes
content-addressed objects and versioned contracts create-only with SHA-256
metadata, and updates `registry.json` and `snapshots/latest.json` last:

```sh
uv sync --frozen --extra r2
uv run neuralstock r2 sync \
  --root dist/release \
  --bucket neuralstock-public \
  --endpoint-url "https://$CLOUDFLARE_ACCOUNT_ID.r2.cloudflarestorage.com"
```

The sync requires `NEURALSTOCK_R2_ACCESS_KEY_ID` and
`NEURALSTOCK_R2_SECRET_ACCESS_KEY` from an Object Read & Write token scoped only
to `neuralstock-public`. Do not commit those credentials. Keep the zone Browser
Cache TTL on **Respect Existing Headers**, so the two aliases preserve their
60-second origin policy while immutable keys retain one-year caching.

## Release retention gate

R2 bucket-lock configuration is intentionally absent from GitHub Actions. The
bucket-scoped S3 publication credentials cannot manage lock rules, and the
available configuration-write token is account-wide. After Phase A stages the
complete immutable release without aliases, use a local interactive Wrangler
OAuth session and the fail-closed helper with the exact extracted release root:

```sh
pnpm wrangler login
tools/manage-r2-release-lock.sh '<registry-revision>' \
  --release-root '<release-root>' --apply
tools/manage-r2-release-lock.sh '<registry-revision>' \
  --release-root '<release-root>'
pnpm wrangler logout
```

The helper validates all five historical locks, refuses any indefinite rule
covering a mutable alias, reproduces the candidate plan, and directly verifies
every immutable R2 item. It creates and reads back only `schema-v0.2` on
`v0.2/`, `profile-v0.2` on `profiles/v0.2/`, and the exact revision snapshot
rule. Retain both JSON outputs, upload the check-only file once under its
deterministic name to the signed-tag GitHub Release, and confirm all three rules
in the dashboard. Phase B retrieves and binds that evidence before aliases or
Pages can change.
