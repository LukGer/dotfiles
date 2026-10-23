#!/usr/bin/env python3
"""Browse saved reviews, newest first, with whether the PR moved since.

Usage: ghd history [<owner/repo> <pr>]
enter opens a review here, ctrl-y copies it to the clipboard.
"""
from __future__ import annotations

import glob
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

from ui import reviewer

STORE = os.environ.get("GHD_STORE") or os.path.expanduser("~/.local/share/gh-dash-reviews")
LIB = os.path.dirname(os.path.realpath(__file__))


def gh(*args: str) -> str | None:
    r = subprocess.run(["gh", *args], capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else None


def current(key: tuple[str, int]) -> tuple[str | None, str | None]:
    out = gh("pr", "view", str(key[1]), "--repo", key[0], "--json", "state,headRefOid", "-q", '.state + " " + .headRefOid')
    return tuple(out.split(" ")) if out else (None, None)


def status(meta: dict, cur: tuple[str | None, str | None]) -> str:
    state, head = cur
    if state is None:
        return "\033[2munknown\033[0m"
    if state != "OPEN":
        return f"\033[35m{state.lower()}\033[0m"
    if head == meta["sha"]:
        return "\033[32mup to date\033[0m"
    n = gh("api", f"repos/{meta['repo']}/compare/{meta['sha']}...{head}", "--jq", ".ahead_by")
    if n is None:
        return "\033[33mforce-pushed\033[0m"
    return f"\033[33m{n} new commit{'s' if n != '1' else ''}\033[0m"


def duration(meta: dict) -> str:
    seconds = meta.get("seconds")
    return f"{seconds // 60}m{seconds % 60:02d}s" if seconds is not None else ""


def main(argv: list[str]) -> None:
    only = tuple(argv[:2]) if len(argv) >= 2 else None
    metas = []
    for path in sorted(glob.glob(f"{STORE}/*.json"), reverse=True):
        meta = json.load(open(path))
        meta["file"] = path[: -len(".json")] + ".md"
        if os.path.exists(meta["file"]) and (not only or (meta["repo"], str(meta["pr"])) == only):
            metas.append(meta)
    if not metas:
        print("No saved reviews yet.")
        input("\nPress enter to close...")
        return

    keys = sorted({(m["repo"], m["pr"]) for m in metas})
    with ThreadPoolExecutor(8) as pool:
        cur = dict(zip(keys, pool.map(current, keys)))
        states = list(pool.map(lambda m: status(m, cur[(m["repo"], m["pr"])]), metas))
    rows = [f"{m['file']}\t{m['at']}  {m['repo']}#{m['pr']}  {reviewer(m):24}  {duration(m):>7}  {(m.get('title') or '')[:55]:55}  {s}"
            for m, s in zip(metas, states)]

    picked = subprocess.run(
        ["fzf", "--ansi", "--delimiter=\t", "--with-nth=2", "--no-sort",
         "--header=enter: read review   ctrl-y: copy   esc: close",
         "--bind", "ctrl-y:execute-silent(pbcopy < {1})+change-header(Copied to clipboard.)",
         "--preview", "glow -s dark -w $FZF_PREVIEW_COLUMNS {1}", "--preview-window=right:60%"],
        input="\n".join(rows), stdout=subprocess.PIPE, text=True,
    ).stdout.strip()
    if picked:
        meta = next(m for m in metas if m["file"] == picked.split("\t")[0])
        os.execv(f"{LIB}/view", [f"{LIB}/view", meta["repo"], str(meta["pr"]), meta["file"]])


if __name__ == "__main__":
    main(sys.argv[1:])
