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


def commit(cwd, files: dict[str, str], message="change") -> str:
    git = ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false", "-C", str(cwd)]
    for name, content in files.items():
        (cwd / name).parent.mkdir(parents=True, exist_ok=True)
        (cwd / name).write_text(content)
    subprocess.run([*git, "add", "."], check=True)
    subprocess.run([*git, "commit", "-qm", message], check=True)
    return subprocess.run([*git, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()


@pytest.mark.parametrize("path, reason", [
    ("src/app.ts", None),
    ("packages/hub/src/gen/schemas/a.json", "generated"),
    ("gen/client.ts", "generated"),
    ("src/routeTree.gen.ts", "generated"),
    ("src/__generated__/types.ts", "generated"),
    ("src/__snapshots__/a.test.ts.snap", "generated"),
    ("marked/output.ts", "generated"),
    ("pnpm-lock.yaml", "lockfile"),
    ("sub/package-lock.json", "lockfile"),
    ("go.sum", "lockfile"),
    ("src/huge.ts", "diff over 100 KB"),
])
def test_generated_lockfiles_and_huge_diffs_are_listed_instead_of_diffed(repo, path, reason):
    cwd, _, base = repo
    commit(cwd, {".gitattributes": "marked/** linguist-generated\n"})
    base = subprocess.run(["git", "-C", str(cwd), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    content = "x = 1;\n" * (20_000 if "huge" in path else 1)
    head = commit(cwd, {path: content})
    text = packet.build("o/r", 7, base, head, cwd=cwd, gh=fake_gh)
    diff = text.split("## Diff", 1)[1]
    assert (f"diff --git a/{path}" in diff) == (reason is None)
    assert (f"- {path} ({reason}" in text) == (reason is not None)
    assert f"reviewable: {0 if reason else 1} files" in text


@pytest.mark.parametrize("lines, mode", [(1, "single"), (200, "single"), (201, "specialists")])
def test_mode_follows_the_reviewable_size(repo, lines, mode):
    cwd, _, base = repo
    head = commit(cwd, {"src/app.ts": "x\n" * lines, "pnpm-lock.yaml": "y\n" * 1000})
    text = packet.build("o/r", 7, base, head, cwd=cwd, gh=fake_gh)
    assert f"reviewable: 1 files, {lines} changed lines" in text
    assert f"\nmode: {mode}\n" in text


@pytest.mark.parametrize("lines, mode", [(5, "single"), (300, "specialists")])
def test_rereview_scopes_mode_and_delta_to_changes_since_the_previous_review(repo, lines, mode):
    cwd, base, _ = repo
    previous = commit(cwd, {"src/app.ts": "x\n" * 500})
    head = commit(cwd, {"src/new.ts": "y\n" * lines, "pnpm-lock.yaml": "z\n" * 1000})
    text = packet.build("o/r", 7, base, head, cwd=cwd, gh=fake_gh, previous=previous)
    assert f"previous: {previous} (1 reviewable files, {lines} changed lines since)" in text
    since = text.split("## Since previous review", 1)[1].split("## Diff", 1)[0]
    assert f"git diff {previous} {head} --" in since and "- src/new.ts +" in since
    assert "src/app.ts" not in since and "pnpm-lock.yaml" not in since
    assert f"\nmode: {mode}\n" in text


@pytest.mark.parametrize("rebase_aware, mode", [(True, "single"), (False, "specialists")])
def test_rereview_after_a_stack_rebase_ignores_changes_from_the_lower_layer(repo, rebase_aware, mode):
    cwd, _, _ = repo
    git = ["git", "-C", str(cwd)]
    original = [f"a{i}" for i in range(1000)]
    lower = [f"lower{i}" if i < 300 else line for i, line in enumerate(original)]
    mine = lambda lines: "\n".join(f"pr{i}" if i >= 900 else line for i, line in enumerate(lines)) + "\n"
    old_base = commit(cwd, {"src/app.ts": "\n".join(original) + "\n"})
    previous = commit(cwd, {"src/app.ts": mine(original)})
    subprocess.run([*git, "checkout", "-q", old_base], check=True)
    base = commit(cwd, {"src/app.ts": "\n".join(lower) + "\n"}, "lower layer moved")
    commit(cwd, {"src/app.ts": mine(lower)}, "rebased onto the lower layer")
    head = commit(cwd, {"src/new.ts": "y\n" * 5})
    text = packet.build("o/r", 7, base, head, cwd=cwd, gh=fake_gh, previous=previous,
                        previous_base=old_base if rebase_aware else None)
    since = text.split("## Since previous review", 1)[1].split("## Diff", 1)[0]
    assert "- src/new.ts +5 -0" in since
    assert ("src/app.ts" in since) == (not rebase_aware)
    assert f"\nmode: {mode}\n" in text
