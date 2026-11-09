# ghd: PR dashboard with agent reviews

[gh-dash](https://github.com/dlvhdr/gh-dash) in your current terminal. From
any PR you can open the diff or full description in a tab, chat about its changes,
run a GPT-6.1 Sol or Opus (Claude Code) review, and turn the findings you tick into a
**pending** GitHub review.

The idea and most of the original scripts are Valentin's. This version uses
Ghostty tabs for diffs and descriptions, an isolated tmux session for review
popups, menus and pickers, [OpenCode V2](https://opencode.ai/v2/docs/) as the review harness around the
`pr-review` skill, and a Bubble Tea review screen to watch, read and post.

## Start

```sh
ghd
```

Runs gh-dash in the terminal where you invoke it, inside its own tmux server
(`-L ghd`) with no status bar or personal tmux configuration. Quitting returns
to your existing shell prompt, preserving your configuration and working directory.
Needs `jq` (ships with macOS), `gh`, `tmux` 3.3+, `glow`, `delta` and
`mise`, which `script/install` provides. Opening diffs and
descriptions in Ghostty tabs needs Ghostty 1.3+ (AppleScript); the first such
action asks whether your shell may control Ghostty. In other terminals these
viewers run in place.

## Keys

| Key | Action |
| --- | --- |
| `ctrl+g` / `ctrl+t` | Opus (Claude Code) / GPT-6.1 Sol high review (both through OpenCode) in a popup in this window |
| `c` | Chat with the PR: choose a model, then ask questions about its diff |
| `f` | Menu: review models (then instructions), past reviews of this PR, post, chat |
| `E` | Past reviews of every PR: `enter` reads one here, `ctrl-y` copies it |
| `ctrl+o` | Post findings as a pending review |
| `d` / `D` | Diff in a new tab, side by side |
| `i` | Full PR description in a new tab |
| `O` | Open the selected PR's active deployment; choose an environment if several exist |
| `j` / `k` | Scroll the preview pane |

gh-dash's own keys still work; `?` lists them. The review menu floats in the
centre of the dashboard; choose with `1`–`5` or the arrow keys and enter.
Choosing a model then asks for instructions for this review, such as files to
focus on or skip and concerns to weigh: enter starts the review (leave it empty
for a full review), alt+enter or ctrl+j adds a line, and escape returns to the
models with the draft kept. The menu is `ghd tui menu`, part of the review screen.
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
environments, choose one in the Bubble Tea picker; Escape returns to the dashboard. The
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

## Chat with a PR

Press `c`, or choose **Chat with PR** from `f`, then choose GPT-6.1 Sol or
Opus (Claude Code). OpenCode opens an interactive conversation with the PR description and full
diff attached. It starts with a brief overview; ask follow-up questions directly,
such as “Why did this change?” or “Walk me through the new error handling.”

```sh
ghd chat owner/repo 42
ghd chat owner/repo 42 --model 'openai/gpt-6.1-sol#high'
```

Chat fetches its context through `gh`, so it works without a local clone and
never creates a checkout. The review and chat pickers share the same models;
`--model` accepts OpenCode `provider/model#variant` references.
Opus uses the built-in Claude Agent provider and your Claude Code login.

The conversation uses a snapshot of the description and diff from launch.
It has no tools or access to surrounding repository files; paste extra context
when a question needs it. Large PRs must fit the selected model's context window.
Chat doesn't post anything to GitHub or save a review. OpenCode stores the
conversation; each launch creates a new session with a fresh snapshot. Ctrl+D
exits the minimal interface when the input is empty.

## Reviews

Use OpenCode **2.2.5 or newer** and Claude Code **2.1.248 or newer** for
Claude subscription reviews. See [OpenCode setup and sources](opencode.md).

`ghd review <owner/repo> <pr> [opencode [provider/model#variant]] [--instructions <text>]`
also works from any shell. The dashboard uses OpenCode with
`openai/gpt-6.1-sol#high` or `claude-agent/opus#high`. Opus follows Claude Code's
advertised alias; it is not pinned to a guessed model identifier. Reviews run
only through OpenCode. Human instructions end the brief,
reach every specialist verbatim, and appear in the saved metadata and review.

1. Fetches the PR into your clone at `~/dev/<repo>` (`GHD_CODE_DIR` overrides
   `~/dev`) and checks its head out into a detached worktree under
   `~/.cache/ghd/`, with git hooks off. No clone means a diff-only review.
2. Gathers the **review packet** once with `ghd packet` (`packet.py`): the
   window, PR text, commits, files, Jira keys, existing review threads and
   the full diff, saved as `<review>.packet.md`. Every reviewer reads it
   instead of re-gathering, and it flags changes to `AGENTS.md`, `CLAUDE.md`,
   `.agents/`, `.claude/` or `.codex/` so the human knows the review
   instructions moved.
3. Starts OpenCode's `pr-review` agent in a private server (`--standalone`),
   which receives this review's environment and the exact `pr-review` skill
   path. Native `subagent` calls run scoped passes through `ghd-reviewer`,
   inheriting the selected model. Repository `local-review` rosters, exclusions
   and Deep triggers take precedence; otherwise `ghd/specialists/` provides
   generic correctness, security, risk, quality, design, completeness and deep
   checklists. Code Mode combines independent reads and Jira lookups.
   `ghd/opencode-plugin.ts` adds `save_finding` and `finish_review`: candidates
   are validated and deduplicated before saving, and only the parent session
   can write the final artifacts. Agent permissions deny edits, unlisted shell
   commands, interactive questions and Jira writes; a plugin hook also blocks
   file, git, GitHub and install writes for every session.
   Jira comes from the Atlassian MCP server. `install.sh` registers it if
   missing; authorise it once with `opencode mcp auth atlassian`. Missing access
   is recorded as a coverage gap. Re-reviews receive the previous findings and
   commit, classify each finding as fixed, open or dropped, and skip points
   already discussed on GitHub.

   After discovery, the parent deduplicates candidates and sends one compact
   batch to a fresh cheaper verifier: Luna for OpenAI reviews, Haiku for Claude
   reviews. Set `GHD_VERIFY_MODEL` to override it using the chosen harness's
   model syntax, for example:

   ```sh
   GHD_VERIFY_MODEL=claude-agent/haiku ghd review owner/repo 42 opencode
   ```

   The verifier checks supplied claims with targeted reads, returning confirmed,
   refuted or uncertain with a short reason. The full packet and discovery
   transcripts stay out of its context. At most one escalation batch on the
   selected review model checks disputed P0/P1 findings; there are no debate
   loops. OpenCode enforces the two-stage dispatch limit. The six additional-read
   limit is an instruction to the verifier, not a hard token cap. Unavailable
   verification stays uncertain. Verdicts and model attribution remain in the
   saved findings and evidence pane; disputed or uncertain findings start
   unticked, and contradictory votes remain unticked even after escalation.
   Older reviews without verification retain their previous selection behavior.

4. The findings file at `~/.local/share/gh-dash-reviews/` (`GHD_STORE`
   overrides) holds the TLDR and findings, each with a category (`bug`,
   `security`, `risk`, `quality`, `design`, `completeness`) and a severity
   (`P0`–`P3`, where `P3` is a nitpick), plus the dropped candidates and
   coverage. `ghd check <findings> [--head <sha>]` validates it, including
   each anchor against the file at `head`; `ghd review` runs it again after
   the agent and keeps an invalid file aside as `.findings.invalid`. A failed
   run leaves no metadata behind.
5. On a terminal the review runs inside the **review screen** (`ghd tui`, a
   Bubble Tea program in `ghd/reviewtui/`, built once per source change and
   cached under `~/.cache/ghd/`). While the agent runs it shows elapsed time,
   cost, the phase, each specialist pass as it starts and finishes, findings
   as they are saved, and the streamed transcript with one line per tool
   call; scroll with the arrow keys, `G` follows again, Ctrl+C cancels. Typing
   never reaches the agent. A bell sounds when the review is saved.
   Off a terminal, `opencode.py` renders V2 JSON text and completed tool calls
   and preserves provider failures. The progress plugin reports live specialist
   activity while calls are running.
6. The review screen then shows the findings: a list with checkboxes
   (P0–P2 start ticked, nitpicks and completeness unticked) and, for the
   selected finding, the exact comment that will be posted, the diff hunk at
   head around its anchor, and the reviewer's evidence. Up/Down chooses a
   finding; the mouse wheel, Page Up/Page Down, or dragging the scrollbar
   scrolls the right pane. Long paths, comments, code, and evidence wrap to
   the pane width. `space` ticks, `a`
   and `n` tick all or none, `e` edits the comment in `$EDITOR` and saves it
   back into the findings file, `tab` switches to the full review markdown,
   `p` immediately posts the ticked findings to your pending GitHub review.
   Progress and a scrollable result stay in the review screen; Enter returns
   to the findings. Posted findings are unticked, including after a partial
   failure, so a retry only includes findings that were not posted.
   `c` continues the
   conversation with the reviewer in its worktree (ask about a finding, have
   it explain a fix, or discuss its evidence), and `q` returns to
   the dashboard. The worktree is removed when the popup closes, so a review
   opened later from `E` can no longer be continued. Saved reviews from `E`
   open in the same screen.

The alert uses the standard terminal bell (BEL). In tmux popups it is sent
directly to the attached terminal because popup output does not forward bells.
Ghostty's `bell-features = system` setting plays the macOS alert sound.

To save an additional review from a separate agent conversation, use
`ghd save <repo> <pr> <tool> <markdown file> <findings file>`.

## Posting

`ghd post <owner/repo> <pr> [--dry] [--pick 1,3]`, or `ctrl+o`:

1. Pick the review, then tick findings. Confirmed P0–P2 start ticked; nitpicks,
   completeness and disputed/uncertain findings start unticked. The preview shows the exact comment.
2. Each line is checked against the live PR diff and moved by its anchor text
   when the PR changed. A finding that cannot be placed becomes a whole-file
   comment, or a line in the review body when its file is not in the diff.
3. Press `p` to post. Comments lead with severity, e.g. `[P1] 🐛 <comment>`,
   with `nit:` on P3s, and end with `(added by AI)`. Findings folded into the
   review body also lead with severity. A new review gets the agent's TLDR as its body.
4. An existing pending review is added to, never replaced. Submit it on GitHub.

`--review <findings file>` skips the review picker and uses that saved review,
checking that it belongs to the requested PR; `--pick` names the findings by
their position in that file and posts immediately without interaction. The
review screen supplies both. `--dry` shows the payload without posting.

Saved-review and deployment pickers, previews, filtering (`/`), clipboard
copying (`ctrl+y` in history), and message screens all run in Bubble Tea.
Python handles fetching and posting data. `--json` returns a posting report
with its message and the 1-based positions that were successfully posted.

## Files

| File | Role |
| --- | --- |
| `bin/ghd` | dispatcher: `ghd <command>` runs `ghd/<command>` |
| `start`, `tmux.conf` | isolated dashboard session in the current terminal |
| `dash`, `gh-dash.patch` | cached gh-dash build with PR stack grouping and deployment details |
| `deployment.py`, `test_deployment.py` | open active GitHub environments, with CLI tests for selection and failures |
| `open` | Ghostty tabs and windows via AppleScript; tmux popups |
| `review` | menu dispatch, instructions, worktree, packet, agent launch, cleanup |
| `chat.py` | model picker and interactive OpenCode conversation over a PR description and diff, without a checkout |
| `packet.py`, `test_packet.py` | the review packet every reviewer reads |
| `review-lib.ts`, `review-lib.test.ts` | shared validation, verification budget and markdown helpers, tested with `node --test` |
| `specialists/`, `verification.md` | generic specialist checklists and the bounded verification contract |
| `opencode-plugin.ts`, `opencode.test.ts` | validated review persistence and read-only guards for OpenCode |
| `opencode.py`, `test_opencode.py` | render V2 events and verify the plugin |
| `tui`, `reviewtui/` | menus, pickers, message and review screens: cached Go build, Bubble Tea program with its own `go test` suite |
| `noninteractive.py` | run OpenCode with stdin closed, suppress typing and restore terminal input |
| `progress.py`, `progress-plugin.ts` | progress events (`<review>.progress`) from the OpenCode plugin and the live progress pane; covered by `test_progress.py` |
| `view` | open a saved review in the review screen, or print it off a terminal |
| `check.py` | findings validator shared by the agents, `save_finding` and `review`; `test_check.py` covers it |
| `config/opencode/agents/pr-review.md` | the OpenCode agent `review` launches |
| `post.py` | saved-review dispatch, noninteractive posting, and pending-review GraphQL; `test_post.py` covers posting and placement |
| `history.py`, `save.py` | past reviews with their duration; ad-hoc saves |
| `diff`, `pager`, `info` | diff and description viewers |
| `config/gh-dash/config.yml` | sections and keys |
| `install.sh` | links the OpenCode agents and plugins and registers Atlassian MCP on `dot` runs |
| `test_ui.py` | keybindings, menu actions, popup routing and automatic review completion |
| `test_menu.py` | real tmux lifecycle: choose a reviewer, give instructions, read the result and return here |

Tests: `uv run --with pytest pytest ghd` (includes the `node --test` run of the
shared review helpers and OpenCode plugin) and `mise exec go@1.27.1 -- go test ./...` in `ghd/reviewtui`.

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
