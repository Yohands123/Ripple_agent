#!/usr/bin/env bash
# Creates one working copy per agent so they never edit the same checkout.
set -euo pipefail
root="$(git rev-parse --show-toplevel)"
cd "$root"
git rev-parse --verify main >/dev/null 2>&1 || git branch -M main
git worktree add "../ripple-ml"  -b ml  2>/dev/null || echo "ripple-ml already exists"
git worktree add "../ripple-web" -b web 2>/dev/null || echo "ripple-web already exists"
git worktree list
echo
echo "Codex:       cd ../ripple-ml  && codex"
echo "Claude Code: cd ../ripple-web && claude"
