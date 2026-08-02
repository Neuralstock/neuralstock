#!/bin/sh
set -eu

usage() {
  >&2 echo "usage: $0 [--allow-absent] RELEASE_ROOT [SCHEMA_ORIGIN]"
  exit 64
}

allow_absent=false
if [ "${1:-}" = "--allow-absent" ]; then
  allow_absent=true
  shift
fi
[ "$#" -ge 1 ] && [ "$#" -le 2 ] || usage

release_root=$1
origin=${2:-https://schemas.neuralstock.ai}
canonical_origin=https://schemas.neuralstock.ai

[ -d "$release_root" ] || {
  >&2 echo "release root does not exist: $release_root"
  exit 66
}
case "$origin" in
  https://*/* | https://) usage ;;
  https://*) ;;
  http://127.0.0.1:* | http://localhost:*)
    [ "${NEURALSTOCK_ALLOW_INSECURE_TEST_ORIGIN:-}" = 1 ] || usage
    ;;
  *) usage ;;
esac

for command_name in awk cmp curl find grep jq mktemp sha256sum tr wc; do
  command -v "$command_name" >/dev/null 2>&1 || {
    >&2 echo "required command is unavailable: $command_name"
    exit 69
  }
done

release_root=$(CDPATH= cd -- "$release_root" && pwd -P)
temporary_root=$(mktemp -d)
cleanup() {
  rm -rf "$temporary_root"
}
trap cleanup 0 1 2 15

header_value() {
  field=$1
  header_file=$2
  awk -v wanted="$field" '
    tolower($1) == wanted ":" {
      $1 = ""
      sub(/^[[:space:]]+/, "")
      value = tolower($0)
    }
    END { print value }
  ' "$header_file" | tr -d '\r'
}

fail() {
  >&2 echo "$*"
  exit 65
}

probe_file() {
  relative_path=$1
  expected_content_type=$2
  local_path="$release_root/$relative_path"
  label=$(printf '%s' "$relative_path" | tr '/' '_')
  header_path="$temporary_root/$label.headers"
  public_path="$temporary_root/$label"

  [ -f "$local_path" ] && [ ! -L "$local_path" ] || \
    fail "release contract is missing or unsafe: $relative_path"
  http_code=$(curl --silent --show-error \
    --retry 3 \
    --retry-all-errors \
    --dump-header "$header_path" \
    "$origin/$relative_path" \
    --output "$public_path" \
    --write-out '%{http_code}')
  if [ "$http_code" = 404 ]; then
    printf '%s\n' absent
    return
  fi
  [ "$http_code" = 200 ] || fail \
    "public contract returned HTTP $http_code: $relative_path"
  cmp "$local_path" "$public_path" || fail \
    "public contract differs from the candidate bytes: $relative_path"

  cache_control=$(header_value cache-control "$header_path" | tr -d ' ')
  [ "$cache_control" = "public,max-age=31536000,immutable" ] || {
    fail "public contract has the wrong cache policy: $relative_path"
  }
  actual_content_type=$(header_value content-type "$header_path")
  case "$actual_content_type" in
    "$expected_content_type" | "$expected_content_type;"*) ;;
    *)
      fail "public contract has the wrong content type: $relative_path"
      ;;
  esac
  printf '%s\n' present
}

license_digest=db925e3df4ed5c6de89e903dd30ecb004f6ba4ae63d9aa98d8570ef50be87200
schema_license_path=v0.2/LICENSE
profile_license_path=profiles/v0.2/LICENSE
for license_path in "$schema_license_path" "$profile_license_path"; do
  [ -f "$release_root/$license_path" ] && [ ! -L "$release_root/$license_path" ] || {
    >&2 echo "release license companion is missing or unsafe: $license_path"
    exit 65
  }
  [ "$(sha256sum "$release_root/$license_path" | awk '{ print $1 }')" = "$license_digest" ] || {
    >&2 echo "release license companion has the wrong SHA-256: $license_path"
    exit 65
  }
done
cmp "$release_root/$schema_license_path" "$release_root/$profile_license_path"

verify_notice() {
  document_path=$1
  expected_license_uri=$2
  jq --exit-status \
    --arg copyright 'Copyright (c) 2026 NeuralStock contributors' \
    --arg digest "$license_digest" \
    --arg license_uri "$expected_license_uri" \
    --rawfile license_text "$release_root/$schema_license_path" \
    '."x-neuralstock-document-license" == {
      "spdx_id": "MIT",
      "copyright": $copyright,
      "license_uri": $license_uri,
      "license_sha256": $digest,
      "license_text": $license_text
    }' "$release_root/$document_path" >/dev/null || {
      >&2 echo "release contract has incomplete MIT license metadata: $document_path"
      exit 65
    }
}

expected_schema_names="
asset.intent.schema.json
asset.schema.json
build-receipt.schema.json
common.schema.json
discovery.schema.json
inspection.schema.json
profile.schema.json
provenance.schema.json
registry.schema.json
"
[ -d "$release_root/v0.2" ] || {
  >&2 echo "release is missing its canonical v0.2 schema directory"
  exit 65
}
schema_count=$(find "$release_root/v0.2" -maxdepth 1 -type f -name '*.schema.json' | wc -l | tr -d ' ')
[ "$schema_count" -eq 9 ] || {
  >&2 echo "release must contain exactly nine canonical v0.2 schemas"
  exit 65
}

printf '%s\n' "$expected_schema_names" | while IFS= read -r schema_name; do
  [ -n "$schema_name" ] || continue
  schema_path="v0.2/$schema_name"
  expected_id="$canonical_origin/$schema_path"
  [ "$(jq -er '."$id"' "$release_root/$schema_path")" = "$expected_id" ] || {
    >&2 echo "release schema has the wrong \$id: $schema_path"
    exit 65
  }
  verify_notice "$schema_path" "$canonical_origin/v0.2/LICENSE"
done

profile_path=profiles/v0.2/web-v1.json
[ "$(jq -er '."$schema"' "$release_root/$profile_path")" = \
  "$canonical_origin/v0.2/profile.schema.json" ] || {
  >&2 echo "release profile has the wrong \$schema"
  exit 65
}
verify_notice "$profile_path" "$canonical_origin/profiles/v0.2/LICENSE"

contract_manifest="$temporary_root/contracts"
{
  printf '%s\n' "$expected_schema_names" | while IFS= read -r schema_name; do
    [ -n "$schema_name" ] || continue
    printf 'v0.2/%s|application/schema+json\n' "$schema_name"
  done
  printf '%s\n' \
    "$schema_license_path|text/plain" \
    "$profile_path|application/json" \
    "$profile_license_path|text/plain"
} >"$contract_manifest"

probe_results="$temporary_root/probe-results"
while IFS='|' read -r contract_path content_type; do
  probe_file "$contract_path" "$content_type"
done <"$contract_manifest" >"$probe_results"

contract_count=$(wc -l <"$contract_manifest" | tr -d ' ')
present_count=$(grep -c '^present$' "$probe_results" || true)
absent_count=$(grep -c '^absent$' "$probe_results" || true)
[ "$((present_count + absent_count))" -eq "$contract_count" ] || \
  fail "contract-origin probe produced an incomplete result"

if [ "$absent_count" -eq "$contract_count" ]; then
  [ "$allow_absent" = true ] || \
    fail "canonical v0.2 contract namespace is absent; bootstrap mode is required"
  echo "Verified locally coherent fresh v0.2 contract namespace at $origin"
  exit 0
fi
[ "$present_count" -eq "$contract_count" ] || fail \
  "canonical v0.2 contract namespace is partially published ($present_count present, $absent_count absent)"

echo "Verified canonical contract at $origin"
