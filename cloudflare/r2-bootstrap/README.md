# Local R2 bootstrap bridge

This Worker gives the release uploader a short-lived, credential-free path to the
`neuralstock-public` bucket through Wrangler's authenticated remote R2 binding. It
is deliberately bound to `127.0.0.1`, has no routes or preview URL, and must not be
deployed.

The binding is remote, so a local development session writes to the real R2
bucket. The Worker accepts only `PUT /upload`, validates the release key and
metadata contract, and asks R2 to verify each streamed SHA-256 checksum.

## Run it

In one terminal:

```sh
pnpm wrangler dev --config cloudflare/r2-bootstrap/wrangler.jsonc
```

In another terminal:

```sh
node tools/r2-bootstrap-upload.mjs \
  --endpoint http://127.0.0.1:8787/upload \
  --root dist/release \
  --plan work/final-room-zero-v01-current/r2-plan.json
```

The CLI validates and hashes every file before the first upload. Immutable items
are uploaded with bounded concurrency. `registry.json` and
`snapshots/latest.json` are sent sequentially only after all immutable items have
succeeded.

To regenerate the binding types after a configuration change:

```sh
pnpm wrangler types \
  --config cloudflare/r2-bootstrap/wrangler.jsonc \
  cloudflare/r2-bootstrap/worker-configuration.d.ts
```

## Licensing

`worker-configuration.d.ts` contains Wrangler-generated Cloudflare Worker
runtime declarations under Apache-2.0 and retains the emitted Cloudflare and
Microsoft headers. See the repository
[`THIRD_PARTY_NOTICES.md`](../../THIRD_PARTY_NOTICES.md) for the complete
license location and the other distributed third-party components.
