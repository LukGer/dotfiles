# ghd: PR dashboard with agent reviews

[gh-dash](https://github.com/dlvhdr/gh-dash) in your current terminal. From
any PR you can open the diff or full description in a tab, run a GPT-6.1 Sol or
Opus 5.5 review, and turn the findings you tick into a **pending** GitHub review.

The idea and most of the original scripts are Valentin's. This version uses
Ghostty tabs for diffs and descriptions, an isolated tmux session for review
popups, menus and pickers, and the `pr-review` skill for reviews.

## Start

```sh
ghd
```

Runs gh-dash in the terminal where you invoke it, inside its own tmux server
(`-L ghd`) with no status bar or personal tmux configuration. Quitting returns
to your existing shell prompt, preserving your configuration and working directory.
Needs `jq` (ships with macOS), `gh`, `tmux` 3.3+, `fzf`, `glow`, `delta` and
the gh-dash extension, which `script/install` provides. Opening diffs and
descriptions in Ghostty tabs needs Ghostty 1.3+ (AppleScript); the first such
action asks whether your shell may control Ghostty. In other terminals these
viewers run in place.

## Keys

| Key | Action |
| --- | --- |
| `ctrl+g` / `ctrl+t` | Opus 5.5 (Claude Code) / GPT-6.1 Sol high (OpenCode) review in a popup in this window |
| `f` | Menu: models with their harnesses, past reviews of this PR, post |
| `E` | Past reviews of every PR: `enter` reads one here, `ctrl-y` copies it |
| `ctrl+o` | Post findings as a pending review |
| `d` / `D` | Diff in a new tab, side by side |
| `i` | Full PR description in a new tab |
| `j` / `k` | Scroll the preview pane |

gh-dash's own keys still work; `?` lists them. The review menu floats in the
centre of the dashboard; choose with `1`–`4` or the arrow keys and enter.
The `f` key launches it through a background tmux job so gh-dash resumes
rendering behind the popup instead of staying suspended on a blank screen.
History and posting pickers open in floating popups and close when you are done.
Escape or `q` cancels the chooser. It uses a modal popup because
[`tmux display-menu` returns immediately in tmux 3.8](https://github.com/tmux/tmux/blob/3.8/cmd-display-menu.c#L553),
allowing gh-dash to repaint over an open native menu.
To open URLs while tmux captures the mouse, use Cmd+Shift+click in Ghostty.

## Reviews

`ghd review <owner/repo> <pr> [opencode|claude]` also works from any shell.
The picker lists GPT-6.1 Sol (high thinking, OpenCode) first and Opus 5.5
(Claude Code) second. Both launches pin the model explicitly.

1. Fetches the PR into your clone at `~/dev/<repo>` (`GHD_CODE_DIR` overrides
   `~/dev`) and checks its head out into a detached worktree under
   `~/.cache/ghd/`, with git hooks off. No clone means a diff-only review.
2. Starts the agent there on the `pr-review` skill (`ai/skills/pr-review`). In
   a repo with a `local-review` skill, this personal orchestrator uses the repo's
   specialist guidelines and launch conditions against exactly the PR's diff.
   It gathers shared context once, scopes parallel passes, and consolidates
   verified findings without changing the repo's skills. Elsewhere it does one
   generic pass. Claude starts
   with `--setting-sources user`, so the PR cannot inject hooks or
   permissions. Its headless run preapproves the GitHub reads, git inspection
    commands and writes to its two output files. OpenCode reads the skill from
    this dotfiles checkout and uses its configured permissions.
3. The agent writes a markdown review and a findings file to
   `~/.local/share/gh-dash-reviews/` (`GHD_STORE` overrides). Each finding has
   a category (`bug`, `security`, `risk`, `quality`, `design`, `completeness`)
   and a severity (`P0`–`P3`, where `P3` is a nitpick).
4. Claude Code and OpenCode run noninteractively in a popup in the dashboard window.
    Typing is hidden and discarded while the agent runs; Ctrl+C cancels.
    Scroll up with the mouse or trackpad to inspect earlier live output without
    interrupting the agent; `q` returns to live output. The review has its own
    tmux scrollback, keeping up to 50,000 lines, removed when the agent exits.
   When both files are saved, a bell sounds and the markdown opens automatically
   in that popup, with keyboard input restored.
   Short reviews show the posting prompt immediately. For longer reviews,
   scroll to the end to advance automatically; `q` also leaves the reader early.
   Press `p` and enter to choose findings from this exact review, or enter to
   return to the dashboard. The worktree is removed when the popup closes.
   Failed runs or missing output pause with
   an error until you press a key. Saved reviews from `E` use the same reader
   and posting prompt.

The alert uses the standard terminal bell (BEL). In tmux popups it is sent
directly to the attached terminal because popup output does not forward bells.
Ghostty's `bell-features = system` setting plays the macOS alert sound.

To save an additional review from a separate agent conversation, use
`ghd save <repo> <pr> <tool> <markdown file> <findings file>`.

## Posting

`ghd post <owner/repo> <pr> [--dry]`, or `ctrl+o`:

1. Pick the review, then tick findings. P0–P2 start ticked; nitpicks and
   completeness start unticked. The preview shows the exact comment.
2. Each line is checked against the live PR diff and moved by its anchor text
   when the PR changed. A finding that cannot be placed becomes a whole-file
   comment, or a line in the review body when its file is not in the diff.
3. Confirm with `s`. Comments read `🐛 <comment>`, with `nit:` on P3s, and end
   with `(added by AI)`. A new review gets the agent's TLDR as its body.
4. An existing pending review is added to, never replaced. Submit it on GitHub.

`--review <findings file>` skips the review picker and uses that saved review,
checking that it belongs to the requested PR. The completion prompt supplies
this automatically.

## Files

| File | Role |
| --- | --- |
| `bin/ghd` | dispatcher: `ghd <command>` runs `ghd/<command>` |
| `start`, `tmux.conf` | isolated dashboard session in the current terminal |
| `open` | Ghostty tabs and windows via AppleScript; tmux popups |
| `review` | menu, worktree, agent launch, cleanup |
| `noninteractive.py` | run the agent with stdin closed, suppress typing and restore terminal input |
| `view` | read a saved review here and optionally post its findings |
| `menu` | compact chooser with number shortcuts and no search input |
| `post.py` | finding picker and pending-review GraphQL; `test_post.py` covers placement |
| `history.py`, `save.py` | past reviews; ad-hoc saves |
| `diff`, `pager`, `info` | diff and description viewers |
| `config/gh-dash/config.yml` | sections and keys |
| `test_ui.py` | keybindings, menu actions, popup routing and automatic review completion |
| `test_menu.py` | real tmux/fzf lifecycle: choose a reviewer, read the result and return here |

Tests: `uv run --with pytest pytest ghd`.
