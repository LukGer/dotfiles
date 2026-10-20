#!/bin/sh
#
# gh CLI extensions.
#
# ai/AGENTS.md tells agents to assume `gh stack` is available on every
# machine, so something has to actually install it — this is that something.
# gh-dash backs the `ghd` PR dashboard.

set -e

if ! command -v gh >/dev/null 2>&1; then
  echo "  gh not on PATH — brew bundle (Brewfile) then re-run"
  exit 0
fi

if ! gh auth status >/dev/null 2>&1; then
  echo "  gh not authenticated — run 'gh auth login', then re-run"
  exit 0
fi

for extension in github/gh-stack dlvhdr/gh-dash; do
  if gh extension list 2>/dev/null | grep -q "$extension"; then
    echo "  ${extension#*/} already installed"
  else
    echo "  installing ${extension#*/}"
    gh extension install "$extension"
  fi
done
