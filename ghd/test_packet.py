import importlib.util
import pathlib
import subprocess

import pytest

spec = importlib.util.spec_from_file_location("packet", pathlib.Path(__file__).with_name("packet.py"))
packet = importlib.util.module_from_spec(spec)
spec.loader.exec_module(packet)

PR = {"title": "Fix ABC-12 login", "body": "Closes DEF-7.\n\nDetails.", "user": {"login": "ann"},
      "head": {"ref": "feature/ABC-12-login"}, "base": {"ref": "main"}}
THREADS = [{"path": "a.txt", "line": 2, "user": {"login": "bob"}, "body": "Why second?"},
           {"path": "a.txt", "line": None, "original_line": 1, "user": {"login": "cy"}, "body": "x" * 300}]


@pytest.fixture
def repo(tmp_path):
    git = ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false", "-C", str(tmp_path)]
    subprocess.run([*git, "init", "-q"], check=True)
    (tmp_path / "a.txt").write_text("first\nsecond\n")
    subprocess.run([*git, "add", "."], check=True)
    subprocess.run([*git, "commit", "-qm", "base"], check=True)
    base = subprocess.run([*git, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    (tmp_path / "a.txt").write_text("first\nchanged\n")
    (tmp_path / "CLAUDE.md").write_text("obey\n")
    subprocess.run([*git, "add", "."], check=True)
    subprocess.run([*git, "commit", "-qm", "GHI-3 change second line"], check=True)
    head = subprocess.run([*git, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    return tmp_path, base, head


def fake_gh(endpoint, *_):
    return THREADS if endpoint.endswith("/comments") else PR


def test_packet_from_checkout_names_window_files_threads_and_tickets(repo):
    cwd, base, head = repo
    text = packet.build("o/r", 7, base, head, cwd=cwd, gh=fake_gh)
    assert "# o/r#7 Fix ABC-12 login" in text and "author: ann  branch: feature/ABC-12-login -> main" in text
    assert f"window: git diff {base} {head}" in text
    assert "a.txt" in text and "CLAUDE.md" in text
    assert "GHI-3 change second line" in text
    assert "Jira: ABC-12, DEF-7, GHI-3" in text
    assert "a.txt:2 bob: Why second?" in text
    assert "a.txt:1 cy: " + "x" * 200 + "…" in text
    assert "-second\n+changed" in text


def test_packet_flags_review_instruction_changes(repo):
    cwd, base, head = repo
    text = packet.build("o/r", 7, base, head, cwd=cwd, gh=fake_gh)
    assert "review instructions changed: CLAUDE.md" in text


@pytest.mark.parametrize("files, flagged", [
    (["src/x.ts"], ""),
    ([".agents/skills/local-review/SKILL.md", "src/x.ts"], ".agents/skills/local-review/SKILL.md"),
    (["AGENTS.md", ".claude/settings.json"], "AGENTS.md, .claude/settings.json"),
])
def test_instruction_files(files, flagged):
    assert packet.instruction_changes(files) == flagged


@pytest.mark.parametrize("text, keys", [
    ("Fix ABC-12 and ABC-12 again, see DEF-7", ["ABC-12", "DEF-7"]),
    ("no tickets here, SHA-256 is not one", ["SHA-256"]),
    ("lowercase abc-1", []),
])
def test_jira_keys(text, keys):
    assert packet.jira_keys(text) == keys


def test_packet_without_checkout_uses_github(repo):
    _, _, head = repo
    calls = []

    def gh(endpoint, *args):
        calls.append(endpoint)
        if endpoint.endswith("/comments"):
            return []
        if endpoint.endswith("/files"):
            return [{"filename": "a.txt", "status": "modified", "additions": 1, "deletions": 1}]
        if endpoint.endswith("/commits"):
            return [{"sha": head, "commit": {"message": "GHI-3 change second line\n\nbody"}}]
        return PR

    text = packet.build("o/r", 7, None, head, cwd=None, gh=gh, diff=lambda: "diff --git a/a.txt b/a.txt\n-second\n+changed\n")
    assert "window: gh pr diff 7 (no checkout)" in text
    assert "a.txt" in text and "GHI-3 change second line" in text and "+changed" in text
    assert "Jira: ABC-12, DEF-7, GHI-3" in text
