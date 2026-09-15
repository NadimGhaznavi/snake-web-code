#!/usr/bin/env bash
# Create and publish a snake-web release: feature -> dev -> main.

set -euo pipefail

cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."

constants_file="snake_web/constants/DSnakeWeb.py"
number='(0|[1-9][0-9]*)'
prerelease='(0|[1-9][0-9]*|[0-9A-Za-z-]*[A-Za-z-][0-9A-Za-z-]*)'
version_pattern="${number}\.${number}\.${number}(-${prerelease}(\.${prerelease})*)?(\+[0-9A-Za-z-]+(\.[0-9A-Za-z-]+)*)?"

fail() {
    printf 'Error: %s\n' "$*" >&2
    exit 1
}

next_patch() {
    python3 -c 'import sys; v = sys.argv[1].split("-")[0].split("+")[0].split("."); print(f"{v[0]}.{v[1]}.{int(v[2]) + 1}")' "$1"
}

current_version() {
    sed -nE 's/^    VERSION: Final\[str\] = "([^"]+)"$/\1/p' "${constants_file}"
}

usage() {
    local branch likely_version next_version current
    branch=$(git branch --show-current)
    if [[ ${branch} =~ (^|[/_-])v?(${version_pattern})$ ]]; then
        likely_version=${BASH_REMATCH[2]}
    else
        current=$(current_version)
        [[ ${current} =~ ^${version_pattern}$ ]] || fail "Invalid VERSION in ${constants_file}."
        likely_version=$(next_patch "${current}")
    fi
    next_version=$(next_patch "${likely_version}")

    cat <<EOF
Usage: $(basename -- "$0") <version> <message> [next-feature-branch]

Current branch: ${branch}
Likely next version: ${likely_version}

Example:
  $(basename -- "$0") ${likely_version} "Maintenance release"

Next feature branch: feat/maint-${next_version}

Run from a clean feat/* branch containing local dev, with dev containing main.
Local dev and main must include their corresponding remote branches, if present.
Use a version without a leading v. The next branch defaults to
feat/maint-<version with patch incremented>.

Updates the version and changelog, merges through dev to main, tags and
pushes the release, then creates the next local feature branch.
EOF
}

if [[ ${1:-} == -h || ${1:-} == --help ]]; then
    usage
    exit 0
fi
if [[ $# -lt 2 || $# -gt 3 ]]; then
    usage >&2
    exit 2
fi

version=$1
[[ ${version} =~ ^${version_pattern}$ ]] || fail "Use a valid semantic version without a leading v."
[[ $2 =~ [^[:space:]] ]] || fail "The release message must not be blank."
message="Release ${version}: $2"
tag="v${version}"
next_branch=${3-"feat/maint-$(next_patch "${version}")"}
source_branch=$(git branch --show-current)
release_date=$(date '+%Y-%m-%d @ %H:%M')

[[ ${source_branch} == feat/* ]] || fail "Start from a feat/* branch."
[[ -z $(git status --porcelain --untracked-files=all) ]] || fail "Commit or stash all changes, including untracked files, first."
[[ ${next_branch} == feat/* ]] || fail "The next branch must start with feat/."
git check-ref-format "refs/heads/${next_branch}" >/dev/null || fail "Invalid next branch name."
git show-ref --verify --quiet "refs/heads/${next_branch}" && fail "Next branch already exists: ${next_branch}."
for branch in dev main; do
    git show-ref --verify --quiet "refs/heads/${branch}" || fail "Missing local ${branch} branch."
done
git merge-base --is-ancestor main dev || fail "Merge main into dev before releasing."
git merge-base --is-ancestor dev "${source_branch}" || fail "Merge dev into ${source_branch} before releasing."
git ls-files --error-unmatch "${constants_file}" CHANGELOG.md >/dev/null || fail "The constants file and changelog must be committed."
current=$(current_version)
[[ ${current} =~ ^${version_pattern}$ ]] || fail "Expected exactly one valid VERSION in ${constants_file}."
[[ ${version} != "${current}" ]] || fail "VERSION is already ${version}."
[[ $(grep -c '^## \[Unreleased\]$' CHANGELOG.md) == 1 ]] || fail "Expected exactly one ## [Unreleased] heading."
if grep -Fq "## [${version}]" CHANGELOG.md; then
    fail "The changelog already contains ${version}."
fi

git fetch --prune --tags origin '+refs/heads/*:refs/remotes/origin/*'
git show-ref --verify --quiet "refs/tags/${tag}" && fail "Tag already exists: ${tag}."
git show-ref --verify --quiet "refs/remotes/origin/${next_branch}" && fail "Next branch already exists on origin: ${next_branch}."
for branch in dev main; do
    if git show-ref --verify --quiet "refs/remotes/origin/${branch}"; then
        git merge-base --is-ancestor "origin/${branch}" "${branch}" || fail "Local ${branch} is behind or diverged from origin/${branch}."
    fi
done

trap 'printf "Release stopped. Inspect git status and branch history before continuing; local changes have not been rolled back.\n" >&2' ERR
git switch dev
git merge --no-ff "${source_branch}" -m "Merge ${source_branch} for ${tag}"

sed -i -E "s/^(    VERSION: Final\[str\] = ).*/\1\"${version}\"/" "${constants_file}"
sed -i "/^## \[Unreleased\]$/a\\
\\
## [${version}] - ${release_date}" CHANGELOG.md
git add -- "${constants_file}" CHANGELOG.md
git commit -m "${message}"

git switch main
git merge --no-ff dev -m "${message}"
git tag -a "${tag}" -m "${message}"

git switch dev
git merge --ff-only main
git push --atomic origin main dev "refs/tags/${tag}"
git switch -c "${next_branch}"
