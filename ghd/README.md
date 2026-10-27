# ghd: PR dashboard with agent reviews

[gh-dash](https://github.com/dlvhdr/gh-dash) in your current terminal. From
any PR you can open the diff or full description in a tab, run a GPT-6.1 Sol or
Opus 5.5 review, and turn the findings you tick into a **pending** GitHub review.

The idea and most of the original scripts are Valentin's. This version uses
Ghostty tabs for diffs and descriptions, an isolated tmux session for review
popups, menus and pickers, [pi](https://pi.dev) as the review harness around the
`pr-review` skill, and a Bubble Tea review screen to watch, read and post.

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
| `ctrl+g` / `ctrl+t` | Opus 5.5 / GPT-6.1 Sol high review (both through pi) in a popup in this window |
| `f` | Menu: models with their harnesses (then instructions for that review), past reviews of this PR, post |
| `E` | Past reviews of every PR: `enter` reads one here, `ctrl-y` copies it |
| `ctrl+o` | Post findings as a pending review |
| `d` / `D` | Diff in a new tab, side by side |
| `i` | Full PR description in a new tab |
| `O` | Open the selected PR's active deployment; choose an environment if several exist |
| `j` / `k` | Scroll the preview pane |

gh-dash's own keys still work; `?` lists them. The review menu floats in the
centre of the dashboard; choose with `1`–`4` or the arrow keys and enter.
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

`ghd review <owner/repo> <pr> [pi [provider/model[:thinking]] | opencode | claude] [--instructions <text>]`
also works from any shell. `--instructions` carries the menu's instructions:
they end the brief, every pi specialist pass receives them verbatim, and the
review's metadata, markdown and screen show them. The dashboard runs every review through pi; the
picker lists GPT-6.1 Sol (high) first and Opus 5.5 (high) second, and both
pin the model explicitly. `opencode` and `claude` remain available from the
shell as single-pass reviewers on the same skill.

1. Fetches the PR into your clone at `~/dev/<repo>` (`GHD_CODE_DIR` overrides
   `~/dev`) and checks its head out into a detached worktree under
   `~/.cache/ghd/`, with git hooks off. No clone means a diff-only review.
2. Gathers the **review packet** once with `ghd packet` (`packet.py`): the
   window, PR text, commits, files, Jira keys, existing review threads and
   the full diff, saved as `<review>.packet.md`. Every reviewer reads it
   instead of re-gathering, and it flags changes to `AGENTS.md`, `CLAUDE.md`,
   `.agents/`, `.claude/` or `.codex/` so the human knows the review
   instructions moved.
3. Starts the agent in the worktree on the `pr-review` skill
   (`ai/skills/pr-review`). Under pi the skill body and `ghd/pi/orchestrator.md`
   are the system prompt and `ghd/pi/review.ts` is loaded as an extension that
   gives the orchestrator three tools:
   - `review_pass` runs one specialist (`correctness`, `deep`, `security`,
     `risk`, `quality`, `design`, `completeness`) in a separate read-only pi
     session and returns its verified candidates. The orchestrator launches
     every in-scope pass at once from one codemode script. In a repository
     with `.agents/skills/local-review`, its roster, launch conditions and
     Deep trigger apply and each pass runs on the repository's own review
     skill (`bugs-review`, `risk-review`, ...) passed as `skill`; elsewhere the
     generic checklists in `ghd/pi/specialists/` apply. `ghd/pi/specialist.md`
     carries the harness rules every pass gets.
   - `save_finding` records one verified finding and runs `ghd check` on it,
     so a wrong anchor or line comes straight back to the model. Duplicates
     of saved findings are rejected.
   - `finish_review` takes the TLDR, dropped candidates, the since-last-review
     table, which passes ran, and coverage gaps, writes the markdown and
     findings files and ends the run.
   A `tool_call` hook blocks `edit`, `write`, and git, GitHub, file and
   install writes in `bash` for the orchestrator and every pass; blocked
   commands fail closed with a reason. Jira comes from the Atlassian MCP
   server that `install.sh` registers with pi; authorise it once with
   `pi mcp login atlassian`. Without it the review records an access gap.
   Claude starts with `--setting-sources user` and preapproved reads; OpenCode
   runs as the `pr-review` agent (`config/opencode/agents/pr-review.md`).
   A second review of the same PR also receives the latest saved findings and
   their commit: the agent reports each earlier finding as fixed, open or
   dropped, skips points that already have a thread on the PR, and lists only
   open and new findings for posting.
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
   Off a terminal (scripts, tests) the agent streams through `pi.py` instead,
   which also turns pi's silent provider errors into a failing exit status.
6. The review screen then shows the findings: a list with checkboxes
   (P0–P2 start ticked, nitpicks and completeness unticked) and, for the
   selected finding, the exact comment that will be posted, the diff hunk at
   head around its anchor, and the reviewer's evidence. Up/Down chooses a
   finding; the mouse wheel, Page Up/Page Down, or dragging the scrollbar
   scrolls the right pane. Long paths, comments, code, and evidence wrap to
   the pane width. `space` ticks, `a`
   and `n` tick all or none, `e` edits the comment in `$EDITOR` and saves it
   back into the findings file, `tab` switches to the full review markdown,
   `p` posts the ticked findings through `ghd post --pick`, `c` continues the
   conversation with the reviewer in its worktree (ask about a finding, have
   it draft a fix, or save a follow-up with `ghd save`), and `q` returns to
   the dashboard. The worktree is removed when the popup closes, so a review
   opened later from `E` can no longer be continued. Saved reviews from `E`
   open in the same screen.

The alert uses the standard terminal bell (BEL). In tmux popups it is sent
directly to the attached terminal because popup output does not forward bells.
Ghostty's `bell-features = system` setting plays the macOS alert sound.

To save an additional review from a separate agent conversation, use
`ghd save <repo> <pr> <tool> <markdown file> <findings file>`.

### pi setup

`config/mise/config.toml` pins `@earendil-works/pi-coding-agent` 1.4.0; run
`mise install` after pulling. `ghd review` starts pi with `--no-extensions`
and adds back only the `codemode` and `mcp` built-ins plus `ghd/pi/review.ts`
(specialist passes get `codemode` and the extension), so personal pi packages
such as `pi-mcp-adapter` or `context-mode`, which do not load on pi 1.x,
cannot break a review. `--tools` is restricted to `read`, `bash`, `codemode`,
the review tools and `mcp__atlassian__*`. Skills, `AGENTS.md` and your
`~/.pi/agent/auth.json` logins still apply.

## Posting

`ghd post <owner/repo> <pr> [--dry] [--pick 1,3]`, or `ctrl+o`:

1. Pick the review, then tick findings. P0–P2 start ticked; nitpicks and
   completeness start unticked. The preview shows the exact comment.
2. Each line is checked against the live PR diff and moved by its anchor text
   when the PR changed. A finding that cannot be placed becomes a whole-file
   comment, or a line in the review body when its file is not in the diff.
3. Confirm with `s`. Comments read `🐛 <comment>`, with `nit:` on P3s, and end
   with `(added by AI)`. A new review gets the agent's TLDR as its body.
4. An existing pending review is added to, never replaced. Submit it on GitHub.

`--review <findings file>` skips the review picker and uses that saved review,
checking that it belongs to the requested PR; `--pick` names the findings by
their position in that file and skips the finding picker. The review screen
supplies both.

## Files

| File | Role |
| --- | --- |
| `bin/ghd` | dispatcher: `ghd <command>` runs `ghd/<command>` |
| `start`, `tmux.conf` | isolated dashboard session in the current terminal |
| `dash`, `gh-dash.patch` | cached gh-dash build with PR stack grouping and deployment details |
| `deployment.py`, `test_deployment.py` | open active GitHub environments, with CLI tests for selection and failures |
| `open` | Ghostty tabs and windows via AppleScript; tmux popups |
| `review` | menu dispatch, instructions, worktree, packet, agent launch, cleanup |
| `packet.py`, `test_packet.py` | the review packet every reviewer reads |
| `pi/review.ts`, `pi/lib.ts`, `pi/lib.test.ts` | pi extension: `review_pass`, `save_finding`, `finish_review`, the read-only guard, progress events; pure helpers tested with `node --test` |
| `pi/orchestrator.md`, `pi/specialist.md`, `pi/specialists/` | system prompt additions for the orchestrator, every pass, and the generic specialist checklists |
| `pi.py`, `test_pi.py` | stream pi's JSON events off a terminal and fail on provider errors |
| `tui`, `reviewtui/` | the review menu and review screen: cached Go build, Bubble Tea program with its own `go test` suite |
| `noninteractive.py` | run claude and opencode with stdin closed, suppress typing and restore terminal input |
| `claude.py` | render Claude's streaming text and tool calls while preserving its exit status |
| `progress.py`, `progress-plugin.ts` | progress events (`<review>.progress`) from Claude hooks and the OpenCode plugin, and the pane above those agents; the pi extension writes the same events itself; `test_progress.py` covers both |
| `view` | open a saved review in the review screen, or print it off a terminal |
| `check.py` | findings validator shared by the agents, `save_finding` and `review`; `test_check.py` covers it |
| `mcp.json` | Atlassian MCP server for Claude's Jira reads |
| `config/opencode/agents/pr-review.md` | the OpenCode agent `review` launches |
| `post.py` | finding picker, `--pick`, and pending-review GraphQL; `test_post.py` covers placement |
| `history.py`, `save.py` | past reviews with their duration; ad-hoc saves |
| `diff`, `pager`, `info` | diff and description viewers |
| `config/gh-dash/config.yml` | sections and keys |
| `install.sh` | links the OpenCode agent and progress plugin and registers pi's Atlassian MCP server on `dot` runs |
| `test_ui.py` | keybindings, menu actions, popup routing and automatic review completion |
| `test_menu.py` | real tmux lifecycle: choose a reviewer, give instructions, read the result and return here |

Tests: `uv run --with pytest pytest ghd` (includes the `node --test` run of the
pi helpers) and `mise exec go@1.27.1 -- go test ./...` in `ghd/reviewtui`.

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
