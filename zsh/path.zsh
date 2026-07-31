# Single authoritative PATH build.
#
# `typeset -U path` makes the array unique, so re-sourcing this file (or a
# tool's installer prepending itself again) can't produce duplicate entries.
# Previously PATH carried two copies each of /bin, /usr/bin, /usr/local/bin,
# /sbin, .volta/bin, .opencode/bin and .bun/bin.
#
# Order matters in one place specifically: $VOLTA_HOME/bin must precede
# /opt/homebrew/bin, because brew pulled in its own node as a transitive
# dependency and Volta's shim has to win. Verify with `which -a node`.
typeset -U path PATH

export VOLTA_HOME="$HOME/.volta"
export BUN_INSTALL="$HOME/.bun"

path=(
  "$DOTFILES/bin"
  "$VOLTA_HOME/bin"
  "$BUN_INSTALL/bin"
  "$HOME/.opencode/bin"
  "$HOME/.local/bin"          # uv installs here; replaces `. ~/.local/bin/env`
  /opt/homebrew/bin
  /opt/homebrew/sbin
  $path
)

export PATH
