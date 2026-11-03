#!/bin/sh
#
# ghd: link the OpenCode agents and review plugins, and register the
# Atlassian MCP server for Jira reads. script/bootstrap
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
link "$DOTFILES/config/opencode/agents/ghd-reviewer.md" "$HOME/.config/opencode/agents/ghd-reviewer.md" "opencode specialist ghd-reviewer"
link "$DOTFILES/config/opencode/agents/ghd-chat.md" "$HOME/.config/opencode/agents/ghd-chat.md" "opencode PR chat"
link "$DOTFILES/ghd/progress-plugin.ts" "$HOME/.config/opencode/plugins/ghd-progress.ts" "opencode plugin ghd-progress"
link "$DOTFILES/ghd/opencode-plugin.ts" "$HOME/.config/opencode/plugins/ghd-review.ts" "opencode plugin ghd-review"

if command -v opencode >/dev/null && ! opencode mcp list 2>/dev/null | grep -q 'atlassian'; then
  opencode mcp add atlassian --global --url https://mcp.atlassian.com/v1/mcp/authv2 >/dev/null \
    && echo "  registered OpenCode MCP server atlassian (run 'opencode mcp auth atlassian' once)"
fi

if command -v pi >/dev/null && ! pi mcp list 2>/dev/null | grep -q '^atlassian\b'; then
  pi mcp add atlassian https://mcp.atlassian.com/v1/mcp/authv2 --description 'Jira reads for ghd reviews' >/dev/null \
    && echo "  registered pi MCP server atlassian (run 'pi mcp login atlassian' once)"
fi
