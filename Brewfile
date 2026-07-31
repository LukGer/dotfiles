# Run `brew bundle --file=~/.dotfiles/Brewfile` (script/install does this).
# Check drift with `brew bundle check --file=~/.dotfiles/Brewfile`.
#
# Deliberately NOT listed:
#   powerlevel10k — installed via zinit in zsh/zshrc.symlink; two copies conflict
#   pnpm          — managed by Volta (VOLTA_FEATURE_PNPM=1 in zsh/tools.zsh)
#   node          — managed by Volta; brew's copy is only a transitive dependency
#
# Cursor extensions are NOT tracked here either, even though `brew bundle dump`
# emits them as `vscode` lines. They live in cursor/extensions.txt so there is
# one source of truth, and because the `code` CLI on this machine is Cursor's.

cask_args appdir: "/Applications"

tap "tw93/tap", trusted: true
tap "withgraphite/tap"

# --- Shell utilities (zsh/aliases.zsh and zsh/tools.zsh depend on these) ---
brew "bat"
brew "fastfetch"
brew "fzf"
brew "lsd"
brew "mole"
brew "ripgrep"

# --- Git and GitHub ---
brew "gh"

# --- Web development ---
brew "biome"

# --- Mobile development (Expo / React Native) ---
brew "cocoapods"
brew "fastlane"
brew "watchman"

# --- Media ---
brew "exiftool"
brew "ffmpeg"

# --- Infrastructure and databases ---
brew "ansible"
brew "mongosh"
brew "nginx"

# --- Languages and crypto ---
# Ruby is here for cocoapods/fastlane, which need a newer interpreter than the
# macOS system 2.6.
brew "gnupg"
brew "ruby@3.1"

# --- Editors and terminals ---
cask "cursor"
cask "ghostty"

# --- AI tooling ---
cask "claude"
cask "conductor"

# --- Development ---
cask "docker-desktop"
cask "fork"
cask "mongodb-compass"
cask "ngrok"

# --- Design ---
cask "figma"

# --- Password managers ---
cask "1password"
cask "bitwarden"

# --- Communication ---
cask "slack"
cask "whatsapp"

# --- Networking ---
cask "surfshark"
cask "tailscale-app"

# --- Everything else ---
cask "google-chrome"
cask "mactex"
cask "raycast"
cask "spotify"
cask "steam"
