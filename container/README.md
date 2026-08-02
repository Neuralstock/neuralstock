# NeuralStock Blender container

The image pins Blender 4.5.12 LTS and verifies Blender's official Linux x64
archive with SHA-256 before installation. It is intentionally `linux/amd64`;
Apple Silicon development hosts must enable Docker's amd64 emulation.

## Locked build inputs

The build does not resolve packages from Ubuntu's moving `noble-updates` or
`noble-security` indexes. Its supply chain is fixed by:

- the Ubuntu 24.04 OCI index digest in `Dockerfile`;
- Dockerfile frontend 1.7 by digest;
- BuildKit v0.30.0 by multi-platform OCI index digest;
- `SOURCE_DATE_EPOCH=1785542400` (2026-08-01T00:00:00Z) for stable image
  configuration and layer timestamps;
- Ubuntu archive snapshot `20260731T000000Z` in `ubuntu.sources`;
- exact direct package versions in `ubuntu-bootstrap.lock`,
  `ubuntu-fetch.lock`, and `ubuntu-runtime.lock`; and
- Blender 4.5.12's official archive SHA-256 in `Dockerfile`.

`image.lock.json` records the independently reproduced runnable manifest and
config digests for these inputs. CI rebuilds from scratch and rejects any
digest or creation-time drift.

## Licensing and corresponding source

The worker is an aggregate image, not an MIT-only artifact. Its OCI label uses
the composite expression documented in
[`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md), and the same notice plus the
repository MIT text are installed in `/usr/share/neuralstock/licenses/`.
Blender's complete bundled license tree and Ubuntu's package copyright notices
remain in their original in-image locations.

The exact Blender 4.5.12 source archive is pinned as
`9cb86825c95e4f0a33bfd41eb574426f2f69aa6c310497e289fdb54cc6482f1b`.
Public image publication must also satisfy the source and notice checklist in
`THIRD_PARTY_NOTICES.md`; in particular, the verified Blender source and any
required Ubuntu package sources must be made available to recipients.

APT resolves transitive dependencies only inside the dated snapshot. The
Dockerfile additionally reads every lock entry back through `dpkg-query` and
fails if the installed version differs. The lock files and source definition
are copied into `/usr/share/neuralstock/container-locks/` in the final image.

The minimal pinned Ubuntu image has the Ubuntu archive signing key but no CA
bundle. The fetch stage therefore disables TLS peer verification only while it
installs the exactly pinned CA bootstrap packages from the signed snapshot.
APT still authenticates the snapshot metadata and package hashes with the
Ubuntu archive key. It then deletes those indexes, performs a fresh update with
normal TLS verification, and uses verified HTTPS for every remaining package
and the Blender download. The runtime stage receives that pinned CA bundle
before making its first, fully verified snapshot request.

This follows Canonical's documented
[Ubuntu snapshot service](https://documentation.ubuntu.com/server/how-to/software/snapshot-service/).
When updating the snapshot, update the three lock files in the same change,
run the no-cache build below, and record the resulting image digest in the
release/build receipt. Retain the built OCI image and mirror every required
binary and source input; the snapshot documentation promises no retention
period.

Build from the repository root:

```sh
docker buildx create \
  --name neuralstock-v01 \
  --driver docker-container \
  --driver-opt image=moby/buildkit:v0.30.0@sha256:0168606be2315b7c807a03b3d8aa79beefdb31c98740cebdffdfeebf31190c9f \
  --bootstrap
docker buildx build \
  --builder neuralstock-v01 \
  --no-cache \
  --provenance=false \
  --build-arg SOURCE_DATE_EPOCH=1785542400 \
  --platform linux/amd64 \
  --file container/Dockerfile \
  --tag neuralstock-blender:4.5.12 \
  --metadata-file work/neuralstock-blender.metadata.json \
  --output type=docker,dest=work/neuralstock-blender.docker.tar,rewrite-timestamp=true,compression=gzip,compression-level=6,oci-mediatypes=false \
  .
docker load --input work/neuralstock-blender.docker.tar
```

Verify the locked identity and runtime after the build:

```sh
docker image inspect neuralstock-blender:4.5.12 \
  --format '{{.Id}} {{.Architecture}} {{index .Config.Labels "org.neuralstock.ubuntu.snapshot"}}'
docker run --rm --platform linux/amd64 \
  --entrypoint /opt/blender/blender \
  neuralstock-blender:4.5.12 --version
```

The Docker archive exporter fixes its media type, gzip level, platform, and
timestamp rewriting behavior while remaining loadable by classic and
containerd-backed Docker Engine stores. `--provenance=false` makes the archive point directly at
the runnable single-platform manifest instead of an attestation index. Release
automation records `containerimage.digest` from the metadata file, loads that
same archive for execution, and checks that the local tag resolves to the same
digest. CI provenance can be published separately when the image is pushed to
an OCI registry.

Generate and build the golden crate in one isolated invocation:

```sh
mkdir -p dist/crate
docker run --rm \
  --platform linux/amd64 \
  --network none \
  --read-only \
  --cap-drop ALL \
  --security-opt no-new-privileges \
  --tmpfs /tmp:rw,nosuid,nodev,size=2g \
  --mount type=bind,src="$PWD/dist/crate",dst=/output \
  neuralstock-blender:4.5.12 \
  build \
  --generate procedural_crate_01 \
  --asset-version 1.0.1 \
  --params '{"width_m":0.8,"height_m":0.55}' \
  --output-dir /output
```

Process an existing source with the same hardening boundary:

```sh
docker run --rm \
  --platform linux/amd64 \
  --network none \
  --read-only \
  --cap-drop ALL \
  --security-opt no-new-privileges \
  --tmpfs /tmp:rw,nosuid,nodev,size=2g \
  --mount type=bind,src="$PWD/work",dst=/input,readonly \
  --mount type=bind,src="$PWD/dist/asset",dst=/output \
  neuralstock-blender:4.5.12 \
  build --source /input/source.blend --output-dir /output
```

Build the complete Room Zero collection with reduced validation previews:

```sh
mkdir -p dist/room-zero
docker run --rm \
  --platform linux/amd64 \
  --network none \
  --read-only \
  --cap-drop ALL \
  --security-opt no-new-privileges \
  --tmpfs /tmp:rw,nosuid,nodev,size=2g \
  --mount type=bind,src="$PWD/dist/room-zero",dst=/output \
  neuralstock-blender:4.5.12 \
  batch --output-dir /output --preview-resolution 192
```

The entrypoint always adds `--background`, `--factory-startup`,
`--disable-autoexec`, and `--python-exit-code 1`. It exposes only
repository-owned scripts; it does not accept an arbitrary Python path.

`--network none`, filesystem limits, CPU/memory limits, and secret isolation
are runtime responsibilities. The image does not claim that a conventional
container alone is a sufficient sandbox for hostile native parser exploits.

To reproduce the collection from accepted sources, mount a tree containing
`<asset-id>/source.blend` read-only and select batch source mode:

```sh
docker run --rm \
  --platform linux/amd64 \
  --network none \
  --read-only \
  --cap-drop ALL \
  --security-opt no-new-privileges \
  --tmpfs /tmp:rw,nosuid,nodev,size=2g \
  --mount type=bind,src="$PWD/assets/room-zero",dst=/input,readonly \
  --mount type=bind,src="$PWD/work/room-zero-reproduced",dst=/output \
  neuralstock-blender:4.5.12 \
  batch --source-root /input --output-dir /output --preview-resolution 192
```
