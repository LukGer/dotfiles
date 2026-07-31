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

# --- CLI ---
# Automate deployment, configuration, and upgrading
brew "ansible"
# Clone of cat(1) with syntax highlighting and Git integration
brew "bat"
# Toolchain of the web
brew "biome"
# Dependency manager for Cocoa projects
brew "cocoapods"
# Perl lib for reading and writing EXIF metadata
brew "exiftool"
# Like neofetch, but much faster because written mostly in C
brew "fastfetch"
# Easiest way to build and release mobile apps
brew "fastlane"
# Play, record, convert, and stream select audio and video codecs
brew "ffmpeg"
# Command-line fuzzy finder written in Go
brew "fzf"
# GitHub command-line tool
brew "gh"
# GNU Privacy Guard (OpenPGP)
brew "gnupg"
# Clone of ls with colorful output, file type icons, and more
brew "lsd"
# Deep clean and optimize your Mac
brew "mole"
# MongoDB Shell to connect, configure, query, and work with your MongoDB database
brew "mongosh"
# HTTP(S) server and reverse proxy, and IMAP/POP3 proxy server
brew "nginx"
# Search tool like grep and The Silver Searcher
brew "ripgrep"
# Powerful, clean, object-oriented scripting language
brew "ruby@3.1"
# Watch files and take action when they change
brew "watchman"

# --- Casks ---
# Everything below was originally installed by hand; listing it here is what
# makes a rebuild one command.
cask "1password"
cask "bitwarden"
cask "claude"
cask "conductor"
cask "cursor"
cask "docker-desktop"
cask "figma"
cask "fork"
cask "ghostty"
cask "google-chrome"
cask "mactex"
cask "mongodb-compass"
cask "ngrok"
cask "raycast"
cask "slack"
cask "spotify"
cask "steam"
cask "surfshark"
cask "tailscale-app"
cask "whatsapp"
