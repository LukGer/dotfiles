---
name: papercuts
description: Triage and fix the friction agents logged in this repo's PAPERCUTS.md.
disable-model-invocation: true
---

Read `PAPERCUTS.md` at the repo root and work through it with the user. Never
run this unprompted — agents log papercuts, the user decides when they get
fixed.

## Scope

Only this repo's `PAPERCUTS.md`. Papercuts logged outside a repo land in
`~/.papercuts/<dir>.md` — don't act on those, but count their entries and
mention the total at the end so they don't rot unseen.

Entries below a `## Won't fix` heading are settled. Skip them during triage.
If a new entry restates one of them, merge it into the settled entry (append a
`(hit again YYYY-MM-DD)` note) rather than triaging it again.

## Triage

Group the open entries by underlying cause, not by wording — five entries about
five wrong commands in `AGENTS.md` are one fix. Then sort each group into:

**Fix now** — stale docs, a command that no longer exists, a wrong path, a
missing script, an undocumented setup step, a gotcha worth a line in
`AGENTS.md`. The boring majority. This is what the tool is for.

**Real bug** — the friction is a genuine product defect, not repo roughness.
Say so plainly in the report and leave the entry untouched. Don't file a ticket
and don't bury it in won't-fix; the user decides what becomes an issue.

**Won't fix** — real friction, not worth the change. Say why in one line.

## Report, then act

Present the grouped plan and wait for approval. For each group: the fix, the
files it touches, and how many entries it closes. Don't edit anything before
the user approves — a papercut about a misleading error can otherwise turn into
an unreviewed change to shared `AGENTS.md` that the whole team inherits.

After approval:

- Apply the approved fixes.
- Delete the entries they close. There is no archive — a fixed papercut is gone,
  and that's deliberate.
- Move won't-fix entries under `## Won't fix` (create it at the bottom of the
  file if absent) with the one-line reason appended.
- Leave real-bug entries exactly where they are.

Don't commit unless asked.
