# Global instructions

Applies to every project unless a repo-level `CLAUDE.md` overrides it.

## Environment

- macOS, zsh, Homebrew on Apple Silicon (`/opt/homebrew`).
- Node toolchain is managed by **Volta**, not nvm/brew. Use `volta install`,
  never `brew install node`. `pnpm` also comes from Volta
  (`VOLTA_FEATURE_PNPM=1`).
- Python is managed by **uv** (`~/.local/bin`).
- Editor is **Cursor**; the `code` CLI on PATH is Cursor's, not VS Code's.
- Dotfiles live in `~/.dotfiles` — see its README before changing anything
  in `$HOME` that looks like a symlink.

## Preferences

- Prefer `rg` over `grep` and `lsd` over `ls` when suggesting shell commands.
- Formatting is Prettier + Biome, 2-space indent. Don't reformat files you
  weren't asked to touch.
- Don't add comments that restate the code. Comment the non-obvious *why*.
- Don't create README files or documentation unless asked.

## Git

- Commit signing is on (SSH, `~/.ssh/id_ed25519.pub`). Don't disable it.
- Never `git push --force`; `git pushf` (force-with-lease) exists as an alias.
- Don't commit or push unless asked.
