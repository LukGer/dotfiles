#!/usr/bin/env python3
"""Gather a PR's review packet once, deterministically, for every reviewer.

Usage: ghd packet <owner/repo> <pr> <merge_base|none> <head> [previous_sha [previous_merge_base]]

Run inside the PR's checkout. With merge_base `none` there is no checkout and
the diff comes from `gh pr diff`. Prints markdown: the window, PR text,
commits, files, Jira keys, existing review threads and the reviewable diff.
Lockfiles, generated files and huge diffs are listed instead of diffed. The
review mode follows the reviewable size, or the size since `previous_sha`. With
`previous_merge_base`, that delta replays the previous review's changes onto
the current merge base first, so rebasing a stack adds nothing to it.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from collections.abc import Callable
from fnmatch import fnmatchcase

INSTRUCTION_FILES = re.compile(r"^(\.agents/|\.claude/|\.codex/|AGENTS\.md$|CLAUDE\.md$)|/(AGENTS|CLAUDE)\.md$")
JIRA_KEY = re.compile(r"\b[A-Z][A-Z0-9]+-\d+\b")
THREAD_BODY = 200
LOCKFILES = {"package-lock.json", "pnpm-lock.yaml", "yarn.lock", "bun.lock", "bun.lockb", "npm-shrinkwrap.json",
             "Cargo.lock", "go.sum", "poetry.lock", "uv.lock", "Gemfile.lock", "composer.lock", "Podfile.lock", "mise.lock"}
GENERATED = ("gen/*", "*/gen/*", "generated/*", "*/generated/*", "*/__generated__/*", "*.gen.*", "*.generated.*",
             "*.min.js", "*.min.css", "*.map", "*.snap")
LARGE_DIFF = 100_000
SINGLE_PASS_LINES = 200


def gh_api(endpoint: str, *args: str):
    out = subprocess.run(["gh", "api", "--method", "GET", "--paginate", "--slurp", endpoint, *args],
                         capture_output=True, text=True, check=True).stdout
    pages = json.loads(out)
    return [item for page in pages for item in page] if pages and isinstance(pages[0], list) else pages[0]


def git(cwd, *args: str, input: str | None = None) -> str:
    return subprocess.run(["git", *args], cwd=cwd, input=input, capture_output=True, text=True, check=True).stdout


def file_diffs(patch: str) -> dict[str, str]:
    blocks = re.split(r"(?m)^(?=diff --git )", patch)
    return {re.match(r"diff --git a/.* b/(.*)", block).group(1): block for block in blocks if block.startswith("diff --git ")}


def changed_lines(block: str) -> int:
    hunks = block.split("\n@@", 1)
    return sum(line.startswith(("+", "-")) for line in hunks[1].splitlines()) if len(hunks) == 2 else 0


def marked_generated(cwd, paths: list[str]) -> set[str]:
    if not paths:
        return set()
    fields = git(cwd, "check-attr", "--stdin", "-z", "linguist-generated", input="\0".join(paths)).split("\0")
    return {path for path, _, value in zip(fields[::3], fields[1::3], fields[2::3]) if value in ("set", "true")}


def exclusion(path: str, block: str, generated: set[str]) -> str | None:
    if path.rsplit("/", 1)[-1] in LOCKFILES:
        return "lockfile"
    if path in generated or any(fnmatchcase(path, pattern) for pattern in GENERATED):
        return "generated"
    if len(block) > LARGE_DIFF:
        return f"diff over {LARGE_DIFF // 1000} KB"
    return None


def numstat(cwd, start: str, end: str, paths: list[str]) -> list[tuple[str, int, int]]:
    rows = [line.split("\t", 2) for line in git(cwd, "diff", "--numstat", start, end, "--", *paths).splitlines()] if paths else []
    return [(path, int(added) if added != "-" else 0, int(deleted) if deleted != "-" else 0) for added, deleted, path in rows]


def replayed(cwd, previous_base: str, base: str, previous: str) -> str:
    # Exit 1 means conflicts: the tree still exists, with markers in the conflicted files.
    result = subprocess.run(["git", "merge-tree", "--write-tree", f"--merge-base={previous_base}", base, previous],
                            cwd=cwd, capture_output=True, text=True)
    if result.returncode not in (0, 1):
        raise subprocess.CalledProcessError(result.returncode, result.args, result.stdout, result.stderr)
    return result.stdout.split("\n", 1)[0]


def mode(lines: int) -> str:
    return "single" if lines <= SINGLE_PASS_LINES else "specialists"


def jira_keys(text: str) -> list[str]:
    return list(dict.fromkeys(JIRA_KEY.findall(text)))


def instruction_changes(files: list[str]) -> str:
    return ", ".join(f for f in files if INSTRUCTION_FILES.search(f))


def thread_line(thread: dict) -> str:
    body = " ".join(thread.get("body", "").split())
    if len(body) > THREAD_BODY:
        body = body[:THREAD_BODY] + "…"
    line = thread.get("line") or thread.get("original_line")
    return f"- {thread['path']}:{line} {thread['user']['login']}: {body}"


def build(repo: str, pr: int | str, merge_base: str | None, head: str, cwd, gh: Callable = gh_api,
          diff: Callable[[], str] | None = None, previous: str | None = None, previous_base: str | None = None) -> str:
    view = gh(f"repos/{repo}/pulls/{pr}")
    threads = gh(f"repos/{repo}/pulls/{pr}/comments")
    if merge_base:
        window = f"git diff {merge_base} {head}"
        commits = git(cwd, "log", "--format=%h %s", f"{merge_base}..{head}").splitlines()
        files = git(cwd, "diff", "--stat=120", merge_base, head).rstrip().splitlines()
        names = git(cwd, "diff", "--name-only", merge_base, head).split()
        patch = git(cwd, "diff", merge_base, head)
    else:
        window = f"gh pr diff {pr} (no checkout)"
        commits = [f"{c['sha'][:7]} {c['commit']['message'].splitlines()[0]}" for c in gh(f"repos/{repo}/pulls/{pr}/commits")]
        changed = gh(f"repos/{repo}/pulls/{pr}/files")
        files = [f" {f['filename']} | {f['status']} +{f['additions']} -{f['deletions']}" for f in changed]
        names = [f["filename"] for f in changed]
        patch = (diff or (lambda: subprocess.run(["gh", "pr", "diff", str(pr), "--repo", repo],
                                                 capture_output=True, text=True, check=True).stdout))()
    keys = jira_keys(" ".join([view["title"], view["head"]["ref"], view.get("body") or "", *commits]))
    flagged = instruction_changes(names)
    blocks = file_diffs(patch)
    generated = marked_generated(cwd, list(blocks)) if merge_base else set()
    excluded = {path: reason for path, block in blocks.items() if (reason := exclusion(path, block, generated))}
    reviewable = {path: block for path, block in blocks.items() if path not in excluded}
    size = sum(map(changed_lines, reviewable.values()))
    lines = [
        f"# {repo}#{pr} {view['title']}",
        f"author: {view['user']['login']}  branch: {view['head']['ref']} -> {view['base']['ref']}",
        f"window: {window}",
        f"head: {head}",
        f"Jira: {', '.join(keys) or 'none'}",
        f"reviewable: {len(reviewable)} files, {size} changed lines",
    ]
    since = []
    if previous and merge_base:
        start = replayed(cwd, previous_base, merge_base, previous) if previous_base else previous
        delta = [row for row in numstat(cwd, start, head, list(reviewable)) if row[1] + row[2]]
        size = sum(added + deleted for _, added, deleted in delta)
        lines.append(f"previous: {previous} ({len(delta)} reviewable files, {size} changed lines since)")
        since = ["", "## Since previous review",
                 *([f"The previous review's changes ({previous_base}..{previous}) replayed onto the current merge base, "
                    "so base and lower stack layers are not part of the delta."] if previous_base else []),
                 f"`git diff {start} {head} -- <path>`",
                 *(f"- {path} +{added} -{deleted}" for path, added, deleted in delta)]
    lines.append(f"mode: {mode(size)}")
    if flagged:
        lines.append(f"review instructions changed: {flagged}")
    lines += ["", "## Description", view.get("body") or "(empty)", "", "## Commits", *commits, "", "## Files", *files]
    if excluded:
        lines += ["", "## Excluded from the diff",
                  "Not reviewed line by line; generated files are reviewed through their sources. Read one directly when a finding depends on it.",
                  *(f"- {path} ({reason}, {changed_lines(blocks[path])} changed lines)" for path, reason in excluded.items())]
    lines += ["", "## Existing review threads", *(map(thread_line, threads) or ["none"]), *since, "", "## Diff", "```diff",
              "".join(reviewable.values()).rstrip(), "```", ""]
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    repo, pr, merge_base, head, *rest = argv
    previous, previous_base = [None if value == "none" else value for value in (rest + ["none", "none"])[:2]]
    sys.stdout.write(build(repo, pr, None if merge_base == "none" else merge_base, head, cwd=None,
                           previous=previous, previous_base=previous_base))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
