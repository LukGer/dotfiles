#!/bin/sh
#
# ghd: link the OpenCode reviewer agent. script/bootstrap links config/ on a
# fresh machine; this keeps existing machines current when `dot` runs.

DOTFILES="${DOTFILES:-$HOME/.dotfiles}"
AGENTS="$HOME/.config/opencode/agents"

mkdir -p "$AGENTS"
src="$DOTFILES/config/opencode/agents/pr-review.md"
dst="$AGENTS/pr-review.md"
if [ "$(readlink "$dst")" != "$src" ]; then
  rm -f "$dst"
  ln -s "$src" "$dst"
  echo "  linked opencode agent pr-review"
fi
