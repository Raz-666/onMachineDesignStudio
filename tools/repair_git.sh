#!/usr/bin/env bash
# R175: self-heal the repo metadata after a workspace snapshot round-trip.
#
# The sandbox snapshot EXCLUDES .git/config (credential policy) and does not
# preserve EMPTY directories (.git/refs, .git/refs/heads, .git/refs/tags) -
# without them git says "not a git repository" although HEAD, objects and
# packed-refs are all intact. Run this once after pulling the workspace up
# in a fresh session:
#
#   bash tools/repair_git.sh
#
# It is idempotent - running it on a healthy repo changes nothing.
set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -f .git/HEAD ]; then
    echo "repair_git: no .git/HEAD here - this is not a repo root, abort"
    exit 1
fi

if [ ! -f .git/config ]; then
    printf '[core]\n\trepositoryformatversion = 0\n\tfilemode = true\n\tbare = false\n\tlogallrefupdates = true\n' > .git/config
    echo "repair_git: .git/config restored"
fi

for d in refs refs/heads refs/tags; do
    if [ ! -d ".git/$d" ]; then
        mkdir -p ".git/$d"
        echo "repair_git: .git/$d restored"
    fi
done

git status --short | head -5
git log --oneline -1
