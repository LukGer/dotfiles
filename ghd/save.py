#!/usr/bin/env python3
"""Save a follow-up review from a review conversation, next to the original.

Usage: ghd save <owner/repo> <pr> <tool> <markdown file> <findings file>
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time

STORE = os.environ.get("GHD_STORE") or os.path.expanduser("~/.local/share/gh-dash-reviews")


def main(repo: str, pr: str, tool: str, md_file: str, findings_file: str) -> None:
    json.load(open(findings_file))
    pr_json = subprocess.run(["gh", "pr", "view", pr, "--repo", repo, "--json", "headRefOid,title"],
                             capture_output=True, text=True, check=True).stdout
    view = json.loads(pr_json)
    base = f"{STORE}/{time.strftime('%Y%m%d-%H%M%S')}__{repo.replace('/', '_')}__{pr}__{tool}-adhoc"
    n = 1
    while os.path.exists(f"{base}{n if n > 1 else ''}.json"):
        n += 1
    base += str(n) if n > 1 else ""

    shutil.copy(md_file, base + ".md")
    shutil.copy(findings_file, base + ".findings")
    json.dump({"repo": repo, "pr": int(pr), "tool": f"{tool} (ad-hoc)", "sha": view["headRefOid"],
               "title": view["title"], "at": time.strftime("%Y-%m-%d %H:%M")}, open(base + ".json", "w"))
    print(f"Saved ad-hoc review: {base}.md")


if __name__ == "__main__":
    main(*sys.argv[1:6])
