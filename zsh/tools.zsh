# Tool initialization. PATH entries for these live in path.zsh; this file is
# for completions, hooks and environment variables only.

# fzf
if command -v fzf >/dev/null 2>&1; then
  eval "$(fzf --zsh)"
fi

# bun completions
[ -s "$BUN_INSTALL/_bun" ] && source "$BUN_INSTALL/_bun"

# Volta manages pnpm as well as node/npm/yarn.
export VOLTA_FEATURE_PNPM=1

export UNITY_PATH="$HOME/dev/unity"
