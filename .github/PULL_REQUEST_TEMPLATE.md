## Change type

- [ ] Asset contribution or asset-version update
- [ ] Schema, profile, provenance, or policy change
- [ ] Pipeline, package, or infrastructure change
- [ ] Documentation or other software change

## Summary

Describe the result, the reason for it, and the public behavior that changes.

## Asset contribution details

Complete this section for an asset pull request. Otherwise write “not applicable.”

- Asset reference: `asset_id@version`
- Publication lane: external / `first-party-founder-controlled` / not applicable
- Creation mode: manual Blender / procedural Blender / tool-assisted Blender / not applicable
- Governing policy or decision ID and SHA-256:
- Assessment mode: independent review / founder self-assessment / not applicable
- Independent human review: `true` / `false` / not applicable
- Quarantine upload/submission ID:
- Declared `source.blend` SHA-256:
- Origin: direct original work / separately approved exception
- Included dependencies and evidence:
- Trademarks, distinctive designs, people, or other rights concerns:

### Rights-holder affirmation

- [ ] I am the named rights holder or their authorized representative.
- [ ] The rights holder owns or controls the submitted asset and every bundled
      input, except for dependencies individually disclosed with accepted
      public-domain evidence.
- [ ] I authorize the dedication recorded in `provenance.json` under Creative
      Commons CC0 1.0 Universal.
- [ ] The source hash above identifies the exact bytes covered by this
      affirmation.

The checkboxes support review but do not replace the versioned, identity-bound
attestation required by the contribution pipeline.

## Validation

- [ ] I ran the relevant locked tests described in `CONTRIBUTING.md`.
- [ ] Generated manifests, reports, GLBs, previews, and registry files were not
      edited by hand.
- [ ] Public contract changes include schema fixtures and compatibility notes.
- [ ] New dependencies are locked, licensed, and justified.
- [ ] No credential, private staging URL, personal contact detail, or hostile
      test asset is included in this pull request.

## Assessment notes

Call out manual visual checks, provenance questions, residual risks, and any
follow-up work that is intentionally outside this pull request. Founder-lane
records must state that founder self-assessment is not independent human review.
