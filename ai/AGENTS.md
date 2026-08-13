# Approach to work

I like "Simple code" that means:

* Passes all the tests.
* Expresses every idea that we need to express.
* Says everything OnceAndOnlyOnce.
* has no superfluous parts

These are called the simplicity rules.

These rules are in conflict with each other. Sometimes to express every idea we can't say everything only once. We look to balance these rules with a focus to future maintainers having an easier time.

Also... it means we work in three stages

* make it work
* make it right
* make it fast

We should always pause and consider if the working code should be improved to make it simpler or to make it faster, but only once we're sure it works

There is no such thing as "pre-existing failures that we don't need to fix"
The decision is always if we fix them in this piece of work or open a quick PR specific to the fix.

* changes that align with our current work: fix in the current PR
* very small off-topic changes: open them in their own PR
* very large changes: open a separate PR, stacking as necessary

The work of software engineering is to keep the software buildable, workable, maintainable, and valuable.

## Context efficiency

- Search with `rg` or `rg --files` before reading files.
- Check file length before reading an unfamiliar file.
- Read targeted line ranges with `sed -n`, not whole files.
- Limit initial reads to 200 lines.
- Never use `cat` on source or log files longer than 300 lines.
- Expand the range only when the current excerpt is insufficient.
- Prefer `git diff`, `git show --stat`, and targeted symbol searches.
- Read an entire file only when its full structure is necessary.

## Token efficiency

- Prefer targeted reads, searches, diffs, and tests.
- Keep command output brief; inspect only relevant failures.
- Never print large logs, generated files, snapshots, or lockfiles.
- Do not reread unchanged content or repeat completed work.
- Delegate only independent work that benefits from parallelism.
- Give subagents narrow scopes and request concise results.
- Start a new session when switching to an unrelated task.

# delegation

Prefer completing straightforward work in the primary agent. Delegate only independent work where parallelism outweighs the additional context and coordination cost.

# tests

i prefer TDD

i don't try to test everything. weigh the value of a test against the speed of testing at that layer.

tests are about protecting future changes as much as validating the current change. every test answers three questions:

* do i know the code does not already do this?
* will i know it does it when i am finished?
* will i know it still does it tomorrow?

IMPORTANT: prefer parameterized tests

# comments

every time we see a comment we ask

* should this be a rename refactoring
* should this be an extract method refactoring

comments are visual noise when they only duplicate information that is present in the code

often applying the simplicity rules removes them

NOTE: never remove comments that are already present in the code, only edit comments you have added

# gh stack

i prefer `gh stack` for git work. the `gh` cli with the `github/gh-stack` extension should always be present on my machines - assume they are available.

prefer `gh stack` over raw git for anything touching a stack - `gh stack rebase`, `gh stack submit`, `gh stack sync`. raw `git rebase` or `git push --force-with-lease` on a stacked branch bypasses stack base tracking and breaks the stack. only fall back to raw git when no `gh stack` equivalent exists.

to inspect a stack without changing anything, use `gh stack view`. there is no `gh stack status` - guessing it just prints the help text.

keep an entire stack in ONE workspace/worktree. never check out a stack branch in a second worktree (including agent-created `git worktree add` or temp worktrees) - a branch parked in another worktree can't be checked out, which breaks `gh stack` mid-command. to work on a different branch of the stack, move within the same workspace using `gh stack up` / `gh stack down` / `gh stack switch` / `gh stack checkout`. after `gh stack rebase`, check which branch HEAD landed on - it can leave you on the bottom branch, parking it.

# time estimates

never estimate time for tasks ("this is a one-day change", "~1 hour of work", "quick fix vs big refactor in time terms"). your training reflects how long humans take, not how long you take. estimate by complexity instead: lines of code touched, number of files, surface area of behaviour change, whether perf benchmarking is needed, etc.

# validating this file has been read

if i say "cuckoo", you say "Phil Haack has taught me well"
# papercuts

when you hit small friction while working — a documented command that doesn't exist, a tool call you had to retry a different way, a confusing or undocumented setup step, a flaky script, a stale cache, a misleading error, a non-obvious gotcha — log it with `papercut "message"`.

do this in the moment, not at the end of the session. none of it is blocking, which is exactly why it goes unreported; logged together it shows where the repo needs sanding down.

two or three sentences: what you were doing → what got in the way → a guess at the cause or fix, if you have one. write for someone who wasn't there. the bar is "it cost me a retry or a wrong turn".

don't log a failure the docs correctly warned you about, or a test that failed because your code was wrong — those are yours, not the repo's. don't stop to fix the friction either: log it and carry on with the task.

reading them back is not your job — the user runs `/papercuts` when they want them triaged.
