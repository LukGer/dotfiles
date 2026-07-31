#!/bin/sh
#
# Cursor: link settings and keybindings, install extensions.
#
# None of the reference dotfiles repos sync GUI editor config; this is the
# local addition. The `code` CLI on this machine is Cursor's (there is no
# VS Code installed), so `code --install-extension` targets Cursor.

set -e

DOTFILES="$HOME/.dotfiles"
CURSOR_USER="$HOME/Library/Application Support/Cursor/User"

if [ ! -d "$CURSOR_USER" ]; then
  echo "  Cursor user directory not found — skipping (is Cursor installed?)"
  exit 0
fi

link() {
  src="$1"
  dst="$2"

  if [ -L "$dst" ] && [ "$(readlink "$dst")" = "$src" ]; then
    echo "  already linked: $(basename "$dst")"
    return
  fi

  if [ -e "$dst" ] && [ ! -L "$dst" ]; then
    mv "$dst" "$dst.backup"
    echo "  backed up existing $(basename "$dst") to $(basename "$dst").backup"
  fi

  rm -f "$dst"
  ln -s "$src" "$dst"
  echo "  linked $(basename "$dst")"
}

link "$DOTFILES/cursor/settings.json" "$CURSOR_USER/settings.json"
link "$DOTFILES/cursor/keybindings.json" "$CURSOR_USER/keybindings.json"

# Extensions. Skips ones already present, so re-runs are cheap.
if command -v cursor >/dev/null 2>&1; then
  installed=$(cursor --list-extensions 2>/dev/null || echo "")
  while IFS= read -r ext; do
    [ -z "$ext" ] && continue
    if echo "$installed" | grep -qix "$ext"; then
      continue
    fi
    echo "  installing extension $ext"
    cursor --install-extension "$ext" >/dev/null 2>&1 || echo "    failed: $ext"
  done < "$DOTFILES/cursor/extensions.txt"
else
  echo "  cursor CLI not on PATH — skipping extension install"
fi
