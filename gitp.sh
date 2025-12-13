#!/usr/bin/env bash
# Hard-reset the current branch to its remote tracking branch,
# discarding any local changes. This is destructive.

set -euo pipefail

# Show current branch
branch="$(git rev-parse --abbrev-ref HEAD)"
echo "Current branch: $branch"

# Ensure there is an upstream set; if not, try to set it to origin/<branch>
if ! git rev-parse --abbrev-ref --symbolic-full-name "@{u}" >/dev/null 2>&1; then
  echo "No upstream set for $branch. Attempting to set upstream to origin/$branch..."
  git branch --set-upstream-to="origin/$branch" "$branch" || {
    echo "Failed to set upstream. Does origin/$branch exist?" >&2
    exit 1
  }
fi

upstream="@{u}"
echo "Upstream: $(git rev-parse --abbrev-ref "$upstream")"

# Fetch latest from remote
echo "Fetching latest from remote..."
git fetch --all --prune

# Reset hard to upstream
echo "Resetting local branch to upstream (destructive)..."
git reset --hard "$upstream"

echo "Done. Branch $branch now matches $(git rev-parse --abbrev-ref "$upstream")."