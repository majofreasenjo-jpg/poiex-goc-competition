#!/usr/bin/env bash
set -euo pipefail

REMOTE_URL="${1:-}"
BRANCH="${2:-main}"

if [[ -z "$REMOTE_URL" ]]; then
  cat >&2 <<'EOF'
usage: scripts/github_publish_new_repo.sh NEW_EMPTY_REPO_URL [BRANCH]

Create a NEW empty repository in GitHub first. Do not initialize it with README,
.gitignore, or license. Then pass its clone URL here.
EOF
  exit 2
fi

if git remote get-url contest >/dev/null 2>&1; then
  existing="$(git remote get-url contest)"
  if [[ "$existing" != "$REMOTE_URL" ]]; then
    echo "contest remote already points to a different URL: $existing" >&2
    exit 1
  fi
else
  git remote add contest "$REMOTE_URL"
fi

echo "Remote: $REMOTE_URL"
echo "Branch: $BRANCH"
echo "About to publish full clean-room/recovery history."
git push contest "HEAD:$BRANCH" --tags

echo "REMOTE_PUBLISH=COMPLETE"
