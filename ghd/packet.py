#!/usr/bin/env python3
"""Gather a PR's review packet once, deterministically, for every reviewer.

Usage: ghd packet <owner/repo> <pr> <merge_base|none> <head>

Run inside the PR's checkout. With merge_base `none` there is no checkout and
the diff comes from `gh pr diff`. Prints markdown: the window, PR text,
commits, files, Jira keys, existing review threads and the full diff.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from collections.abc import Callable

INSTRUCTION_FILES = re.compile(r"^(\.agents/|\.claude/|\.codex/|AGENTS\.md$|CLAUDE\.md$)|/(AGENTS|CLAUDE)\.md$")
JIRA_KEY = re.compile(r"\b[A-Z][A-Z0-9]+-\d+\b")
THREAD_BODY = 200


def gh_api(endpoint: str, *args: str):
    out = subprocess.run(["gh", "api", "--method", "GET", "--paginate", "--slurp", endpoint, *args],
                         capture_output=True, text=True, check=True).stdout
    pages = json.loads(out)
    return [item for page in pages for item in page] if pages and isinstance(pages[0], list) else pages[0]


def git(cwd, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True).stdout


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
          diff: Callable[[], str] | None = None) -> str:
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
    lines = [
        f"# {repo}#{pr} {view['title']}",
        f"author: {view['user']['login']}  branch: {view['head']['ref']} -> {view['base']['ref']}",
        f"window: {window}",
        f"head: {head}",
        f"Jira: {', '.join(keys) or 'none'}",
    ]
    if flagged:
        lines.append(f"review instructions changed: {flagged}")
    lines += ["", "## Description", view.get("body") or "(empty)", "", "## Commits", *commits, "", "## Files", *files,
              "", "## Existing review threads", *(map(thread_line, threads) or ["none"]), "", "## Diff", "```diff",
              patch.rstrip(), "```", ""]
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    repo, pr, merge_base, head = argv
    sys.stdout.write(build(repo, pr, None if merge_base == "none" else merge_base, head, cwd=None))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:5]))
