# Release records

This directory is the durable audit log for public NeuralStock releases. Each
protected Git tag has one Markdown record named after the tag, for example
`v0.1.0.md`. The record is completed from verified workflow and registry
evidence after publication; unknown values remain explicitly `PENDING` rather
than being inferred.

A release record distinguishes four independent version domains:

- the GitHub, Python, and npm package release;
- the immutable JSON Schema and runtime-profile contract;
- each asset collection's version; and
- the registry revision, which is a content-derived SHA-256 value rather than a
  semantic version.

Once a record says `Complete`, published facts and evidence links are
append-only. Correct a mistake in an `Amendments` entry with a timestamp and
reason; never silently replace a source commit, digest, registry revision, or
approval claim. Do not put credentials or private identity evidence here.

Production-workflow success alone cannot make a record complete. A fresh
contract namespace needs an immutable-only Phase A followed by manual OAuth
apply/readback evidence for the schema, profile, and exact snapshot prefixes.
The check-only JSON is uploaded once under its deterministic name to the signed-
tag draft release. A protected finalizer must verify the exact candidate and
evidence set, publish it once with repository release immutability enabled, and
verify GitHub's immutable-release attestation. Phase B must then retrieve, hash,
parse, attest, and candidate-bind that immutable asset before aliases or the
site change. Record the operator, UTC timestamp, both JSON hashes, draft and
finalizer runs, immutable release, asset, and independent Cloudflare dashboard
readback. This gate stays manual because the available bucket-configuration
credential is account-wide and is intentionally not stored in GitHub.

The first record is [`v0.1.0.md`](v0.1.0.md).
