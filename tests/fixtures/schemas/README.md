# Schema fixtures

Every JSON fixture carries the canonical `$schema` URI. Test code can map the
last URI segment to the matching file in `schemas/` and register
`common.schema.json` under its `$id`; validation must not fetch the network.

Files under `valid/` must pass. Files under `invalid/` are otherwise plausible
documents with one contract violation named in the filename. Semantic checks
that JSON Schema cannot express are documented in `schemas/README.md` and
should have separate unit cases in the validator package.
