#!/usr/bin/env python3
"""Validate a findings file before ghd accepts it.

Usage: ghd check <findings file> [--head <sha>]

With --head, run inside the PR's checkout: every anchor must be the text of
its line at that commit. Reviewers run this before saving; ghd review runs it
again before opening the result.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys

CATEGORIES = ("bug", "security", "risk", "quality", "design", "completeness")
SEVERITIES = ("P0", "P1", "P2", "P3")
REQUIRED = {"file": str, "line": int, "anchor": str, "category": str, "severity": str, "title": str, "comment": str}


def line_at(head: str, path: str, line: int, cwd: str | None = None) -> str | None:
    shown = subprocess.run(["git", "show", f"{head}:{path}"], capture_output=True, text=True, cwd=cwd)
    lines = shown.stdout.splitlines()
    return lines[line - 1] if not shown.returncode and 0 < line <= len(lines) else None


def problems(data, head: str | None = None, cwd: str | None = None) -> list[str]:
    if not isinstance(data, dict):
        return ["the file is not a JSON object"]
    found = [] if isinstance(data.get("tldr"), str) and data["tldr"].strip() else ["tldr: missing"]
    findings = data.get("findings")
    if not isinstance(findings, list):
        return found + ["findings: missing list"]
    for n, finding in enumerate(findings, 1):
        if not isinstance(finding, dict):
            found.append(f"finding {n}: not an object")
            continue
        missing = [key for key, kind in REQUIRED.items()
                   if not isinstance(finding.get(key), kind) or (kind is str and not finding[key].strip())]
        found += [f"finding {n}: {key} missing" for key in missing]
        for key, allowed in (("category", CATEGORIES), ("severity", SEVERITIES)):
            if key not in missing and finding[key] not in allowed:
                found.append(f"finding {n}: {key} {finding[key]} is not one of {', '.join(allowed)}")
        start = finding.get("start_line")
        if start is not None and (not isinstance(start, int) or "line" in missing or start >= finding["line"]):
            found.append(f"finding {n}: start_line must be below line")
        if head and not {"file", "line", "anchor"} & set(missing):
            actual = line_at(head, finding["file"], finding["line"], cwd)
            pointer = f"{finding['file']}:{finding['line']}"
            if actual is None:
                found.append(f"finding {n}: {pointer} does not exist at {head[:7]}")
            elif actual.strip() != finding["anchor"].strip():
                found.append(f"finding {n}: anchor does not match {pointer} at {head[:7]}: {actual.strip()!r}")
    return found


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("findings")
    parser.add_argument("--head")
    args = parser.parse_args(argv)
    try:
        data = json.load(open(args.findings))
    except (OSError, ValueError) as error:
        found = [f"{args.findings}: not valid JSON ({error})"]
    else:
        found = problems(data, args.head)
    if found:
        print("\n".join(found))
        return 1
    print(f"ok: {len(data['findings'])} finding(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
