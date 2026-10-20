import importlib.util
import pathlib
import subprocess

import pytest

spec = importlib.util.spec_from_file_location("check", pathlib.Path(__file__).with_name("check.py"))
check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check)

VALID = {"file": "a.txt", "line": 2, "anchor": "second", "category": "bug", "severity": "P1",
         "title": "Title", "comment": "Comment."}


@pytest.mark.parametrize("data, expected", [
    ({"tldr": "ok", "findings": []}, []),
    ({"tldr": "ok", "findings": [VALID, {**VALID, "start_line": 1}]}, []),
    ("nope", ["the file is not a JSON object"]),
    ({"findings": []}, ["tldr: missing"]),
    ({"tldr": "ok"}, ["findings: missing list"]),
    ({"tldr": "ok", "findings": [1]}, ["finding 1: not an object"]),
    ({"tldr": "ok", "findings": [{**VALID, "line": "2", "comment": " "}]},
     ["finding 1: line missing", "finding 1: comment missing"]),
    ({"tldr": "ok", "findings": [{**VALID, "severity": "high"}]},
     ["finding 1: severity high is not one of P0, P1, P2, P3"]),
    ({"tldr": "ok", "findings": [{**VALID, "category": "style"}]},
     ["finding 1: category style is not one of bug, security, risk, quality, design, completeness"]),
    ({"tldr": "ok", "findings": [{**VALID, "start_line": 2}]}, ["finding 1: start_line must be below line"]),
])
def test_problems(data, expected):
    assert check.problems(data) == expected


@pytest.fixture
def head(tmp_path):
    git = ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false"]
    subprocess.run([*git, "init", "-q"], cwd=tmp_path, check=True)
    (tmp_path / "a.txt").write_text("first\nsecond\n")
    subprocess.run([*git, "add", "."], cwd=tmp_path, check=True)
    subprocess.run([*git, "commit", "-qm", "x"], cwd=tmp_path, check=True)
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=tmp_path, capture_output=True, text=True).stdout.strip()


@pytest.mark.parametrize("finding, expected", [
    (VALID, ""),
    ({**VALID, "anchor": "  second  "}, ""),
    ({**VALID, "anchor": "first"}, "anchor does not match a.txt:2 at {head}: 'second'"),
    ({**VALID, "line": 3}, "a.txt:3 does not exist at {head}"),
    ({**VALID, "file": "b.txt"}, "b.txt:2 does not exist at {head}"),
])
def test_anchors_are_checked_against_head(tmp_path, head, finding, expected):
    found = check.problems({"tldr": "ok", "findings": [finding]}, head, cwd=tmp_path)
    assert found == ([f"finding 1: {expected.format(head=head[:7])}"] if expected else [])


@pytest.mark.parametrize("content, code, message", [
    ('{"tldr": "ok", "findings": []}', 0, "ok: 0 finding(s)"),
    ("{", 1, "not valid JSON"),
    ('{"findings": []}', 1, "tldr: missing"),
])
def test_cli(tmp_path, content, code, message):
    findings = tmp_path / "r.findings"
    findings.write_text(content)
    result = subprocess.run([str(pathlib.Path(__file__).with_name("check.py")), str(findings)],
                            capture_output=True, text=True)
    assert result.returncode == code
    assert message in result.stdout
