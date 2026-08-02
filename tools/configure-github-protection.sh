#!/bin/sh
set -eu

api_version=2026-03-10
canonical_repository=Neuralstock/neuralstock
canonical_organization=Neuralstock
maintainer_login=bighippoman
tag_ruleset_name=neuralstock-release-tags

usage() {
  >&2 echo "usage: $0 Neuralstock/neuralstock (--solo-maintainer | --reviewer LOGIN) [--apply]"
  exit 64
}

[ "$#" -ge 2 ] || usage
repository=$1
shift
apply=false
review_mode=
reviewer_login=

while [ "$#" -gt 0 ]; do
  case "$1" in
    --apply)
      [ "$apply" = false ] || usage
      apply=true
      ;;
    --solo-maintainer)
      [ -z "$review_mode" ] || usage
      review_mode=solo
      ;;
    --reviewer)
      [ -z "$review_mode" ] && [ "$#" -ge 2 ] || usage
      review_mode=multi
      reviewer_login=$2
      shift
      ;;
    *) usage ;;
  esac
  shift
done
[ -n "$review_mode" ] || usage

[ "$repository" = "$canonical_repository" ] || {
  >&2 echo "this rollout script is intentionally pinned to $canonical_repository"
  exit 65
}
if [ "$review_mode" = multi ] && ! printf '%s\n' "$reviewer_login" \
  | grep -Eq '^[A-Za-z0-9]([A-Za-z0-9-]{0,37}[A-Za-z0-9])?$'; then
  usage
fi

for command_name in gh grep jq mktemp sed sort tr wc; do
  command -v "$command_name" >/dev/null 2>&1 || {
    >&2 echo "required command is unavailable: $command_name"
    exit 69
  }
done

if [ "$review_mode" = solo ]; then
  review_summary="no required human approvals; PRs and deployments remain ref/check gated"
else
  review_summary="one non-initiating approval by $reviewer_login or @$maintainer_login"
fi

cat <<EOF
GitHub rollout protection plan for $repository:
- squash-only merges, signed commits, protected main, no force-push or deletion;
- required CI/security contexts and pull requests;
- active v* tag ruleset restricting create, move, and delete to @$maintainer_login;
- release, npm, and pypi environments allow only v* tags;
- production allows only branch main or v* tags;
- review mode: $review_summary.
EOF

if [ "$apply" != true ]; then
  cat <<EOF

Dry run only; no GitHub state changed. Re-run the same command with --apply
after the public repository exists, main and all required checks have run once,
and the environment-review mode above is intentional.
EOF
  exit 0
fi

gh auth status >/dev/null

api() {
  gh api \
    -H "Accept: application/vnd.github+json" \
    -H "X-GitHub-Api-Version: $api_version" \
    "$@"
}

repository_json=$(api "repos/$repository")
[ "$(printf '%s' "$repository_json" | jq -r .full_name)" = "$canonical_repository" ] || {
  >&2 echo "GitHub resolved an unexpected repository identity"
  exit 65
}
[ "$(printf '%s' "$repository_json" | jq -r .visibility)" = public ] || {
  >&2 echo "rollout protections require the canonical repository to be public"
  exit 65
}
[ "$(printf '%s' "$repository_json" | jq -r .default_branch)" = main ] || {
  >&2 echo "canonical repository default branch must be main"
  exit 65
}
[ "$(printf '%s' "$repository_json" | jq -r .owner.type)" = Organization ] || {
  >&2 echo "canonical rollout requires an organization-owned repository"
  exit 65
}
owner_login=$(printf '%s' "$repository_json" | jq -er .owner.login)
[ "$owner_login" = "$canonical_organization" ] || {
  >&2 echo "canonical repository owner changed unexpectedly"
  exit 65
}
maintainer_json=$(api "users/$maintainer_login")
maintainer_id=$(printf '%s' "$maintainer_json" | jq -er .id)
maintainer_permission_json=$(api \
  "repos/$repository/collaborators/$maintainer_login/permission")
[ "$(printf '%s' "$maintainer_permission_json" | jq -r .user.login)" = "$maintainer_login" ] || {
  >&2 echo "GitHub resolved an unexpected maintainer identity"
  exit 65
}
[ "$(printf '%s' "$maintainer_permission_json" | jq -r .permission)" = admin ] || {
  >&2 echo "@$maintainer_login must have repository administrator permission"
  exit 65
}

if [ "$review_mode" = solo ]; then
  required_approvals=0
  require_code_owner=false
  require_last_push=false
  prevent_self_review=false
  reviewers_json=null
else
  reviewer_json=$(api "users/$reviewer_login")
  reviewer_id=$(printf '%s' "$reviewer_json" | jq -er .id)
  [ "$reviewer_id" != "$maintainer_id" ] || {
    >&2 echo "--reviewer must name a second person, not the initial maintainer"
    exit 65
  }
  grep -Eq "(^|[[:space:]])@$reviewer_login([[:space:]]|$)" .github/CODEOWNERS || {
    >&2 echo "add @$reviewer_login to .github/CODEOWNERS before enabling reviewer mode"
    exit 65
  }
  required_approvals=1
  require_code_owner=true
  require_last_push=true
  prevent_self_review=true
  reviewers_json=$(jq -cn \
    --argjson maintainer_id "$maintainer_id" \
    --argjson reviewer_id "$reviewer_id" \
    '[
      {type: "User", id: $maintainer_id},
      {type: "User", id: $reviewer_id}
    ]')
fi

rulesets_json=$(api "repos/$repository/rulesets?targets=tag&per_page=100")
ruleset_ids=$(printf '%s' "$rulesets_json" | jq -r \
  --arg name "$tag_ruleset_name" \
  '.[] | select(.name == $name and .source_type == "Repository") | .id')
ruleset_count=$(printf '%s\n' "$ruleset_ids" | sed '/^$/d' | wc -l | tr -d ' ')
[ "$ruleset_count" -le 1 ] || {
  >&2 echo "multiple repository rulesets are named $tag_ruleset_name; reconcile manually"
  exit 65
}

expected_policy_names() {
  printf '%s\n' "$@" \
    | sed 's/^[^:]*://' \
    | sort \
    | jq -Rsc 'split("\n") | map(select(length > 0))'
}

validate_policy_set() {
  environment=$1
  policies=$2
  shift 2
  expected_names_json=$(expected_policy_names "$@")
  unexpected_names=$(printf '%s' "$policies" | jq -r \
    --argjson expected "$expected_names_json" \
    '.branch_policies[]
      | select(.name as $name | ($expected | index($name)) == null)
      | .name')
  if [ -n "$unexpected_names" ]; then
    >&2 echo "$environment has unexpected deployment policies:"
    >&2 printf '%s\n' "$unexpected_names"
    >&2 echo "remove them deliberately, then rerun; this script never deletes policies"
    exit 65
  fi
  for specification in "$@"; do
    policy_type=${specification%%:*}
    policy_name=${specification#*:}
    match_count=$(printf '%s' "$policies" | jq \
      --arg name "$policy_name" \
      '[.branch_policies[] | select(.name == $name)] | length')
    [ "$match_count" -le 1 ] || {
      >&2 echo "$environment has duplicate deployment policies named $policy_name"
      exit 65
    }
    if [ "$match_count" -eq 1 ]; then
      actual_type=$(printf '%s' "$policies" | jq -r \
        --arg name "$policy_name" \
        '.branch_policies[] | select(.name == $name) | (.type // "unknown")')
      if [ "$actual_type" != unknown ] && [ "$actual_type" != "$policy_type" ]; then
        >&2 echo "$environment policy $policy_name has type $actual_type, expected $policy_type"
        exit 65
      fi
    fi
  done
}

preflight_environment() {
  environment=$1
  shift
  if printf '%s' "$environments_json" | jq -e \
    --arg environment "$environment" \
    '.environments[] | select(.name == $environment)' >/dev/null; then
    policies=$(api \
      "repos/$repository/environments/$environment/deployment-branch-policies?per_page=100")
    validate_policy_set "$environment" "$policies" "$@"
  fi
}

environments_json=$(api "repos/$repository/environments?per_page=100")
preflight_environment release tag:v\*
preflight_environment npm tag:v\*
preflight_environment pypi tag:v\*
preflight_environment production branch:main tag:v\*

temporary_root=$(mktemp -d)
cleanup() {
  rm -rf "$temporary_root"
}
trap cleanup 0 1 2 15

api \
  --method PATCH \
  "repos/$repository" \
  -F allow_merge_commit=false \
  -F allow_rebase_merge=false \
  -F allow_squash_merge=true \
  -F delete_branch_on_merge=true \
  -F has_issues=true >/dev/null

jq -n \
  --argjson approvals "$required_approvals" \
  --argjson code_owner "$require_code_owner" \
  --argjson last_push "$require_last_push" \
  '{
    required_status_checks: {
      strict: true,
      contexts: [
        "Contract and clients",
        "Pinned Blender smoke test",
        "Dependency review",
        "Analyze (javascript-typescript)",
        "Analyze (python)"
      ]
    },
    enforce_admins: true,
    required_pull_request_reviews: {
      dismiss_stale_reviews: true,
      require_code_owner_reviews: $code_owner,
      required_approving_review_count: $approvals,
      require_last_push_approval: $last_push
    },
    restrictions: null,
    required_linear_history: true,
    allow_force_pushes: false,
    allow_deletions: false,
    block_creations: false,
    required_conversation_resolution: true,
    lock_branch: false,
    allow_fork_syncing: true
  }' >"$temporary_root/main-protection.json"

api \
  --method PUT \
  "repos/$repository/branches/main/protection" \
  --input "$temporary_root/main-protection.json" >/dev/null

if ! api "repos/$repository/branches/main/protection/required_signatures" >/dev/null 2>&1; then
  api \
    --method POST \
    "repos/$repository/branches/main/protection/required_signatures" >/dev/null
fi

jq -n \
  --argjson maintainer_id "$maintainer_id" \
  --arg name "$tag_ruleset_name" \
  '{
    name: $name,
    target: "tag",
    enforcement: "active",
    bypass_actors: [
      {
        actor_id: $maintainer_id,
        actor_type: "User",
        bypass_mode: "always"
      }
    ],
    conditions: {
      ref_name: {
        include: ["refs/tags/v*"],
        exclude: []
      }
    },
    rules: [
      {type: "creation"},
      {
        type: "update",
        parameters: {update_allows_fetch_and_merge: false}
      },
      {type: "deletion"}
    ]
  }' >"$temporary_root/tag-ruleset.json"

case "$ruleset_count" in
  0)
    api \
      --method POST \
      "repos/$repository/rulesets" \
      --input "$temporary_root/tag-ruleset.json" >/dev/null
    ;;
  1)
    api \
      --method PUT \
      "repos/$repository/rulesets/$ruleset_ids" \
      --input "$temporary_root/tag-ruleset.json" >/dev/null
    ;;
esac

jq -n \
  --argjson prevent_self_review "$prevent_self_review" \
  --argjson reviewers "$reviewers_json" \
  '{
    wait_timer: 0,
    prevent_self_review: $prevent_self_review,
    reviewers: $reviewers,
    deployment_branch_policy: {
      protected_branches: false,
      custom_branch_policies: true
    }
  }' >"$temporary_root/environment.json"

ensure_policy() {
  environment=$1
  policy_name=$2
  policy_type=$3
  policy_endpoint="repos/$repository/environments/$environment/deployment-branch-policies"
  policies=$(api "$policy_endpoint?per_page=100")
  matches=$(printf '%s' "$policies" | jq -r \
    --arg name "$policy_name" \
    '.branch_policies[] | select(.name == $name) | .id')
  match_count=$(printf '%s\n' "$matches" | sed '/^$/d' | wc -l | tr -d ' ')
  case "$match_count" in
    0)
      jq -n \
        --arg name "$policy_name" \
        --arg type "$policy_type" \
        '{name: $name, type: $type}' >"$temporary_root/policy.json"
      api \
        --method POST \
        "$policy_endpoint" \
        --input "$temporary_root/policy.json" >/dev/null
      ;;
    1)
      actual_type=$(printf '%s' "$policies" | jq -r \
        --arg name "$policy_name" \
        '.branch_policies[] | select(.name == $name) | (.type // "unknown")')
      if [ "$actual_type" != unknown ] && [ "$actual_type" != "$policy_type" ]; then
        >&2 echo "$environment policy $policy_name has type $actual_type, expected $policy_type"
        exit 65
      fi
      ;;
    *)
      >&2 echo "$environment has duplicate deployment policies named $policy_name"
      exit 65
      ;;
  esac
}

configure_environment() {
  environment=$1
  shift
  api \
    --method PUT \
    "repos/$repository/environments/$environment" \
    --input "$temporary_root/environment.json" >/dev/null

  policies=$(api \
    "repos/$repository/environments/$environment/deployment-branch-policies?per_page=100")
  validate_policy_set "$environment" "$policies" "$@"

  for specification in "$@"; do
    policy_type=${specification%%:*}
    policy_name=${specification#*:}
    ensure_policy "$environment" "$policy_name" "$policy_type"
  done
}

configure_environment release tag:v\*
configure_environment npm tag:v\*
configure_environment pypi tag:v\*
configure_environment production branch:main tag:v\*

api "repos/$repository/branches/main/protection" >/dev/null
api "repos/$repository/rulesets?targets=tag&per_page=100" \
  --jq ".[] | select(.name == \"$tag_ruleset_name\")" >/dev/null
for environment in release npm pypi production; do
  api "repos/$repository/environments/$environment" >/dev/null
  api \
    "repos/$repository/environments/$environment/deployment-branch-policies?per_page=100" \
    --jq '.branch_policies[] | [.name, (.type // "type-not-returned-by-api")] | @tsv'
done

cleanup
trap - 0 1 2 15
echo "Reconciled GitHub rollout protections for $repository"
