#!/bin/sh
#
# ghd: link the OpenCode reviewer agent and progress plugin. script/bootstrap
# links config/ on a fresh machine; this keeps existing machines current when
# `dot` runs.

DOTFILES="${DOTFILES:-$HOME/.dotfiles}"

link() {
  mkdir -p "$(dirname "$2")"
  if [ "$(readlink "$2")" != "$1" ]; then
    rm -f "$2"
    ln -s "$1" "$2"
    echo "  linked $3"
  fi
}

link "$DOTFILES/config/opencode/agents/pr-review.md" "$HOME/.config/opencode/agents/pr-review.md" "opencode agent pr-review"
link "$DOTFILES/ghd/progress-plugin.ts" "$HOME/.config/opencode/plugins/ghd-progress.ts" "opencode plugin ghd-progress"
