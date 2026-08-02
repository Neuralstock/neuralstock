# NeuralStock

NeuralStock is an open, agent-native registry of CC0 Blender assets. Every
published asset pairs an editable `.blend` source with a validated GLB runtime
artifact, semantic metadata, provenance, inspection results, and a reproducible
build receipt.

The initial release is **Room Zero**: fifteen compatible assets that allow a
human or coding agent to assemble a correctly scaled Three.js room without
opening Blender or repairing geometry.

Read the [project purpose](https://github.com/Neuralstock/neuralstock/blob/main/PURPOSE.md)
and [architecture](https://github.com/Neuralstock/neuralstock/blob/main/ARCHITECTURE.md)
for the mission and accepted system design.

## Install the Python package

NeuralStock requires Python 3.12 or newer:

```sh
python -m pip install neuralstock
```

The default package validates, packages, and verifies local assets and static
registries. Install the optional R2 adapter only when a trusted publisher needs
Cloudflare R2 access:

```sh
python -m pip install 'neuralstock[r2]'
```

### Command line

The package installs the `neuralstock` command:

```sh
neuralstock --version
neuralstock validate --schema asset.intent ./asset.intent.json
neuralstock sha256 --json ./asset.intent.json
neuralstock release verify --root ./neuralstock-release
neuralstock r2 plan --root ./neuralstock-release
```

Run `neuralstock <command> --help` for every option. `r2 plan` is read-only;
`r2 sync` additionally requires the `r2` extra, explicitly scoped credentials,
bucket, and endpoint URL.

### Python API

Version 0.1 exposes canonical endpoint constants and immutable snapshot URL
construction from the top-level package:

```python
from neuralstock import (
    CANONICAL_REGISTRY_URL,
    DISCOVERY_URL,
    SCHEMA_ORIGIN,
    registry_snapshot_url,
)

revision = "0123456789abcdef" * 4
immutable_registry = registry_snapshot_url(revision)
```

`registry_snapshot_url` accepts only a 64-character lowercase SHA-256 revision.
The wheel bundles the v0.2 JSON Schemas, `web-v1` profile, typing marker, and
the pinned glTF validation tool, so validation does not depend on fetching
schemas over the network.

## Status

NeuralStock v0.1.0 is public. The signed `v0.1.0` tag identifies commit
`6a0d8bb5696a24792c606128b016d2fcf3fad6ff`; its
[GitHub Release](https://github.com/Neuralstock/neuralstock/releases/tag/v0.1.0)
is immutable and contains the five attested candidate files plus the
independently read-back R2 retention evidence. The Python package is available
as [`neuralstock==0.1.0`](https://pypi.org/project/neuralstock/0.1.0/) and the
JavaScript client as
[`@neuralstock/client@0.1.0`](https://www.npmjs.com/package/@neuralstock/client/v/0.1.0).

Prospective first-party work operates under the openly unilateral
[founder governance reset and continuing direct-publication lane](https://github.com/Neuralstock/neuralstock/blob/main/docs/FOUNDER-BOOTSTRAP-GOVERNANCE-RESET.md).
Joseph Nordqvist / `@bighippoman` is the accountable controller, CC0 dedicator,
self-assessor, and publisher for qualifying founder-controlled work;
independent human approval is `false`. The lane has no model-count or calendar
limit. It does not open external intake or waive any publication gate, and no
new non-Room-Zero asset may publish until the lane's machine-readable
prerequisites are enforced.

The canonical Room Zero graph is published to the `neuralstock-public`
Cloudflare R2 bucket as asset version 1.0.1 and registry revision
`744accaa3f9efcd053d8e589b2bb7e966753b070004f7c78ef00c3431cbbe391`.
The public artifact origin is `https://assets.neuralstock.ai`, the canonical
contracts use the locked `https://schemas.neuralstock.ai/v0.2/` schema and
profile namespaces, and `r2.dev` access is disabled. The earlier 1.0.0 graph,
revision `a3e851194d092bf1a06452a62ae98ba8687462ea0cbca668a9b9cc2385768523`,
its v0.1 contracts, and its CC0 evidence remain immutable historical records;
they were not overwritten during promotion. See
[the namespace decision](https://github.com/Neuralstock/neuralstock/blob/main/docs/NAMESPACE.md).
Joseph Nordqvist is recorded as the individual CC0 dedicator for every Room
Zero asset, with ownership or control of the inputs and authority to make the
dedication explicitly affirmed. The release includes:

- JSON Schema 2020-12 for the public contract;
- Python for validation, packaging, registry generation, and publishing;
- Blender 4.5 LTS in a pinned OCI image for source generation and export;
- GLB/glTF 2.0 as the runtime contract;
- TypeScript and Three.js for the reference consumer;
- immutable, content-addressed artifacts served directly from Cloudflare R2.

Room Zero contains exactly 15 coordinated assets, including seven bounded
procedural generators. All runtime files pass the Khronos validator without
errors or warnings, all accepted-source rebuilds are byte-reproducible, and
the real-release browser suite passes at desktop and narrow widths.

The v0.1.0 registry is a static downloadable snapshot. D1, Durable Objects,
Queues, Workflows, Vectorize, and public hosted generation are deliberately
deferred until the static pipeline proves useful.

The Cloudflare Pages project `neuralstock` has preview and production
deployments. Its `neuralstock.ai` and `www.neuralstock.ai` custom domains are
active. The reference site gives people a direct GLB, Blender source, and
manifest download for each asset; those downloads come from the R2 origin and
do not pass through Pages or a Worker.

## Development

Prerequisites:

- Python 3.12+
- `uv`
- Node.js 22+ and pnpm 10+
- an OCI runtime for the pinned Blender build

Install and run the fast checks:

```bash
uv sync --extra dev
uv run pytest
uv run ruff check .
pnpm install
pnpm test
```

The root `pnpm test` command runs the fast suites in every checkout. When
`dist/release/registry.json` exists, or `NEURALSTOCK_RELEASE_DIR` points to a
release, it also runs the Room Zero Playwright suite against that real static
release.

Inspect the CLI:

```bash
uv run neuralstock --help
```

Build and verify the complete collection from the versioned accepted sources:

```bash
tools/release-room-zero.sh
```

The optional independent-build gate and its deliberately narrow treatment of
Blender serialization and lossless PNG encoding are documented in
[the reproducibility guide](https://github.com/Neuralstock/neuralstock/blob/main/docs/REPRODUCIBILITY.md).
The end-to-end build, local publication, browser verification, and optional R2
sync are documented in the
[release runbook](https://github.com/Neuralstock/neuralstock/blob/main/docs/RELEASE.md).
The scalable workshop-to-quarantine-to-public-registry process is documented in
the
[asset lifecycle](https://github.com/Neuralstock/neuralstock/blob/main/docs/ASSET-LIFECYCLE.md).

Rollout and operations are governed by the
[governance policy](https://github.com/Neuralstock/neuralstock/blob/main/GOVERNANCE.md),
[rollout plan](https://github.com/Neuralstock/neuralstock/blob/main/docs/ROLLOUT.md),
[GitHub runbook](https://github.com/Neuralstock/neuralstock/blob/main/docs/GITHUB-GOVERNANCE.md),
and [operations runbook](https://github.com/Neuralstock/neuralstock/blob/main/docs/OPERATIONS.md).
The historical, exact v0.1 promotion gates are in the
[release checklist](https://github.com/Neuralstock/neuralstock/blob/main/docs/RELEASE-CHECKLIST-v0.1.md),
with durable evidence recorded under
[`docs/releases/`](https://github.com/Neuralstock/neuralstock/tree/main/docs/releases).

Generated Blender sources belong in `work/`; packaged outputs belong in
`dist/`. Neither directory is committed. Reviewed catalog metadata remains in
Git while content-addressed binaries are published separately.

## Contributing and security

Before proposing an asset or software change, read the
[contribution guide](https://github.com/Neuralstock/neuralstock/blob/main/CONTRIBUTING.md).
Report vulnerabilities through the private process in the
[security policy](https://github.com/Neuralstock/neuralstock/blob/main/SECURITY.md),
not a public issue.

## License

Repository-owned software is MIT licensed. Published asset content is dedicated
under CC0-1.0 and must pass the provenance policy before publication. The
[asset licensing policy](https://github.com/Neuralstock/neuralstock/blob/main/ASSET-LICENSE.md)
defines that boundary precisely; vendored and generated dependencies retain the
terms listed in the
[third-party notices](https://github.com/Neuralstock/neuralstock/blob/main/THIRD_PARTY_NOTICES.md).
