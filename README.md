# LukGer dotfiles

Your dotfiles are how you personalize your system. These are mine — macOS
config for zsh, git, Homebrew, Ghostty, Cursor and Claude Code.

They're so personal I copied much of them from
[pauldambra/dotfiles](https://github.com/pauldambra/dotfiles) including the
approach to install them.

## Install

```sh
git clone https://github.com/LukGer/dotfiles.git ~/.dotfiles
cd ~/.dotfiles
script/bootstrap
```

Bootstrap symlinks everything into place and runs each topic's installer. When
it finds a file already sitting where a symlink should go it asks per file —
pick **[b]ackup** on a first run, which moves the original to `~/.foo.backup`.

macOS defaults are *not* applied automatically. Read `macos/set-defaults.sh`,
then run it yourself.

## How it works

Four conventions, all handled by `script/bootstrap` and `script/install`:

| Convention | Effect |
| --- | --- |
| `topic/foo.symlink` | linked to `~/.foo` |
| `config/<path>` | linked to `~/.config/<path>` |
| `topic/install.sh` | run by `script/install` |
| `zsh/*.zsh` | sourced at shell startup |

The `config/` tree is the one addition to holman's design — his `*.symlink`
rule can only produce `~/.foo`, and Ghostty, lsd and gh all keep their
config under `~/.config`.

Run `dot` any time to pull, update Homebrew and re-run the installers.

## Topics

| Topic | Contents |
| --- | --- |
| `zsh/` | zinit + Powerlevel10k, split into `path`/`config`/`aliases`/`functions`/`tools` |
| `git/` | shared config, ~30 aliases, global gitignore, gitignored local identity; installs the `gh-stack` extension |
| `node/` | installs mise-managed toolchains and global CLIs, plus Bun when missing |
| `homebrew/` | installs Homebrew itself; packages come from `Brewfile` |
| `macos/` | `defaults write` settings, run manually |
| `cursor/` | settings, keybindings, and the 17-extension list |
| `ai/` | global `AGENTS.md` (shared) + `CLAUDE.md` import, Claude Code settings, skill lock file |
| `config/` | Ghostty, lsd, gh, mise defaults, GUI git-hook toolchain |
| `npm/` | `~/.npmrc` template (private registry token) |
| `bin/` | `dot`, `e`, and a few git helpers; added to `PATH` |

### bin

| Script | Purpose |
| --- | --- |
| `dot` | pull, `brew update`, re-run installers |
| `e` | open a path in the editor (defaults to `.`) |
| `git-nuke` | delete a branch locally and on origin; refuses the default branch |
| `git-bclean` | delete local branches whose upstream is gone (`--force` to commit to it) |
| `git-credit` | add a co-author trailer to the last commit |
| `papercut` | log a small friction hit to `PAPERCUTS.md`; agents call it mid-task (see `ai/AGENTS.md`) |

## Secrets

The repo is public, so everything secret is kept out by construction:

- `~/.gitconfig.local` — identity and signing key. Generated from
  `git/gitconfig.local.symlink.template`, gitignored.
- `~/.npmrc` — private registry token. Generated from
  `npm/npmrc.symlink.template`, gitignored. An existing `~/.npmrc` is
  preserved rather than overwritten, so bootstrap never destroys a token.
- `~/.zshrc.local` — sourced at the end of `.zshrc` if present, never
  committed. Put machine-specific exports and API keys here.

Deliberately **not** tracked, because each carries a live credential:
`~/.config/gh/hosts.yml`, `~/.claude.json`, `~/.cursor/mcp.json`, `~/.ssh/*`.

### Skills

Nearly all installed Claude skills come from other people's repositories.
Vendoring them into a public repo would republish someone else's work, so
`ai/skill-lock.json` records where each came from and `ai/install.sh`
re-fetches them on a new machine. Only self-authored skills live in
`ai/skills/`.

## Notes

- **Node and pnpm** are managed by mise, installed through Homebrew. Global
  defaults and CLI versions live in `config/mise/config.toml`; repository
  `mise.toml` and `package.json#packageManager` pins take precedence. The global
  Node default preserves 26.10.0; Unity selects 22.14.0 and pnpm 12.3.4.
  See [mise's version-file guidance](https://mise.jdx.dev/configuration.html#idiomatic-version-files).
- **Shells and GUI git hooks** put mise's shims ahead of Homebrew's transitive
  Node installation. Interactive zsh also activates mise's directory-change
  hook. Check with `mise current`, `which -a node`, and `node -v`; use
  `mise install` and `mise exec -- pnpm install` for non-interactive setup.
- **Migrating an existing machine:** remove old Volta exports from `~/.profile`
  and any local shell overrides, then restart terminals and GUI apps. Before
  deleting `~/.volta`, migrate its global CLI packages to mise. The tracked
  mise config preserves the CLI versions from this machine's migration.
- **Conductor setup** should use the repository's shared mise script. An old
  `.conductor/settings.local.toml` in the main checkout can override it with
  plain `pnpm install`; remove that setup override to inherit the shared one.
- **Cursor and Claude Code rewrite their `settings.json`** when you change
  settings through the UI. They currently write in place, so the symlink
  survives — but if a settings change ever stops showing up in `git status`,
  check whether the symlink was replaced by a real file.

## TODO

- Split work and personal git identity with
  `includeIf "gitdir:~/dev/work/"`. The stub is in
  `git/gitconfig.local.symlink.template`; currently everything commits as
  `lukger1999@gmail.com`.
