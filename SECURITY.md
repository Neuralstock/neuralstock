# Security policy

NeuralStock treats every contributed Blender file, texture, archive, and
metadata document as untrusted input. Passing a license review does not make a
file safe to execute.

## Report a vulnerability

When this repository is hosted on GitHub, report vulnerabilities with a
private GitHub security advisory at
<https://github.com/Neuralstock/neuralstock/security/advisories/new>. Do not open a public issue for a flaw that
could execute contributor-controlled code, expose build credentials, overwrite
published objects, bypass provenance checks, or serve different bytes for an
existing asset version.

Include the affected commit or version, a minimal reproduction, expected
impact, and any known mitigation. Avoid attaching hostile `.blend` files to a
public issue.

The initial response target is two business days. A credible report involving
credential exposure, contributor-controlled execution, or mutable-registry
integrity stops publication until triage. This target is not a bounty promise.

## Build boundary

The v0.1 worker applies these controls:

- Blender is pinned and installed from an archive verified by SHA-256.
- Builds use `--background`, `--factory-startup`, `--disable-autoexec`, and a
  nonzero Python failure exit code.
- The container entrypoint can invoke only repository-owned scripts; it does
  not accept an arbitrary Python path.
- The worker runs as a non-root user with a read-only root filesystem, dropped
  Linux capabilities, `no-new-privileges`, and no network in the documented
  invocation.
- Sources and outputs are separate mounts. Production credentials never enter
  the Blender container.
- The release runner enforces four CPUs, 12 GiB memory, 1,024 PIDs, a 2 GiB
  temporary filesystem, a 512 MiB output filesystem, and a 30-minute
  wall-clock limit for each Room Zero batch.
- Linked libraries, missing external resources, embedded code, and undeclared
  parameter hooks fail the `web-v1` profile.
- The outer process validates GLB bytes, schemas, hashes, budgets, provenance,
  and build receipts before publication.

A conventional container is a risk-reduction boundary, not a claim of perfect
isolation against a native Blender parser exploit. Public ingestion at scale
must use a VM-isolated sandbox or equivalent hardened job runtime, enforce CPU,
memory, disk, output, and wall-clock limits, and keep staging, quarantine, and
published storage separate.

Pull-request CI uses an ephemeral GitHub-hosted runner, read-only repository
permission, pinned Actions, and no production secrets. External asset ingestion
must additionally use a protected, digest-pinned toolchain rather than pipeline
code modified by the same asset pull request. `pull_request_target` must never
open or build contributor content.

## Publication boundary

Content-addressed objects and `asset-id@version` manifests are immutable.
Conditional writes must reject replacement bytes. The mutable registry aliases
are written only after all referenced objects, manifests, validation reports,
and the immutable registry snapshot are present.

Clients must verify SHA-256 and byte length when mirroring. A rights or security
problem is recorded as a withdrawal; an already published version is never
silently replaced.

## Secrets

Do not commit R2 keys, account IDs tied to credentials, staging URLs, GitHub
tokens, or local environment files. Use a write-scoped publication identity
separate from read-only serving and administrative bucket configuration.

Release candidates and software package archives carry SHA-256 checksum files
and GitHub build-provenance attestations. Production deployment consumes a
specific candidate workflow run and verifies its source commit, version,
registry revision, archive graph, and checksums before any credentialed write.
See [`docs/OPERATIONS.md`](docs/OPERATIONS.md).
