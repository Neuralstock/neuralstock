#!/bin/sh
set -eu

usage() {
  >&2 echo "usage: $0 [EXPECTED_REGISTRY_REVISION [RELEASE_ROOT]]"
  exit 64
}

[ "$#" -le 2 ] || usage
expected_revision=${1:-}
release_root=${2:-}

asset_origin=${NEURALSTOCK_VERIFY_ASSET_ORIGIN:-https://assets.neuralstock.ai}
schema_origin=${NEURALSTOCK_VERIFY_SCHEMA_ORIGIN:-https://schemas.neuralstock.ai}
site_origin=${NEURALSTOCK_VERIFY_SITE_ORIGIN:-https://neuralstock.ai}
www_origin=${NEURALSTOCK_VERIFY_WWW_ORIGIN:-https://www.neuralstock.ai}
cors_origin=${NEURALSTOCK_VERIFY_CORS_ORIGIN:-https://neuralstock.ai}
canonical_schema_origin=https://schemas.neuralstock.ai
alias_cache_control=public,max-age=60,must-revalidate
immutable_cache_control=public,max-age=31536000,immutable
discovery_cache_control=public,max-age=300,stale-while-revalidate=86400
verification_attempts=${NEURALSTOCK_VERIFY_ATTEMPTS:-1}
verification_delay=${NEURALSTOCK_VERIFY_DELAY_SECONDS:-5}

if [ -n "$expected_revision" ] && ! printf '%s\n' "$expected_revision" \
  | grep -Eq '^[0-9a-f]{64}$'; then
  usage
fi
if ! printf '%s\n' "$verification_attempts" | grep -Eq '^[1-9][0-9]*$'; then
  >&2 echo "NEURALSTOCK_VERIFY_ATTEMPTS must be a positive integer"
  exit 64
fi
if ! printf '%s\n' "$verification_delay" | grep -Eq '^[0-9]+$'; then
  >&2 echo "NEURALSTOCK_VERIFY_DELAY_SECONDS must be a non-negative integer"
  exit 64
fi

for command_name in awk cmp curl dirname grep head jq mktemp python3 sha256sum sleep tr wc; do
  command -v "$command_name" >/dev/null 2>&1 || {
    >&2 echo "required command is unavailable: $command_name"
    exit 69
  }
done

script_directory=$(CDPATH= cd -- "$(dirname "$0")" && pwd -P)
project_root=$(CDPATH= cd -- "$script_directory/.." && pwd -P)
discovery_source="$project_root/discovery/neuralstock.json"
license_source="$project_root/LICENSE"
sitemap_source="$project_root/examples/room-zero/public/sitemap.xml"
[ -f "$discovery_source" ] && [ -f "$license_source" ] && [ -f "$sitemap_source" ] || {
  >&2 echo "production verification must run from a complete NeuralStock checkout"
  exit 66
}
if [ -n "$release_root" ]; then
  [ -n "$expected_revision" ] || usage
  [ -d "$release_root" ] || {
    >&2 echo "release root does not exist: $release_root"
    exit 66
  }
  release_root=$(CDPATH= cd -- "$release_root" && pwd -P)
  [ -f "$release_root/registry.json" ] || {
    >&2 echo "release root does not contain registry.json"
    exit 66
  }
fi

temporary_root=$(mktemp -d)
cleanup() {
  rm -rf "$temporary_root"
}
trap cleanup 0 1 2 15

fail() {
  >&2 echo "$*"
  exit 65
}

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

header_value_raw() {
  field=$1
  header_file=$2
  awk -v wanted="$field" '
    tolower($1) == wanted ":" {
      $1 = ""
      sub(/^[[:space:]]+/, "")
      value = $0
    }
    END { print value }
  ' "$header_file" | tr -d '\r'
}

require_header() {
  field=$1
  expected=$2
  header_file=$3
  label=$4
  actual=$(header_value "$field" "$header_file" | tr -d ' ')
  [ "$actual" = "$expected" ] || {
    fail "$label has $field '$actual', expected '$expected'"
  }
}

require_content_type() {
  expected=$1
  header_file=$2
  label=$3
  actual=$(header_value content-type "$header_file")
  case "$actual" in
    "$expected" | "$expected;"*) ;;
    *) fail "$label has content-type '$actual', expected '$expected'" ;;
  esac
}

require_cors() {
  header_file=$1
  label=$2
  require_header access-control-allow-origin '*' "$header_file" "$label"
}

require_exposed_header() {
  wanted=$1
  header_file=$2
  label=$3
  exposed=$(header_value access-control-expose-headers "$header_file" | tr -d ' ')
  case ",$exposed," in
    *",$wanted,"*) ;;
    *) fail "$label does not expose the $wanted response header through CORS" ;;
  esac
}

require_document_license() {
  document_file=$1
  expected_uri=$2
  label=$3
  jq --exit-status \
    --arg copyright 'Copyright (c) 2026 NeuralStock contributors' \
    --arg license_uri "$expected_uri" \
    --arg license_sha256 db925e3df4ed5c6de89e903dd30ecb004f6ba4ae63d9aa98d8570ef50be87200 \
    --rawfile license_text "$license_source" \
    '."x-neuralstock-document-license" == {
      "spdx_id": "MIT",
      "copyright": $copyright,
      "license_uri": $license_uri,
      "license_sha256": $license_sha256,
      "license_text": $license_text
    }' "$document_file" >/dev/null || {
      fail "$label has incomplete MIT license metadata"
    }
}

fetch() {
  url=$1
  header_file=$2
  output_file=$3
  curl --fail --silent --show-error \
    --retry 4 \
    --retry-all-errors \
    --connect-timeout 15 \
    --max-time 300 \
    --header "Origin: $cors_origin" \
    --dump-header "$header_file" \
    --output "$output_file" \
    "$url"
}

fetch_exact_with_retry() {
  url=$1
  expected_file=$2
  header_file=$3
  output_file=$4
  mismatch_message=$5
  exact_attempt=1
  while :; do
    fetch "$url" "$header_file" "$output_file"
    if cmp "$expected_file" "$output_file" >/dev/null 2>&1; then
      return
    fi
    if [ "$exact_attempt" -ge "$verification_attempts" ]; then
      cmp "$expected_file" "$output_file" || true
      fail "$mismatch_message"
    fi
    exact_attempt=$((exact_attempt + 1))
    sleep "$verification_delay"
  done
}

verify_descriptor() {
  file=$1
  expected_sha=$2
  expected_bytes=$3
  label=$4
  actual_sha=$(sha256sum "$file" | awk '{print $1}')
  actual_bytes=$(wc -c <"$file" | tr -d ' ')
  [ "$actual_sha" = "$expected_sha" ] || {
    fail "$label SHA-256 mismatch: expected $expected_sha, got $actual_sha"
  }
  [ "$actual_bytes" = "$expected_bytes" ] || {
    fail "$label byte-count mismatch: expected $expected_bytes, got $actual_bytes"
  }
}

require_safe_uri() {
  uri=$1
  label=$2
  case "$uri" in
    /*) ;;
    *) fail "$label URI is not root-relative: $uri" ;;
  esac
  case "$uri" in
    //* | *\\* | */../* | */.. | *'/./'*) fail "$label URI is unsafe: $uri" ;;
  esac
}

# The www host is canonicalized by a zone-level Single Redirect. Pages does not
# support host-level rules in _redirects, so verify status, path, and query here.
redirect_path=/asset/neuralstock-redirect-probe/0.0.0
redirect_query=neuralstock_redirect_probe=1
redirect_status=$(curl --fail --silent --show-error \
  --retry 4 \
  --retry-all-errors \
  --connect-timeout 15 \
  --max-time 60 \
  --dump-header "$temporary_root/redirect.headers" \
  --output "$temporary_root/redirect.body" \
  --write-out '%{http_code}' \
  "$www_origin$redirect_path?$redirect_query")
[ "$redirect_status" = 301 ] || {
  fail "www canonical redirect returned HTTP $redirect_status, expected 301"
}
redirect_location=$(header_value_raw location "$temporary_root/redirect.headers")
expected_location="$site_origin$redirect_path?$redirect_query"
[ "$redirect_location" = "$expected_location" ] || {
  fail "www canonical redirect location is '$redirect_location', expected '$expected_location'"
}

fetch \
  "$site_origin/" \
  "$temporary_root/site.headers" \
  "$temporary_root/site.html"
require_content_type text/html "$temporary_root/site.headers" "site root"
grep --fixed-strings '<title>NeuralStock' "$temporary_root/site.html" >/dev/null || {
  fail "site root does not contain the NeuralStock application shell"
}

fetch_exact_with_retry \
  "$site_origin/.well-known/neuralstock.json" \
  "$discovery_source" \
  "$temporary_root/discovery.headers" \
  "$temporary_root/discovery.json" \
  "live machine discovery differs from discovery/neuralstock.json"
require_content_type application/json "$temporary_root/discovery.headers" \
  "machine discovery"
require_header cache-control "$discovery_cache_control" \
  "$temporary_root/discovery.headers" "machine discovery"
require_cors "$temporary_root/discovery.headers" "machine discovery"

registry_attempt=1
while :; do
  fetch \
    "$asset_origin/registry.json" \
    "$temporary_root/registry.headers" \
    "$temporary_root/registry.json"
  live_revision=$(jq -r '.revision // empty' "$temporary_root/registry.json" 2>/dev/null || true)
  if [ -z "$expected_revision" ] || [ "$live_revision" = "$expected_revision" ]; then
    break
  fi
  [ "$registry_attempt" -lt "$verification_attempts" ] || {
    fail "live registry revision is $live_revision, expected $expected_revision"
  }
  registry_attempt=$((registry_attempt + 1))
  sleep "$verification_delay"
done

revision=$(jq -er '.revision | select(test("^[0-9a-f]{64}$"))' \
  "$temporary_root/registry.json")
entries=$(jq -er '.entries | length | select(. > 0)' \
  "$temporary_root/registry.json")
calculated_revision=$(python3 - "$temporary_root/registry.json" <<'PY'
import hashlib
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    registry = json.load(handle, parse_constant=lambda value: (_ for _ in ()).throw(
        ValueError(f"non-finite JSON number: {value}")
    ))
payload = {
    "generated_at": registry["generated_at"],
    "profiles": registry["profiles"],
    "entries": registry["entries"],
    "aliases": registry["aliases"],
    "withdrawals": registry["withdrawals"],
}
canonical = json.dumps(
    payload,
    ensure_ascii=False,
    allow_nan=False,
    sort_keys=True,
    separators=(",", ":"),
).encode("utf-8")
print(hashlib.sha256(canonical).hexdigest())
PY
)
[ "$calculated_revision" = "$revision" ] || {
  fail "registry semantic revision mismatch: declared $revision, calculated $calculated_revision"
}
[ -z "$expected_revision" ] || [ "$revision" = "$expected_revision" ] || {
  fail "live registry revision is $revision, expected $expected_revision"
}
[ -z "$release_root" ] || cmp \
  "$release_root/registry.json" \
  "$temporary_root/registry.json" || {
  fail "live registry bytes differ from the verified release candidate"
}
require_content_type application/json "$temporary_root/registry.headers" "registry alias"
require_header cache-control "$alias_cache_control" \
  "$temporary_root/registry.headers" "registry alias"
require_cors "$temporary_root/registry.headers" "registry alias"

fetch \
  "$asset_origin/snapshots/latest.json" \
  "$temporary_root/latest.headers" \
  "$temporary_root/latest.json"
cmp "$temporary_root/registry.json" "$temporary_root/latest.json" || {
  fail "registry.json and snapshots/latest.json differ"
}
require_content_type application/json "$temporary_root/latest.headers" \
  "latest snapshot alias"
require_header cache-control "$alias_cache_control" \
  "$temporary_root/latest.headers" "latest snapshot alias"
require_cors "$temporary_root/latest.headers" "latest snapshot alias"

fetch \
  "$asset_origin/snapshots/$revision/registry.json" \
  "$temporary_root/snapshot.headers" \
  "$temporary_root/snapshot.json"
cmp "$temporary_root/registry.json" "$temporary_root/snapshot.json" || {
  fail "mutable registry aliases differ from immutable revision snapshot $revision"
}
require_content_type application/json "$temporary_root/snapshot.headers" \
  "immutable revision snapshot"
require_header cache-control "$immutable_cache_control" \
  "$temporary_root/snapshot.headers" "immutable revision snapshot"
require_cors "$temporary_root/snapshot.headers" "immutable revision snapshot"

fetch_exact_with_retry \
  "$site_origin/sitemap.xml" \
  "$sitemap_source" \
  "$temporary_root/sitemap.headers" \
  "$temporary_root/sitemap.xml" \
  "live sitemap differs from examples/room-zero/public/sitemap.xml"
sitemap_content_type=$(header_value content-type "$temporary_root/sitemap.headers")
case "$sitemap_content_type" in
  application/xml | application/xml\;* | text/xml | text/xml\;*) ;;
  *) fail "sitemap has unexpected content-type '$sitemap_content_type'" ;;
esac
python3 - "$temporary_root/registry.json" "$temporary_root/sitemap.xml" <<'PY'
import json
import sys
import urllib.parse
import xml.etree.ElementTree as ET

with open(sys.argv[1], encoding="utf-8") as handle:
    registry = json.load(handle)
locations = [
    element.text
    for element in ET.parse(sys.argv[2]).getroot().findall(
        "{http://www.sitemaps.org/schemas/sitemap/0.9}url/"
        "{http://www.sitemaps.org/schemas/sitemap/0.9}loc"
    )
]
safe = "-_.!~*'()"
expected = ["https://neuralstock.ai/"]
expected.extend(
    "https://neuralstock.ai/asset/"
    + urllib.parse.quote(entry["asset"]["id"], safe=safe)
    + "/"
    + urllib.parse.quote(entry["asset"]["version"], safe=safe)
    for entry in registry["entries"]
)
if len(locations) != len(set(locations)):
    raise SystemExit("sitemap contains duplicate URLs")
if set(locations) != set(expected):
    missing = sorted(set(expected) - set(locations))
    extra = sorted(set(locations) - set(expected))
    raise SystemExit(f"sitemap/registry mismatch; missing={missing!r}, extra={extra!r}")
PY

asset_path=$(python3 - "$temporary_root/registry.json" <<'PY'
import json
import sys
import urllib.parse

with open(sys.argv[1], encoding="utf-8") as handle:
    entry = json.load(handle)["entries"][0]
safe = "-_.!~*'()"
print(
    "/asset/"
    + urllib.parse.quote(entry["asset"]["id"], safe=safe)
    + "/"
    + urllib.parse.quote(entry["asset"]["version"], safe=safe)
)
PY
)
asset_route_status=$(curl --fail --silent --show-error \
  --retry 4 \
  --retry-all-errors \
  --connect-timeout 15 \
  --max-time 60 \
  --dump-header "$temporary_root/asset-route.headers" \
  --output "$temporary_root/asset-route.html" \
  --write-out '%{http_code}' \
  "$site_origin$asset_path")
[ "$asset_route_status" = 200 ] || {
  fail "stable asset route $asset_path returned HTTP $asset_route_status"
}
require_content_type text/html "$temporary_root/asset-route.headers" \
  "stable asset route"
grep --fixed-strings '<title>NeuralStock' "$temporary_root/asset-route.html" >/dev/null || {
  fail "stable asset route $asset_path did not return the NeuralStock application shell"
}

manifest_uri=$(jq -er '.entries[0].manifest.uri' "$temporary_root/registry.json")
manifest_sha=$(jq -er '.entries[0].manifest.sha256' "$temporary_root/registry.json")
manifest_bytes=$(jq -er '.entries[0].manifest.bytes' "$temporary_root/registry.json")
require_safe_uri "$manifest_uri" "manifest"
fetch \
  "$asset_origin$manifest_uri" \
  "$temporary_root/manifest.headers" \
  "$temporary_root/manifest.json"
verify_descriptor "$temporary_root/manifest.json" "$manifest_sha" "$manifest_bytes" \
  "version manifest"
require_content_type application/json "$temporary_root/manifest.headers" \
  "version manifest"
require_header cache-control "$immutable_cache_control" \
  "$temporary_root/manifest.headers" "version manifest"
require_cors "$temporary_root/manifest.headers" "version manifest"
jq -e --slurpfile registry "$temporary_root/registry.json" \
  '.id == $registry[0].entries[0].asset.id
    and .version == $registry[0].entries[0].asset.version' \
  "$temporary_root/manifest.json" >/dev/null || {
  fail "version manifest identity differs from its registry entry"
}

for role in runtime source; do
  uri=$(jq -er --arg role "$role" '.artifacts[$role].uri' \
    "$temporary_root/manifest.json")
  sha=$(jq -er --arg role "$role" '.artifacts[$role].sha256' \
    "$temporary_root/manifest.json")
  bytes=$(jq -er --arg role "$role" '.artifacts[$role].bytes' \
    "$temporary_root/manifest.json")
  media_type=$(jq -er --arg role "$role" '.artifacts[$role].media_type' \
    "$temporary_root/manifest.json")
  require_safe_uri "$uri" "$role artifact"
  fetch \
    "$asset_origin$uri" \
    "$temporary_root/$role.headers" \
    "$temporary_root/$role.bin"
  verify_descriptor "$temporary_root/$role.bin" "$sha" "$bytes" "$role artifact"
  require_content_type "$media_type" "$temporary_root/$role.headers" "$role artifact"
  require_header cache-control "$immutable_cache_control" \
    "$temporary_root/$role.headers" "$role artifact"
  require_header accept-ranges bytes "$temporary_root/$role.headers" "$role artifact"
  require_cors "$temporary_root/$role.headers" "$role artifact"
  for exposed_header in accept-ranges cache-control content-length content-range content-type; do
    require_exposed_header "$exposed_header" "$temporary_root/$role.headers" \
      "$role artifact"
  done
done

runtime_uri=$(jq -er '.artifacts.runtime.uri' "$temporary_root/manifest.json")
runtime_bytes=$(jq -er '.artifacts.runtime.bytes' "$temporary_root/manifest.json")
range_last=1023
[ "$runtime_bytes" -gt "$range_last" ] || range_last=$((runtime_bytes - 1))
[ "$range_last" -ge 0 ] || fail "runtime artifact is empty"
range_status=$(curl --silent --show-error \
  --retry 4 \
  --retry-all-errors \
  --connect-timeout 15 \
  --max-time 120 \
  --header "Origin: $cors_origin" \
  --header "Range: bytes=0-$range_last" \
  --dump-header "$temporary_root/range.headers" \
  --output "$temporary_root/range.bin" \
  --write-out '%{http_code}' \
  "$asset_origin$runtime_uri")
[ "$range_status" = 206 ] || {
  fail "runtime byte-range request returned HTTP $range_status, expected 206"
}
range_bytes=$((range_last + 1))
[ "$(wc -c <"$temporary_root/range.bin" | tr -d ' ')" = "$range_bytes" ] || {
  fail "runtime byte-range response has the wrong byte count"
}
require_header content-range "bytes0-$range_last/$runtime_bytes" \
  "$temporary_root/range.headers" "runtime byte-range response"
require_header cache-control "$immutable_cache_control" \
  "$temporary_root/range.headers" "runtime byte-range response"
# RFC 9110 defines Accept-Ranges as advisory. Cloudflare R2 advertises it on
# the full response but can omit it from the self-describing 206 response.
require_content_type model/gltf-binary "$temporary_root/range.headers" \
  "runtime byte-range response"
require_cors "$temporary_root/range.headers" "runtime byte-range response"
head -c "$range_bytes" "$temporary_root/runtime.bin" \
  >"$temporary_root/range.expected"
cmp "$temporary_root/range.expected" "$temporary_root/range.bin" || {
  fail "runtime byte-range content differs from the verified full artifact"
}

license_sha256=db925e3df4ed5c6de89e903dd30ecb004f6ba4ae63d9aa98d8570ef50be87200
[ "$(sha256sum "$license_source" | awk '{print $1}')" = "$license_sha256" ] || {
  fail "repository MIT license has changed without updating the canonical contract policy"
}
if [ -n "$release_root" ]; then
  cmp "$license_source" "$release_root/v0.2/LICENSE" || {
    fail "release schema license companion differs from the repository MIT license"
  }
  cmp "$license_source" "$release_root/profiles/v0.2/LICENSE" || {
    fail "release profile license companion differs from the repository MIT license"
  }
fi

fetch \
  "$schema_origin/v0.2/LICENSE" \
  "$temporary_root/schema-license.headers" \
  "$temporary_root/schema.LICENSE"
cmp "$license_source" "$temporary_root/schema.LICENSE" || {
  fail "canonical schema license companion differs from the repository MIT license"
}
require_content_type text/plain "$temporary_root/schema-license.headers" \
  "canonical schema license"
require_header cache-control "$immutable_cache_control" \
  "$temporary_root/schema-license.headers" "canonical schema license"
require_cors "$temporary_root/schema-license.headers" "canonical schema license"

fetch \
  "$schema_origin/profiles/v0.2/LICENSE" \
  "$temporary_root/profile-license.headers" \
  "$temporary_root/profile.LICENSE"
cmp "$license_source" "$temporary_root/profile.LICENSE" || {
  fail "canonical profile license companion differs from the repository MIT license"
}
require_content_type text/plain "$temporary_root/profile-license.headers" \
  "canonical profile license"
require_header cache-control "$immutable_cache_control" \
  "$temporary_root/profile-license.headers" "canonical profile license"
require_cors "$temporary_root/profile-license.headers" "canonical profile license"

fetch \
  "$schema_origin/v0.2/common.schema.json" \
  "$temporary_root/schema.headers" \
  "$temporary_root/common.schema.json"
[ "$(jq -er '."$id"' "$temporary_root/common.schema.json")" = \
  "$canonical_schema_origin/v0.2/common.schema.json" ] || {
  fail "canonical common schema declares the wrong \$id"
}
require_document_license \
  "$temporary_root/common.schema.json" \
  "$canonical_schema_origin/v0.2/LICENSE" \
  "canonical common schema"
require_content_type application/schema+json "$temporary_root/schema.headers" \
  "canonical common schema"
require_header cache-control "$immutable_cache_control" \
  "$temporary_root/schema.headers" "canonical common schema"
require_cors "$temporary_root/schema.headers" "canonical common schema"

fetch \
  "$schema_origin/profiles/v0.2/web-v1.json" \
  "$temporary_root/profile.headers" \
  "$temporary_root/web-v1.json"
[ "$(jq -er '."$schema"' "$temporary_root/web-v1.json")" = \
  "$canonical_schema_origin/v0.2/profile.schema.json" ] || {
  fail "canonical web-v1 profile declares the wrong \$schema"
}
require_document_license \
  "$temporary_root/web-v1.json" \
  "$canonical_schema_origin/profiles/v0.2/LICENSE" \
  "canonical web-v1 profile"
require_content_type application/json "$temporary_root/profile.headers" \
  "canonical web-v1 profile"
require_header cache-control "$immutable_cache_control" \
  "$temporary_root/profile.headers" "canonical web-v1 profile"
require_cors "$temporary_root/profile.headers" "canonical web-v1 profile"

echo "Verified NeuralStock production revision $revision ($entries assets)"
if [ -n "${GITHUB_STEP_SUMMARY:-}" ]; then
  {
    echo "### NeuralStock production health"
    echo
    echo "- Registry revision: \`$revision\`"
    echo "- Registry entries: $entries"
    echo "- www-to-apex 301 with path/query preservation: verified"
    echo "- Machine discovery, sitemap, and stable asset route: verified"
    echo "- Mutable aliases and immutable revision snapshot: byte-identical"
    echo "- Registry semantic revision: verified"
    echo "- Manifest, GLB, Blender source, CORS, cache, and byte ranges: verified"
    echo "- Canonical v0.2 schema/profile origin and MIT license companions: verified"
  } >>"$GITHUB_STEP_SUMMARY"
fi
