---
name: papercuts
description: Triage and fix shared papercuts, optionally scoped to the current repository.
disable-model-invocation: true
---

Run `papercut list --all --json` and work through the entries with the user.
When the user asks for the current repository (for example, `/papercuts current repo`),
add `--current-repo`. This includes entries from all of its worktrees.
Never run this unprompted — agents log papercuts, the user decides when they get
fixed.

## Scope

All instances share `~/.papercuts/papercuts.sqlite`. Without `--current-repo`,
the list includes entries from every repository and from outside Git.
The filter requires running inside a Git repository. Use each entry's `directory` to
locate the source; `repository` identifies its shared Git directory across
worktrees. The current checkout may be unrelated.
If `directory` no longer exists, use `git --git-dir <repository> worktree list`
to find a surviving checkout. Report entries whose source is unavailable and
leave them open.

Entries with status `dismissed` are settled. Skip them during triage.
If an open entry restates one of them, propose dismissing the recurrence with
a reason referencing the settled entry's ID rather than triaging it again.

## Triage

Group open entries by source and underlying cause, not by wording — five entries
about five wrong commands in `AGENTS.md` are one fix. Then sort each group into:

**Fix now** — stale docs, a command that no longer exists, a wrong path, a
missing script, an undocumented setup step, a gotcha worth a line in
`AGENTS.md`. The boring majority. This is what the tool is for.

**Real bug** — the friction is a genuine product defect, not repo roughness.
Say so plainly in the report and leave the entry untouched. Don't file a ticket
and don't bury it in won't-fix; the user decides what becomes an issue.

**Won't fix** — real friction, not worth the change. Say why in one line.

Distinguish a deliberate decision from an issue owned by an external tool or
infrastructure. Record the owner and the useful workaround for external issues;
being outside the repository is not itself a reason to dismiss a fix.

Put recurring repository procedures in the relevant focused documentation and
link it from the workflow that needs it. Put general agent-tool instructions in
their global skill. Keep machine-specific setup out of shared repository files.
Transient failures and command guesses do not need permanent documentation.

## Report, then act

Present the grouped plan and wait for approval. For each group: the fix, the
source repository or directory, files it touches, and entry IDs it closes.
Don't edit anything before the user approves — a papercut about a misleading
error can otherwise turn into an unreviewed change to shared `AGENTS.md` that
the whole team inherits.

After approval:

- Apply the approved fixes.
- Run `papercut resolve <id>...` for entries they close. There is no archive —
  a fixed papercut is gone, and that's deliberate.
- Run `papercut dismiss <id>... --reason "..."` for won't-fix entries.
- Leave real-bug entries open.

Use the CLI for database changes. `papercut --help` lists commands.

Don't commit unless asked.
