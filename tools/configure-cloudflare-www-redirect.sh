#!/bin/sh
set -eu

canonical_zone=neuralstock.ai
redirect_ref=neuralstock_www_to_apex
redirect_phase=http_request_dynamic_redirect
source_expression='http.host eq "www.neuralstock.ai"'
target_expression='concat("https://neuralstock.ai", http.request.uri.path)'
api_origin=https://api.cloudflare.com/client/v4

for command_name in curl grep jq mktemp; do
  command -v "$command_name" >/dev/null 2>&1 || {
    >&2 echo "required command is unavailable: $command_name"
    exit 69
  }
done

: "${CLOUDFLARE_REDIRECT_API_TOKEN:?set a token with Zone Read and Dynamic URL Redirects Write}"
: "${NEURALSTOCK_CLOUDFLARE_ZONE_ID:?set the neuralstock.ai Cloudflare zone ID}"

if ! printf '%s\n' "$NEURALSTOCK_CLOUDFLARE_ZONE_ID" \
  | grep -Eq '^[0-9a-f]{32}$'; then
  >&2 echo "NEURALSTOCK_CLOUDFLARE_ZONE_ID must be a 32-character lowercase hexadecimal ID"
  exit 65
fi

temporary_root=$(mktemp -d)
cleanup() {
  rm -rf "$temporary_root"
}
trap cleanup 0 1 2 15

api_request() {
  method=$1
  url=$2
  output=$3
  payload=${4:-}
  if [ -n "$payload" ]; then
    curl --silent --show-error \
      --retry 3 \
      --retry-all-errors \
      --request "$method" \
      --header "Authorization: Bearer $CLOUDFLARE_REDIRECT_API_TOKEN" \
      --header 'Content-Type: application/json' \
      --data-binary "@$payload" \
      --output "$output" \
      --write-out '%{http_code}' \
      "$url"
  else
    curl --silent --show-error \
      --retry 3 \
      --retry-all-errors \
      --request "$method" \
      --header "Authorization: Bearer $CLOUDFLARE_REDIRECT_API_TOKEN" \
      --output "$output" \
      --write-out '%{http_code}' \
      "$url"
  fi
}

require_success() {
  status=$1
  response=$2
  operation=$3
  case "$status" in
    2??) ;;
    *)
      >&2 echo "$operation failed with HTTP $status"
      jq -r '.errors[]?.message // empty' "$response" >&2 || true
      exit 65
      ;;
  esac
  jq -e '.success == true' "$response" >/dev/null || {
    >&2 echo "$operation returned an unsuccessful Cloudflare response"
    jq -r '.errors[]?.message // empty' "$response" >&2 || true
    exit 65
  }
}

zone_url="$api_origin/zones/$NEURALSTOCK_CLOUDFLARE_ZONE_ID"
zone_status=$(api_request GET "$zone_url" "$temporary_root/zone.json")
require_success "$zone_status" "$temporary_root/zone.json" "zone identity lookup"
jq -e --arg zone "$canonical_zone" \
  '.result.name == $zone and .result.status == "active"' \
  "$temporary_root/zone.json" >/dev/null || {
  >&2 echo "the supplied zone ID is not the active $canonical_zone zone"
  exit 65
}

jq -n \
  --arg ref "$redirect_ref" \
  --arg source_expression "$source_expression" \
  --arg target_expression "$target_expression" \
  '{
    ref: $ref,
    description: "Canonicalize www.neuralstock.ai to neuralstock.ai",
    expression: $source_expression,
    action: "redirect",
    action_parameters: {
      from_value: {
        target_url: {expression: $target_expression},
        status_code: 301,
        preserve_query_string: true
      }
    },
    enabled: true
  }' >"$temporary_root/rule.json"

phase_url="$zone_url/rulesets/phases/$redirect_phase/entrypoint"
phase_status=$(api_request GET "$phase_url" "$temporary_root/phase.json")
case "$phase_status" in
  200)
    jq -e '.success == true and (.result.id | type == "string")' \
      "$temporary_root/phase.json" >/dev/null || {
      >&2 echo "Cloudflare returned a malformed redirect phase entry point"
      exit 65
    }
    ruleset_id=$(jq -er '.result.id' "$temporary_root/phase.json")
    matching_count=$(jq --arg ref "$redirect_ref" \
      '[.result.rules[]? | select(.ref == $ref)] | length' \
      "$temporary_root/phase.json")
    [ "$matching_count" -le 1 ] || {
      >&2 echo "multiple Cloudflare redirect rules use ref $redirect_ref"
      exit 65
    }
    managed_exact_count=$(jq \
      --arg ref "$redirect_ref" \
      --arg source_expression "$source_expression" \
      --arg target_expression "$target_expression" \
      '[
        .result.rules[]?
        | select(.ref == $ref)
        | select(.enabled != false)
        | select(.action == "redirect")
        | select(.expression == $source_expression)
        | select(.action_parameters.from_value.target_url.expression == $target_expression)
        | select(.action_parameters.from_value.status_code == 301)
        | select(.action_parameters.from_value.preserve_query_string == true)
      ] | length' "$temporary_root/phase.json")
    adoptable_count=$(jq \
      --arg ref "$redirect_ref" \
      --arg source_expression "$source_expression" \
      '[
        .result.rules[]?
        | select(.ref != $ref)
        | select(.action == "redirect")
        | select(
            .expression == $source_expression
            or .expression == ("(" + $source_expression + ")")
          )
      ] | length' "$temporary_root/phase.json")
    [ "$adoptable_count" -le 1 ] || {
      >&2 echo "multiple host-only redirect rules target www.neuralstock.ai"
      exit 65
    }
    conflicting_count=$(jq --arg ref "$redirect_ref" \
      --arg source_expression "$source_expression" \
      '[
        .result.rules[]?
        | select(.ref != $ref)
        | select(.action == "redirect")
        | select((.expression // "") | contains("www.neuralstock.ai"))
        | select(
            .expression != $source_expression
            and .expression != ("(" + $source_expression + ")")
          )
      ] | length' "$temporary_root/phase.json")
    [ "$conflicting_count" -eq 0 ] || {
      >&2 echo "another redirect rule already targets www.neuralstock.ai; reconcile it manually"
      exit 65
    }
    if [ "$matching_count" -eq 1 ]; then
      [ "$adoptable_count" -eq 0 ] || {
        >&2 echo "both managed and unmanaged host-only www redirect rules exist"
        exit 65
      }
      if [ "$managed_exact_count" -eq 1 ]; then
        mutation_method=
      else
        rule_id=$(jq -er --arg ref "$redirect_ref" \
          '.result.rules[] | select(.ref == $ref) | .id' \
          "$temporary_root/phase.json")
        mutation_url="$zone_url/rulesets/$ruleset_id/rules/$rule_id"
        mutation_method=PATCH
        operation="www redirect rule update"
      fi
    elif [ "$adoptable_count" -eq 1 ]; then
      rule_id=$(jq -er \
        --arg ref "$redirect_ref" \
        --arg source_expression "$source_expression" \
        '.result.rules[]
        | select(.ref != $ref)
        | select(.action == "redirect")
        | select(
            .expression == $source_expression
            or .expression == ("(" + $source_expression + ")")
          )
        | .id' "$temporary_root/phase.json")
      mutation_url="$zone_url/rulesets/$ruleset_id/rules/$rule_id"
      mutation_method=PATCH
      operation="host-only www redirect rule adoption"
    else
      mutation_url="$zone_url/rulesets/$ruleset_id/rules"
      mutation_method=POST
      operation="www redirect rule creation"
    fi
    if [ -n "$mutation_method" ]; then
      mutation_status=$(api_request \
        "$mutation_method" \
        "$mutation_url" \
        "$temporary_root/mutation.json" \
        "$temporary_root/rule.json")
      require_success "$mutation_status" "$temporary_root/mutation.json" "$operation"
    fi
    ;;
  404)
    jq -n \
      --slurpfile rule "$temporary_root/rule.json" \
      '{
        name: "NeuralStock canonical redirects",
        description: "Zone-level canonical host redirects managed by NeuralStock release automation",
        kind: "zone",
        phase: "http_request_dynamic_redirect",
        rules: $rule
      }' >"$temporary_root/ruleset.json"
    mutation_status=$(api_request \
      POST \
      "$zone_url/rulesets" \
      "$temporary_root/mutation.json" \
      "$temporary_root/ruleset.json")
    require_success "$mutation_status" "$temporary_root/mutation.json" \
      "redirect phase entry point creation"
    ;;
  *)
    >&2 echo "redirect phase lookup failed with HTTP $phase_status"
    jq -r '.errors[]?.message // empty' "$temporary_root/phase.json" >&2 || true
    exit 65
    ;;
esac

readback_status=$(api_request GET "$phase_url" "$temporary_root/readback.json")
require_success "$readback_status" "$temporary_root/readback.json" \
  "www redirect readback"
jq -e \
  --arg ref "$redirect_ref" \
  --arg source_expression "$source_expression" \
  --arg target_expression "$target_expression" \
  '[.result.rules[]? | select(.ref == $ref)] as $rules
  | ($rules | length) == 1
    and ($rules[0].enabled != false)
    and ($rules[0].action == "redirect")
    and ($rules[0].expression == $source_expression)
    and ($rules[0].action_parameters.from_value.target_url.expression == $target_expression)
    and ($rules[0].action_parameters.from_value.status_code == 301)
    and ($rules[0].action_parameters.from_value.preserve_query_string == true)' \
  "$temporary_root/readback.json" >/dev/null || {
  >&2 echo "Cloudflare redirect readback does not match the canonical rule"
  exit 65
}

echo "Verified Cloudflare zone rule: www.neuralstock.ai -> neuralstock.ai (301, path/query preserved)"
