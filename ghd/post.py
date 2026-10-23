#!/usr/bin/env python3
"""Pick findings from a saved review and add them to your pending GitHub review.

Usage: ghd post <owner/repo> <pr> [--dry] [--review <findings file>] [--pick 1,3,...]

Never submits: the review stays pending until you submit it on GitHub. An
existing pending review is added to, never replaced.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import subprocess
import sys
import tempfile

from ui import choice, pause, reviewer

STORE = os.environ.get("GHD_STORE") or os.path.expanduser("~/.local/share/gh-dash-reviews")
EMOJI = {"bug": "🐛", "security": "🔒", "risk": "⚠️", "quality": "🧹", "design": "🎨", "completeness": "📋"}
AI_SUFFIX = "(added by AI)"
SEVERITIES = ["P0", "P1", "P2", "P3"]


def parse_patch(patch: str) -> dict[int, tuple[int, str]]:
    lines, hunk, new = {}, -1, 0
    for raw in patch.splitlines():
        header = re.match(r"@@ -\d+(?:,\d+)? \+(\d+)", raw)
        if header:
            hunk += 1
            new = int(header.group(1))
        elif raw.startswith(("-", "\\")):
            continue
        else:
            lines[new] = (hunk, raw[1:])
            new += 1
    return lines


def place(finding: dict, diff: dict[str, dict[int, tuple[int, str]]]) -> dict:
    line = finding.get("line")
    lines = diff.get(finding.get("file"))
    if lines is None:
        return {"kind": "body", "line": line, "note": "file not in diff"}

    anchor = (finding.get("anchor") or "").strip()
    note = ""
    if line not in lines or (anchor and lines[line][1].strip() != anchor):
        hits = [n for n, (_, text) in lines.items() if anchor and text.strip() == anchor]
        if len(hits) != 1:
            return {"kind": "file", "line": line, "note": "line does not match the diff" if anchor else "line not in diff"}
        note = f"line corrected {line} -> {hits[0]}"
        shift, line = hits[0] - line, hits[0]
    else:
        shift = 0

    placed = {"kind": "line", "line": line, "note": note}
    start = finding.get("start_line")
    if start is None or start + shift >= line:
        return placed
    start += shift
    if start in lines and lines[start][0] == lines[line][0]:
        return {"kind": "line", "start_line": start, "line": line, "note": note}
    return {**placed, "note": "; ".join(filter(None, [note, "range dropped"]))}


def comment_text(finding: dict) -> str:
    nit = "nit: " if finding["severity"] == "P3" else ""
    return f"{EMOJI.get(finding['category'], '•')} {nit}{finding['comment']}\n\n{AI_SUFFIX}"


def preselected(finding: dict) -> bool:
    return finding["severity"] != "P3" and finding["category"] != "completeness"


def review_body(tldr: str, folded: list[dict]) -> str:
    parts = [tldr] if tldr else []
    if folded:
        notes = [f"- {EMOJI.get(f['category'], '•')} `{f['file']}:{f['line']}` {f['comment']}" for f in folded]
        parts.append("**Further notes**\n" + "\n".join(notes))
    return "\n\n".join(parts + [AI_SUFFIX]) if parts else ""


def position(placement: dict) -> str:
    if placement["kind"] == "file":
        return "whole file"
    if "start_line" in placement:
        return f"{placement['start_line']}-{placement['line']}"
    return str(placement["line"])


def gh(*args: str, payload: dict | None = None) -> str:
    result = subprocess.run(["gh", *args], capture_output=True, text=True,
                            input=json.dumps(payload) if payload else None)
    if result.returncode:
        raise RuntimeError(result.stderr or result.stdout)
    return result.stdout


def graphql(query: str, **variables) -> dict:
    out = json.loads(gh("api", "graphql", "--input", "-", payload={"query": query, "variables": variables}))
    if out.get("errors"):
        raise RuntimeError("; ".join(e["message"] for e in out["errors"]))
    return out["data"]


PR_QUERY = """query($owner: String!, $name: String!, $number: Int!) {
  repository(owner: $owner, name: $name) { pullRequest(number: $number) {
    id headRefOid reviews(states: PENDING, first: 1) { nodes { id } } } } }"""
CREATE_REVIEW = """mutation($input: AddPullRequestReviewInput!) {
  addPullRequestReview(input: $input) { pullRequestReview { id } } }"""
ADD_THREAD = """mutation($input: AddPullRequestReviewThreadInput!) {
  addPullRequestReviewThread(input: $input) { thread { id } } }"""


def thread_input(finding: dict) -> dict:
    p = finding["placement"]
    thread = {"path": finding["file"], "body": comment_text(finding)}
    if p["kind"] == "file":
        return {**thread, "subjectType": "FILE"}
    thread.update(line=p["line"], side="RIGHT")
    if "start_line" in p:
        thread.update(startLine=p["start_line"], startSide="RIGHT")
    return thread


def diff_files(repo: str, pr: str) -> dict[str, dict[int, tuple[int, str]]]:
    out = gh("api", "--paginate", f"repos/{repo}/pulls/{pr}/files", "--jq", ".[] | {filename, patch}")
    return {d["filename"]: parse_patch(d.get("patch") or "") for d in map(json.loads, out.splitlines())}


def saved_reviews(repo: str, pr: str) -> list[tuple[str, dict]]:
    found = []
    for path in sorted(glob.glob(f"{STORE}/*.findings"), reverse=True):
        try:
            meta = json.load(open(path[: -len(".findings")] + ".json"))
        except (OSError, ValueError):
            continue
        if meta["repo"] == repo and str(meta["pr"]) == str(pr):
            found.append((path, meta))
    return found


def fzf(rows: list[str], *opts: str) -> list[str]:
    out = subprocess.run(["fzf", "--delimiter=\t", "--with-nth=2", "--no-sort", *opts],
                         input="\n".join(rows), stdout=subprocess.PIPE, text=True).stdout
    return [r for r in out.splitlines() if r.strip()]


def pick_review(repo: str, pr: str, review_path: str | None = None) -> tuple[str, dict] | None:
    reviews = saved_reviews(repo, pr)
    if review_path is not None:
        return next((r for r in reviews if os.path.realpath(r[0]) == os.path.realpath(review_path)), None)
    if len(reviews) < 2:
        return reviews[0] if reviews else None
    rows = [f"{i}\t{m['at']}  {reviewer(m):24}  {(m.get('title') or '')[:50]}\t{path[: -len('.findings')]}.md"
            for i, (path, m) in enumerate(reviews)]
    picked = fzf(rows, "--header=Choose the review to post from   enter: select   esc: cancel",
                 "--preview", "glow -s dark -w $FZF_PREVIEW_COLUMNS {3}", "--preview-window=right:55%")
    return reviews[int(picked[0].split("\t")[0])] if picked else None


def picked_by_number(findings: list[dict], pick: str) -> list[dict]:
    """Findings by their 1-based position in the saved review, as the review TUI numbers them."""
    numbers = sorted({int(n) for n in pick.split(",") if n.strip()})
    return [findings[n - 1] for n in numbers if 0 < n <= len(findings)]


def pick_findings(findings: list[dict]) -> list[dict]:
    order = sorted(range(len(findings)), key=lambda i: SEVERITIES.index(findings[i]["severity"]))
    rows, previews = [], {}
    for i in order:
        f, p = findings[i], findings[i]["placement"]
        tag = {"line": "", "file": "  [file comment]", "body": "  [review body]"}[p["kind"]]
        note = f"  [{p['note']}]" if p["note"] else ""
        rows.append(f"{i}\t{EMOJI.get(f['category'], '•')} {f['severity']} {f['category']:12} {f['file']}:{f['line']}  {f['title']}{tag}{note}")
        previews[i] = f"**{f['severity']} {f['category']}** `{f['file']}:{f['line']}`\n\n### {f['title']}\n\n{comment_text(f)}\n\n---\n\n{f.get('detail', '')}"
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as tmp:
        json.dump({str(k): v for k, v in previews.items()}, tmp)
    ticks = "+".join(f"pos({row + 1})+select" for row, i in enumerate(order) if preselected(findings[i]))
    try:
        picked = fzf(rows, "--multi", "--ansi", "--marker=✔ ", "--pointer=▶",
                     f"--bind=load:{ticks}+first" if ticks else "--bind=load:first",
                     "--header=tab: include/exclude   enter: review & confirm   esc: cancel",
                     "--preview", f"jq -r '.[\"{{1}}\"]' {tmp.name} | glow -s dark -w $FZF_PREVIEW_COLUMNS -",
                     "--preview-window=right:55%")
    finally:
        os.unlink(tmp.name)
    return [findings[int(r.split("\t")[0])] for r in picked]


def main(argv: list[str]) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repo")
    parser.add_argument("pr")
    parser.add_argument("--dry", action="store_true")
    parser.add_argument("--review", help="use this saved findings file without a review picker")
    parser.add_argument("--pick", help="post these findings (1-based positions in the saved review) without the picker")
    args = parser.parse_args(argv)
    repo, pr, dry = args.repo, args.pr, args.dry

    picked_review = pick_review(repo, pr, args.review)
    if not picked_review:
        return pause(f"No saved review with findings for {repo}#{pr}. Run one first (ctrl+g / ctrl+t).")
    path, meta = picked_review
    data = json.load(open(path))
    findings = data.get("findings", [])
    if not findings:
        return pause("The saved review has no findings to post.")

    owner, name = repo.split("/")
    pull = graphql(PR_QUERY, owner=owner, name=name, number=int(pr))["repository"]["pullRequest"]
    pending = (pull["reviews"]["nodes"] or [None])[0]
    diff = diff_files(repo, pr)
    for f in findings:
        f["placement"] = place(f, diff)

    chosen = picked_by_number(findings, args.pick) if args.pick else pick_findings(findings)
    if not chosen:
        return
    threads = [f for f in chosen if f["placement"]["kind"] != "body"]
    folded = [f for f in chosen if f["placement"]["kind"] == "body"]
    body = "" if pending else review_body(data.get("tldr", ""), folded)

    B, DIM, YELLOW, R = "\033[1m", "\033[2m", "\033[33m", "\033[0m"
    view = [f"{B}{'Add to your pending review' if pending else 'New pending review'} on {repo}#{pr}{R}",
            f"{DIM}Only you can see it until you submit it on GitHub.{R}\n"]
    if pull["headRefOid"] != meta["sha"]:
        view.append(f"{YELLOW}The PR has new commits since the review ({meta['sha'][:7]} -> {pull['headRefOid'][:7]}). Lines were re-placed by anchor.{R}\n")
    if not pending:
        view += [f"{B}Review body{R}", body or f"{DIM}(none){R}", ""]
    elif folded:
        view += [f"{YELLOW}Not posted, the pending review's body is left alone. Add these yourself:{R}"]
        view += [f"- {f['file']}:{f['line']} {f['comment']}" for f in folded] + [""]
    view.append(f"{B}Comments ({len(threads)}){R}")
    for f in threads:
        view += [f"{DIM}{f['file']} {position(f['placement'])}{R}", comment_text(f), ""]
    print("\n".join(view), flush=True)

    if not threads and not body:
        return pause("Nothing to post.")
    if choice(f"[s] post {len(threads)} comment(s) to the pending review   [c/esc/q] cancel > ", "sc\x1bq") != "s":
        return
    if dry:
        return pause(json.dumps({"review": None if pending else {"pullRequestId": pull["id"], "commitOID": pull["headRefOid"], "body": body},
                                 "threads": [thread_input(f) for f in threads]}, indent=2, ensure_ascii=False))

    review_id = pending["id"] if pending else graphql(CREATE_REVIEW, input={
        "pullRequestId": pull["id"], "commitOID": pull["headRefOid"], "body": body,
    })["addPullRequestReview"]["pullRequestReview"]["id"]
    failed = []
    for f in threads:
        try:
            graphql(ADD_THREAD, input={"pullRequestReviewId": review_id, **thread_input(f)})
        except RuntimeError as error:
            failed.append(f"{f['file']}:{f['line']} {error}")
    posted = len(threads) - len(failed)
    report = [f"{posted} comment(s) added to your pending review. Submit it at https://github.com/{repo}/pull/{pr}/files"]
    pause("\n".join(report + (["\nFailed:"] + failed if failed else [])))


if __name__ == "__main__":
    main(sys.argv[1:])
