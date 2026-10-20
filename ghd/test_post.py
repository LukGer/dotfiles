import importlib.util
import json
import os
import pathlib
import subprocess

import pytest

spec = importlib.util.spec_from_file_location("post", pathlib.Path(__file__).with_name("post.py"))
post = importlib.util.module_from_spec(spec)
spec.loader.exec_module(post)

PATCH = "\n".join([
    "@@ -1,3 +1,4 @@",
    " a",
    "-b",
    "+B",
    "+C",
    " d",
    "@@ -20,2 +21,3 @@",
    " x",
    "+y",
    "+y",
    "\\ No newline at end of file",
])
DIFF = {"f.ts": post.parse_patch(PATCH)}


@pytest.mark.parametrize("review, message", [
    ("older", "The saved review has no findings to post."),
    ("newer", "The saved review has no findings to post."),
    ("other-pr", "No saved review with findings for owner/repo#42."),
])
def test_post_cli_uses_the_requested_review_without_opening_a_picker(tmp_path, review, message):
    store = tmp_path / "reviews"
    store.mkdir()
    for name, pr in (("older", 42), ("newer", 42), ("other-pr", 99)):
        (store / f"{name}.json").write_text(json.dumps({
            "repo": "owner/repo", "pr": pr, "at": name, "tool": "codex",
        }))
        (store / f"{name}.findings").write_text('{"findings": []}')
    marker = tmp_path / "picker-was-opened"
    fzf = tmp_path / "fzf"
    fzf.write_text(f"#!/usr/bin/env python3\nfrom pathlib import Path\nPath({str(marker)!r}).touch()\n")
    fzf.chmod(0o755)
    result = subprocess.run(
        [str(pathlib.Path(__file__).with_name("post.py")), "owner/repo", "42", "--review", str(store / f"{review}.findings")],
        env={**os.environ, "GHD_STORE": str(store), "PATH": f"{tmp_path}:{os.environ['PATH']}"},
        input="\n", text=True, capture_output=True, timeout=5,
    )
    assert result.returncode == 0, result.stderr
    assert not marker.exists(), "the newly completed review should not need another review picker"
    assert message in result.stdout


def test_parse_patch_keeps_new_side_lines_with_their_hunk():
    assert DIFF["f.ts"] == {
        1: (0, "a"), 2: (0, "B"), 3: (0, "C"), 4: (0, "d"),
        21: (1, "x"), 22: (1, "y"), 23: (1, "y"),
    }


@pytest.mark.parametrize("finding, expected", [
    ({"file": "f.ts", "line": 2, "anchor": "B"},
     {"kind": "line", "line": 2, "note": ""}),
    ({"file": "f.ts", "line": 2},
     {"kind": "line", "line": 2, "note": ""}),
    ({"file": "f.ts", "line": 9, "anchor": "  C "},
     {"kind": "line", "line": 3, "note": "line corrected 9 -> 3"}),
    ({"file": "f.ts", "line": 9, "anchor": "nope"},
     {"kind": "file", "line": 9, "note": "line does not match the diff"}),
    ({"file": "f.ts", "line": 9, "anchor": "y"},
     {"kind": "file", "line": 9, "note": "line does not match the diff"}),
    ({"file": "f.ts", "line": 9},
     {"kind": "file", "line": 9, "note": "line not in diff"}),
    ({"file": "other.ts", "line": 2, "anchor": "B"},
     {"kind": "body", "line": 2, "note": "file not in diff"}),
    ({"file": "f.ts", "start_line": 1, "line": 3, "anchor": "C"},
     {"kind": "line", "start_line": 1, "line": 3, "note": ""}),
    ({"file": "f.ts", "start_line": 3, "line": 5, "anchor": "d"},
     {"kind": "line", "start_line": 2, "line": 4, "note": "line corrected 5 -> 4"}),
    ({"file": "f.ts", "start_line": 3, "line": 21, "anchor": "x"},
     {"kind": "line", "line": 21, "note": "range dropped"}),
    ({"file": "f.ts", "start_line": 3, "line": 3, "anchor": "C"},
     {"kind": "line", "line": 3, "note": ""}),
])
def test_place(finding, expected):
    assert post.place(finding, DIFF) == expected


@pytest.mark.parametrize("category, severity, expected", [
    ("bug", "P1", "🐛 Off by one.\n\n(added by AI)"),
    ("quality", "P3", "🧹 nit: Off by one.\n\n(added by AI)"),
    ("unknown", "P2", "• Off by one.\n\n(added by AI)"),
])
def test_comment_text(category, severity, expected):
    finding = {"category": category, "severity": severity, "comment": "Off by one."}
    assert post.comment_text(finding) == expected


@pytest.mark.parametrize("category, severity, expected", [
    ("security", "P0", True),
    ("bug", "P2", True),
    ("quality", "P3", False),
    ("completeness", "P1", False),
])
def test_preselected(category, severity, expected):
    assert post.preselected({"category": category, "severity": severity}) is expected


@pytest.mark.parametrize("tldr, folded, expected", [
    ("", [], ""),
    ("Looks good.", [], "Looks good.\n\n(added by AI)"),
    ("", [{"category": "risk", "severity": "P2", "file": "x.ts", "line": 4, "comment": "Slow."}],
     "**Further notes**\n- ⚠️ `x.ts:4` Slow.\n\n(added by AI)"),
])
def test_review_body(tldr, folded, expected):
    assert post.review_body(tldr, folded) == expected
