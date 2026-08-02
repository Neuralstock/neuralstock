#!/bin/sh
set -eu

canonical_repository=Neuralstock/neuralstock
ruleset_name=neuralstock-release-tags

usage() {
  >&2 echo "usage: $0 VERSION EXPECTED_COMMIT"
  exit 64
}

[ "$#" -eq 2 ] || usage
version=$1
expected_commit=$2
tag="v$version"

if ! printf '%s\n' "$version" \
  | grep -Eq '^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$'; then
  >&2 echo "release version must be a semantic version without a v prefix: $version"
  exit 65
fi
if ! printf '%s\n' "$expected_commit" | grep -Eq '^[0-9a-f]{40}$'; then
  >&2 echo "expected commit must contain exactly 40 lowercase hexadecimal characters"
  exit 65
fi

for command_name in git grep; do
  command -v "$command_name" >/dev/null 2>&1 || {
    >&2 echo "required command is unavailable: $command_name"
    exit 69
  }
done
git rev-parse --is-inside-work-tree >/dev/null 2>&1 || {
  >&2 echo "release-tag verification requires a Git working tree"
  exit 65
}
origin_url=$(git remote get-url origin 2>/dev/null) || {
  >&2 echo "release-tag verification requires an origin remote"
  exit 65
}
if [ -n "${GITHUB_REPOSITORY:-}" ]; then
  [ "$GITHUB_REPOSITORY" = "$canonical_repository" ] || {
    >&2 echo "release verification is pinned to $canonical_repository"
    exit 65
  }
  case "$origin_url" in
    "https://github.com/$canonical_repository" | "https://github.com/$canonical_repository.git") ;;
    *)
      >&2 echo "GitHub Actions origin is not the canonical repository"
      exit 65
      ;;
  esac
fi

main_ref=refs/neuralstock-verification/main
tag_ref=refs/neuralstock-verification/tag
shallow_file=$(git rev-parse --git-path shallow)
if [ -f "$shallow_file" ]; then
  git fetch --quiet --no-tags --unshallow --force origin \
    "refs/heads/main:$main_ref" \
    "refs/tags/$tag:$tag_ref"
else
  git fetch --quiet --no-tags --force origin \
    "refs/heads/main:$main_ref" \
    "refs/tags/$tag:$tag_ref"
fi || {
  >&2 echo "origin must contain branch main and release tag $tag"
  exit 65
}

tag_commit=$(git rev-parse "$tag_ref^{commit}")
main_commit=$(git rev-parse "$main_ref^{commit}")
[ "$tag_commit" = "$expected_commit" ] || {
  >&2 echo "$tag resolves to $tag_commit, expected $expected_commit"
  exit 65
}
git merge-base --is-ancestor "$expected_commit" "$main_ref" || {
  >&2 echo "$tag commit $expected_commit is not an ancestor of origin/main"
  exit 65
}

if [ -n "${GITHUB_REPOSITORY:-}" ]; then
  [ -n "${GH_TOKEN:-}" ] || {
    >&2 echo "GH_TOKEN is required in GitHub Actions"
    exit 65
  }
  for command_name in gh jq sed tr wc; do
    command -v "$command_name" >/dev/null 2>&1 || {
      >&2 echo "required command is unavailable: $command_name"
      exit 69
    }
  done

  branch_json=$(gh api "repos/$canonical_repository/branches/main")
  [ "$(printf '%s' "$branch_json" | jq -r .protected)" = true ] || {
    >&2 echo "canonical main is not protected"
    exit 65
  }
  api_main_commit=$(printf '%s' "$branch_json" | jq -er .commit.sha)
  [ "$api_main_commit" = "$main_commit" ] || {
    >&2 echo "origin/main moved during release-tag verification; rerun the workflow"
    exit 75
  }

  rulesets_json=$(gh api \
    "repos/$canonical_repository/rulesets?targets=tag&per_page=100")
  ruleset_ids=$(printf '%s' "$rulesets_json" | jq -r \
    --arg name "$ruleset_name" \
    '.[]
      | select(
          .name == $name
          and .source_type == "Repository"
          and .target == "tag"
          and .enforcement == "active"
        )
      | .id')
  ruleset_count=$(printf '%s\n' "$ruleset_ids" | sed '/^$/d' | wc -l | tr -d ' ')
  [ "$ruleset_count" -eq 1 ] || {
    >&2 echo "expected one active repository tag ruleset named $ruleset_name"
    exit 65
  }
  ruleset_json=$(gh api "repos/$canonical_repository/rulesets/$ruleset_ids")
  printf '%s' "$ruleset_json" | jq -e '
    (.conditions.ref_name.include | index("refs/tags/v*")) != null
    and ((["creation", "update", "deletion"] - [.rules[].type]) | length == 0)
  ' >/dev/null || {
    >&2 echo "$ruleset_name does not protect creation, update, and deletion of v* tags"
    exit 65
  }

  tag_ref_json=$(gh api "repos/$canonical_repository/git/ref/tags/$tag")
  tag_object_sha=$(printf '%s' "$tag_ref_json" | jq -er '
    if .object.type == "tag" then .object.sha
    else error("release ref is not an annotated tag")
    end
  ') || {
    >&2 echo "$tag is not an annotated signed tag"
    exit 65
  }
  tag_json=$(gh api "repos/$canonical_repository/git/tags/$tag_object_sha")
  printf '%s' "$tag_json" | jq -e \
    --arg tag "$tag" \
    --arg commit "$expected_commit" '
      .tag == $tag
      and .object.type == "commit"
      and .object.sha == $commit
      and .verification.verified == true
      and .verification.reason == "valid"
    ' >/dev/null || {
    >&2 echo "$tag is not a valid GitHub-verified signature over $expected_commit"
    exit 65
  }
  protection_status="signed tag on protected main"
else
  protection_status="origin/main (GitHub protection not checked locally)"
fi

echo "Verified $tag at $expected_commit on $protection_status $main_commit"
