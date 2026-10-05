# Load mise shims for GUI apps (Fork, Tower, etc.).
export PATH="${MISE_DATA_DIR:-$HOME/.local/share/mise}/shims:/opt/homebrew/bin:/opt/homebrew/sbin:$PATH"

# Add the Bun toolchain used by dotfiles helpers.
export PATH="$HOME/.bun/bin:$PATH"
