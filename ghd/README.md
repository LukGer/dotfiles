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
`mise`, which `script/install` provides. Opening diffs and
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
| `O` | Open the selected PR's active deployment; choose an environment if several exist |
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

## PR stacks

PRs loaded in the same tab are grouped by their base and head branches, with
the base PR first and dependent PRs below it. The group stays where its first
member appeared in the search results. A `┌` / `├` / `└` marker connects the
rows; every PR keeps its own checks, selection and actions.

Grouping uses GitHub branch relationships, so it works without local clones or
stack-tool metadata. It only groups loaded PRs: filters and pagination can hide
other members of a stack. Branch names in different repositories or forks do
not create a group.

## Deployments

The selected PR's Overview shows its GitHub deployment environments, latest
states and URLs, or `Deployments: none`. It reads GitHub's deployments API
through GraphQL using your existing `gh` authentication, for any repository
and deployment provider. The sidebar checks the latest 100 PR commits and
the latest 100 deployments per commit, including the PR's actual or test merge
commit when GitHub provides one.

Press `O` to open the latest active deployment's environment URL. With multiple
environments, choose one with `fzf`; Escape returns to the dashboard. The
command also works as `ghd deployment <owner/repo> <pr>`. It pages through
all PR commits and identifies deployments serving an earlier commit, including
when a newer deployment is still building. Missing URLs, inactive deployments
and API errors stay visible until Enter returns to the dashboard.

`ghd dash` builds gh-dash v4.26.2 with stack grouping and deployment details
from `gh-dash.patch`. The first launch
downloads that release and its Go toolchain through `mise`, then caches the
binary under `${XDG_CACHE_HOME:-~/.cache}/ghd/`. Later launches reuse it;
changing the patch rebuilds it. The installed `gh dash` extension is independent.
Quit and restart `ghd` to load dashboard changes. To update the patched version,
change the release and toolchain in `dash` and rebase `gh-dash.patch`.

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
   commands, `ghd check`, Jira reads and writes to its two output files. Jira
   comes from the Atlassian MCP server in `ghd/mcp.json`; authorise it once
   with `claude --mcp-config ~/.dotfiles/ghd/mcp.json` and `/mcp`. OpenCode
   runs as the `pr-review` agent (`config/opencode/agents/pr-review.md`),
   which loads the same skill from `~/.agents/skills`.
   A second review of the same PR also receives the latest saved findings and
   their commit: the agent reports each earlier finding as fixed, open or
   dropped, skips points that already have a thread on the PR, and lists only
   open and new findings for posting.
3. The agent writes a markdown review and a findings file to
   `~/.local/share/gh-dash-reviews/` (`GHD_STORE` overrides). Each finding has
   a category (`bug`, `security`, `risk`, `quality`, `design`, `completeness`)
   and a severity (`P0`–`P3`, where `P3` is a nitpick). `ghd check <findings>
   [--head <sha>]` validates a findings file, including each anchor against
   the file at `head`; the agent runs it before saving and `ghd review` runs it
   again, keeping an invalid file aside as `.findings.invalid`. A failed run
   leaves no metadata behind.
4. Claude Code and OpenCode run noninteractively in a popup in the dashboard window.
    Typing is hidden and discarded while the agent runs; Ctrl+C cancels.
    Claude's text streams as it is generated, with a summary of each tool call.
    `claude.py` renders its `stream-json` events; plain `claude -p` only prints
    the final response, leaving the live output blank during tool calls.
    Three lines above the agent's output track the review: elapsed time, the
    phase (gather, review with each specialist pass and whether it finished,
    verify, write, check), tool calls so far, and which output files exist.
    The harness reports this, not the agent: Claude Code through `PreToolUse`
    and `PostToolUse` hooks declared in the skill's frontmatter, OpenCode
    through the `ghd-progress` plugin (`ghd/progress-plugin.ts`, linked into
    `~/.config/opencode/plugins/` by `install.sh`), which follows tool calls
    of `ses_ghd…` sessions and their subagents. Both feed `ghd progress`,
    which appends to `<review>.progress`.
    Scroll up with the mouse or trackpad to inspect earlier live output without
    interrupting the agent; `q` returns to live output. The review has its own
    tmux scrollback, keeping up to 50,000 lines, removed when the agent exits.
   When both files are saved, a bell sounds and the markdown opens automatically
   in that popup, with keyboard input restored.
   Reviews render directly in the popup and show the action prompt immediately,
   without a pager to quit first.
   Press `p` to choose findings from this exact review, `c` to
   continue the conversation with the reviewer in its worktree (ask about a
   finding, have it draft a fix, or save a follow-up with `ghd save`), or
   Esc to return to the dashboard. These shortcuts respond immediately,
   without an extra Enter. The worktree is removed when the popup
   closes, so a review opened later from `E` can no longer be continued.
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
| `dash`, `gh-dash.patch` | cached gh-dash build with PR stack grouping and deployment details |
| `deployment.py`, `test_deployment.py` | open active GitHub environments, with CLI tests for selection and failures |
| `open` | Ghostty tabs and windows via AppleScript; tmux popups |
| `review` | menu, worktree, agent launch, cleanup |
| `noninteractive.py` | run the agent with stdin closed, suppress typing and restore terminal input |
| `claude.py` | render Claude's streaming text and tool calls while preserving its exit status |
| `progress.py`, `progress-plugin.ts` | live phase and specialist summary above the agent, from Claude hooks and the OpenCode plugin; `test_progress.py` covers both |
| `view` | read a saved review here, post its findings, or continue its conversation |
| `check.py` | findings validator shared by the agents and `review`; `test_check.py` covers it |
| `mcp.json` | Atlassian MCP server for Claude's Jira reads |
| `config/opencode/agents/pr-review.md` | the OpenCode agent `review` launches |
| `menu` | compact chooser with number shortcuts and no search input |
| `post.py` | finding picker and pending-review GraphQL; `test_post.py` covers placement |
| `history.py`, `save.py` | past reviews with their duration; ad-hoc saves |
| `diff`, `pager`, `info` | diff and description viewers |
| `config/gh-dash/config.yml` | sections and keys |
| `install.sh` | links the OpenCode agent and progress plugin on `dot` runs |
| `test_ui.py` | keybindings, menu actions, popup routing and automatic review completion |
| `test_menu.py` | real tmux/fzf lifecycle: choose a reviewer, read the result and return here |

Tests: `uv run --with pytest pytest ghd`.

The stack regression tests are included in `gh-dash.patch`. From the dotfiles
root, apply it to a clean release and run gh-dash's Go tests:

```sh
dotfiles_root=$PWD
dash_source=$(mktemp -d)
gh api repos/dlvhdr/gh-dash/tarball/v4.26.2 | tar -xz --strip-components=1 -C "$dash_source"
patch -s -d "$dash_source" -p1 < "$dotfiles_root/ghd/gh-dash.patch"
(cd "$dash_source" && mise exec go@1.27.1 -- go test ./internal/...)
rm -rf "$dash_source"
```
