# ghd: PR dashboard with agent reviews

[gh-dash](https://github.com/dlvhdr/gh-dash) in its own Ghostty window. From
any PR you can open the diff or full description in a tab, run a Claude or
Codex review, and turn the findings you tick into a **pending** GitHub review.

The idea and most of the original scripts are Valentin's; this version swaps
tmux for Ghostty tabs and runs the reviews through the `pr-review` skill.

## Start

```sh
ghd
```

Opens gh-dash in a new Ghostty window. Needs Ghostty 1.3+ (AppleScript), `jq`
(ships with macOS), and `gh`, `fzf`, `glow`, `delta` and the gh-dash
extension, which `script/install` provides. The first run asks whether your shell may control
Ghostty; allow it.

## Keys

| Key | Action |
| --- | --- |
| `ctrl+g` / `ctrl+t` | Claude / Codex review in a new tab |
| `f` | Menu: Claude, Codex, past reviews of this PR, post |
| `E` | Past reviews of every PR: `enter` opens one in a tab, `ctrl-y` copies it |
| `ctrl+o` | Post findings as a pending review |
| `d` / `D` | Diff in a new tab, side by side |
| `i` | Full PR description in a new tab |
| `j` / `k` | Scroll the preview pane |

gh-dash's own keys still work; `?` lists them. Menus and pickers open in a
split below the dashboard and close when you are done.

## Reviews

`ghd review <owner/repo> <pr> [claude|codex]` also works from any shell.

1. Fetches the PR into your clone at `~/dev/<repo>` (`GHD_CODE_DIR` overrides
   `~/dev`) and checks its head out into a detached worktree under
   `~/.cache/ghd/`, with git hooks off. No clone means a diff-only review.
2. Starts the agent there on the `pr-review` skill (`ai/skills/pr-review`). In
   a repo with a `local-review` skill it runs those specialists against
   exactly the PR's diff; elsewhere it does one generic pass. Claude starts
   with `--setting-sources user`, so the PR cannot inject hooks or
   permissions; Codex marks the worktree untrusted.
3. The agent writes a markdown review and a findings file to
   `~/.local/share/gh-dash-reviews/` (`GHD_STORE` overrides). Each finding has
   a category (`bug`, `security`, `risk`, `quality`, `design`, `completeness`)
   and a severity (`P0`–`P3`, where `P3` is a nitpick).
4. The worktree is removed when you quit the agent. Ask it to "save what we
   discussed as an additional review" to add an ad-hoc review beside it.

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

## Files

| File | Role |
| --- | --- |
| `bin/ghd` | dispatcher: `ghd <command>` runs `ghd/<command>` |
| `start`, `open` | the dashboard window; new tabs, splits and windows via AppleScript |
| `review` | menu, worktree, agent launch, cleanup |
| `post.py` | finding picker and pending-review GraphQL; `test_post.py` covers placement |
| `history.py`, `save.py` | past reviews; ad-hoc saves |
| `diff`, `pager`, `info` | diff and description viewers |
| `config/gh-dash/config.yml` | sections and keys |

Tests: `uv run --with pytest pytest ghd`.
