#!/bin/sh
#
# Node toolchain: mise (which manages node, npm and pnpm) and Bun.
#
# Node is deliberately not in the Brewfile: a brew node would fight mise's shims
# (see zsh/path.zsh), and bin/papercut needs bun at $BUN_INSTALL/bin, where
# .zshenv puts it on PATH for non-interactive shells.

set -e

if ! command -v mise >/dev/null 2>&1; then
  echo "  installing mise"
  # The Brewfile normally installs mise; this also handles SKIP_BREW_BUNDLE.
  # Shell activation and PATH are handled by the zsh topic.
  brew install mise
fi

mise install --cd "$HOME"

if [ -x "$HOME/.bun/bin/bun" ]; then
  echo "  Bun already installed"
else
  echo "  installing Bun"
  # SHELL=sh keeps the installer from appending PATH exports to ~/.zshrc,
  # which is a symlink into this repo. .zshenv already covers PATH.
  curl -fsSL https://bun.sh/install | SHELL=sh bash
fi
