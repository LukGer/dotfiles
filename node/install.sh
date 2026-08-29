#!/bin/sh
#
# Node toolchain: Volta (which manages node, npm and pnpm) and Bun.
#
# Deliberately not in the Brewfile: a brew node would fight Volta's shims
# (see zsh/path.zsh), and bin/papercut needs bun at $BUN_INSTALL/bin, where
# .zshenv puts it on PATH for non-interactive shells.

set -e

if [ -x "$HOME/.volta/bin/volta" ]; then
  echo "  Volta already installed"
else
  echo "  installing Volta"
  # --skip-setup: PATH is handled by .zshenv, and Volta's own profile edits
  # come back on every upgrade anyway (see README).
  curl -fsSL https://get.volta.sh | bash -s -- --skip-setup
  "$HOME/.volta/bin/volta" install node
fi

if [ -x "$HOME/.bun/bin/bun" ]; then
  echo "  Bun already installed"
else
  echo "  installing Bun"
  # SHELL=sh keeps the installer from appending PATH exports to ~/.zshrc,
  # which is a symlink into this repo. .zshenv already covers PATH.
  curl -fsSL https://bun.sh/install | SHELL=sh bash
fi
