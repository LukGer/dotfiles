# dotfiles

macOS config for zsh, git, Homebrew, Ghostty, Cursor and Claude Code.

Structure and install mechanism are lifted from
[holman/dotfiles](https://github.com/holman/dotfiles), by way of
[haacked/dotfiles](https://github.com/haacked/dotfiles) and
[pauldambra/dotfiles](https://github.com/pauldambra/dotfiles).

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
rule can only produce `~/.foo`, and Ghostty, lsd, gh and Graphite all keep
their config under `~/.config`.

Run `dot` any time to pull, update Homebrew and re-run the installers.

## Topics

| Topic | Contents |
| --- | --- |
| `zsh/` | zinit + Powerlevel10k, split into `path`/`config`/`aliases`/`functions`/`tools` |
| `git/` | shared config, ~30 aliases, global gitignore, gitignored local identity |
| `homebrew/` | installs Homebrew itself; packages come from `Brewfile` |
| `macos/` | `defaults write` settings, run manually |
| `cursor/` | settings, keybindings, and the 17-extension list |
| `ai/` | global `CLAUDE.md`, Claude Code settings, skill lock file |
| `config/` | Ghostty, lsd, gh, Graphite |
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
`~/.config/gh/hosts.yml`, `~/.config/graphite/user_config`, `~/.claude.json`,
`~/.cursor/mcp.json`, `~/.ssh/*`.

### Skills

45 of the 46 installed Claude skills come from other people's repositories.
Vendoring them into a public repo would republish someone else's work, so
`ai/skill-lock.json` records where each came from and `ai/install.sh`
re-fetches them on a new machine. Only self-authored skills live in
`ai/skills/`.

## Notes

- **Node** is managed by Volta, not brew or nvm. `zsh/path.zsh` puts
  `$VOLTA_HOME/bin` ahead of `/opt/homebrew/bin` so Volta's shim wins — brew
  has its own `node` as a transitive dependency. Check with `which -a node`.
- **Volta's installer re-adds** its `PATH` export to `~/.zprofile` and
  `~/.profile` on upgrade. It belongs only in `.zshenv`; delete the duplicates
  if they come back.
- **Cursor and Claude Code rewrite their `settings.json`** when you change
  settings through the UI. They currently write in place, so the symlink
  survives — but if a settings change ever stops showing up in `git status`,
  check whether the symlink was replaced by a real file.

## TODO

- Split work and personal git identity with
  `includeIf "gitdir:~/dev/work/"`. The stub is in
  `git/gitconfig.local.symlink.template`; currently everything commits as
  `lukger1999@gmail.com`.
