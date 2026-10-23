import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def cli(tmp_path):
    stub = tmp_path / "stub"
    stub.write_text("""#!/usr/bin/env python3
import json, os, pathlib, subprocess, sys
name = pathlib.Path(sys.argv[0]).name
args = sys.argv[1:]
with open(os.environ['CALLS'], 'a') as f:
    f.write(json.dumps([name, *args]) + '\\n')
if name == 'osascript':
    sys.stdin.read()
elif name == 'gh':
    if args[:1] == ['api']:
        endpoint = next(a for a in args if a.startswith('repos/'))
        pull = {'title': 'A review', 'body': 'Closes ABC-1', 'user': {'login': 'author'}, 'head': {'ref': 'feature'}, 'base': {'ref': 'main'}}
        print(json.dumps([pull] if endpoint.split('/')[-1].isdigit() else [[]]))
    else:
        print('A review\\tauthor\\t' + os.environ.get('PR_HEAD', '1234567890') + '\\tmain')
elif name == 'git':
    if os.environ.get('REAL_GIT'):
        os.execv(os.environ['REAL_GIT'], ['git', *args])
    sys.exit(1)
elif name == 'fzf':
    print(os.environ.get('MENU_CHOICE', ''))
elif name == 'tmux':
    if args[0] == '-L' and os.environ.get('TMUX'):
        sys.exit(91)
    if os.environ.get('TMUX_FAIL'):
        sys.exit(1)
    child_env = {**os.environ, 'TERM_PROGRAM': 'tmux'}
    if args[0] == 'display-popup' and (os.environ.get('RUN_POPUP') or
        (os.environ.get('MENU_CHOICE') and args[args.index('-w') + 1] == '64')):
        sys.exit(subprocess.call(args[-1], shell=True, env=child_env))
elif name in ('opencode', 'claude', 'pi'):
    with open(os.environ['CALLS'], 'a') as f:
        f.write(json.dumps(['agent-progress', os.environ.get('GHD_PROGRESS', '')]) + '\\n')
    if os.environ.get('CHECK_AGENT_INPUT'):
        with open(os.environ['CALLS'], 'a') as f:
            f.write(json.dumps(['agent-input', sys.stdin.read()]) + '\\n')
    if os.environ.get('AGENT_FAIL'):
        sys.exit(1)
    if name == 'pi' and os.environ.get('PI_EVENTS'):
        assert args[:3] == ['-p', '--mode', 'json']
        for event in json.loads(os.environ['PI_EVENTS']):
            print(json.dumps(event), flush=True)
    if name == 'claude' and os.environ.get('CLAUDE_EVENTS'):
        events = json.loads(os.environ['CLAUDE_EVENTS'])
        if '--output-format' in args and args[args.index('--output-format') + 1] == 'stream-json':
            assert '--verbose' in args and '--include-partial-messages' in args
            for event in events:
                print(json.dumps(event), flush=True)
        else:
            print(events[-1]['result'])
    if not os.environ.get('MISSING_OUTPUT'):
        for line in args[-1].splitlines():
            for field in ('review_file: ', 'findings_file: '):
                if line.startswith(field):
                    pathlib.Path(line[len(field):]).write_text(os.environ.get('FINDINGS', '{"tldr": "stub", "findings": []}'))
""")
    stub.chmod(0o755)
    for command in ("tmux", "osascript", "fzf", "gh", "git", "opencode", "claude", "pi", "glow"):
        (tmp_path / command).symlink_to(stub)
    calls_file = tmp_path / "calls.jsonl"
    env = {
        **os.environ,
        "PATH": f"{tmp_path}:{ROOT / 'bin'}:{os.environ['PATH']}",
        "CALLS": str(calls_file),
        "TERM_PROGRAM": "ghostty",
        "TMUX": "/tmp/ghd-test,1,0",
        "GHD_STORE": str(tmp_path / "reviews"),
        "GHD_CODE_DIR": str(tmp_path / "clones"),
        "MISE_DATA_DIR": str(tmp_path / "mise"),  # zshenv puts mise's shims first; keep the stubbed pi ahead of the real one
    }

    def run(*args, input_text="x", **overrides):
        calls_file.write_text("")
        result = subprocess.run(
            [str(ROOT / "bin/ghd"), *args], env={**env, **overrides},
            input=input_text, text=True, capture_output=True, timeout=10,
        )
        calls = [json.loads(line) for line in calls_file.read_text().splitlines()]
        return result, calls

    return run


def key_command(key):
    lines = (ROOT / "config/gh-dash/config.yml").read_text().splitlines()
    start = lines.index(f"    - key: {key}")
    return shlex.split(next(line.split("command: ", 1)[1] for line in lines[start:] if "command: " in line))


def test_f_key_opens_a_floating_review_menu(cli):
    command = [arg.replace("{{.RepoName}}", "owner/repo").replace("{{.PrNumber}}", "42")
               for arg in key_command("f")]
    assert command[:3] == ["tmux", "run-shell", "-b"]
    review_command = shlex.split(command[3])
    assert review_command == ["ghd", "review", "owner/repo", "42"]
    result, calls = cli(*review_command[1:])
    assert result.returncode == 0, result.stderr
    menus = [args for name, *args in calls if name == "tmux" and args[0] == "display-popup"]
    assert len(menus) == 1, calls
    assert menus[0][menus[0].index("-w") + 1] == "64"
    assert menus[0][menus[0].index("-h") + 1] == "10"
    assert not any(name in ("fzf", "osascript") for name, *_ in calls)


@pytest.mark.parametrize("key", ["E", "ctrl+o"])
def test_picker_keys_open_popups(cli, key):
    command = [arg.replace("{{.RepoName}}", "owner/repo").replace("{{.PrNumber}}", "42")
               for arg in key_command(key)]
    result, calls = cli(*command[1:])
    assert result.returncode == 0, result.stderr
    popups = [args for name, *args in calls if name == "tmux" and args[0] == "display-popup"]
    assert len(popups) == 1, calls
    assert "-E" in popups[0]
    assert not any(name == "osascript" for name, *_ in calls)


def test_dashboard_starts_in_isolated_tmux_even_from_another_session(cli):
    result, calls = cli("start")
    assert result.returncode == 0, result.stderr
    launches = [args for name, *args in calls if name == "tmux"]
    assert len(launches) == 1, calls
    args = launches[0]
    assert args[:2] == ["-L", "ghd"]
    assert "new-session" in args and "-A" in args
    assert args[-1] == str(ROOT / "ghd/dash")
    assert not any(name == "osascript" for name, *_ in calls)


@pytest.mark.parametrize("terminal", ["ghostty", "Apple_Terminal"])
@pytest.mark.parametrize("exit_code", [0, 1])
def test_dashboard_runs_in_the_calling_terminal(cli, terminal, exit_code):
    result, calls = cli("start", TERM_PROGRAM=terminal, TMUX_FAIL="1" if exit_code else "")
    assert result.returncode == exit_code, result.stderr
    assert len(calls) == 1, calls
    name, *args = calls[0]
    assert name == "tmux"
    assert f"TERM_PROGRAM={terminal}" in args


MODELS = {"pi": "openai-codex/gpt-6.1-sol:high", "opencode": "openai/gpt-6.1-sol#high", "claude": "claude-opus-5-5"}


@pytest.mark.parametrize("tool, mode", [("pi", "-p"), ("opencode", "run"), ("claude", "-p")])
def test_review_finishes_without_an_interactive_agent_prompt(cli, tool, mode):
    result, calls = cli("review", "owner/repo", "42", tool)
    assert result.returncode == 0, result.stderr
    args = next(args for name, *args in calls if name == tool)
    assert mode in args
    assert args[args.index("--model") + 1] == MODELS[tool]
    if tool == "pi":
        assert args[args.index("-e") + 1] == str(ROOT / "ghd/pi/review.ts")
        assert {"save_finding", "finish_review", "review_pass", "codemode"} <= set(args[args.index("--tools") + 1].split(","))
        assert "# PR review" in args[args.index("--append-system-prompt") + 1], "the skill body without its frontmatter"
        assert "---" not in args[args.index("--append-system-prompt") + 1].splitlines()[0]
        assert args[args.index("--append-system-prompt", args.index("--append-system-prompt") + 1) + 1] == str(ROOT / "ghd/pi/orchestrator.md")
    elif tool == "opencode":
        assert args[args.index("--agent") + 1] == "pr-review"
    else:
        assert args[args.index("--mcp-config") + 1] == str(ROOT / "ghd/mcp.json")
        allowed = args[args.index("--allowedTools") + 1].split(",")
        assert "mcp__atlassian__getJiraIssue" in allowed
        output_paths = [line.split(": ", 1)[1] for line in args[-1].splitlines()
                        if line.startswith(("review_file: ", "findings_file: "))]
        assert {rule for rule in allowed if rule.startswith("Edit")} == {
            f"Edit(/{path})" for path in output_paths
        }


@pytest.mark.parametrize("events, stdout, exit_code", [
    ([{"type": "message_update", "assistantMessageEvent": {"type": "text_delta", "delta": "Reading"}},
      {"type": "tool_execution_start", "toolCallId": "1", "toolName": "codemode", "args": {"code": "await tools.read({path: 'a'})\nmore"}},
      {"type": "tool_execution_start", "toolCallId": "1/1", "parentToolCallId": "1", "toolName": "read", "args": {"path": "a"}},
      {"type": "tool_execution_start", "toolCallId": "2", "toolName": "review_pass", "args": {"specialist": "security", "scope": "x"}},
      {"type": "message_end", "message": {"role": "assistant", "stopReason": "toolUse"}}],
     ["Reading", "codemode: await tools.read({path: 'a'})", "review_pass: security"], 0),
    ([{"type": "message_end", "message": {"role": "assistant", "stopReason": "error", "errorMessage": "OAuth refresh failed"}}],
     [], 1),
])
def test_pi_review_streams_text_and_tool_calls_and_surfaces_provider_errors(cli, events, stdout, exit_code):
    result, _ = cli("review", "owner/repo", "42", "pi", PI_EVENTS=json.dumps(events), MISSING_OUTPUT="1" if exit_code else "")
    assert result.returncode == exit_code, result.stderr
    for line in stdout:
        assert line in result.stdout
    assert "read: a" not in result.stdout, "nested calls stay inside their script"
    if exit_code:
        assert "OAuth refresh failed" in result.stderr


@pytest.mark.parametrize("tool", ["pi", "claude", "opencode"])
def test_review_brief_names_the_gathered_packet(cli, tool):
    result, calls = cli("review", "owner/repo", "42", tool)
    assert result.returncode == 0, result.stderr
    brief = next(args for name, *args in calls if name == tool)[-1]
    packet = next(line.removeprefix("packet: ") for line in brief.splitlines() if line.startswith("packet: "))
    text = Path(packet).read_text()
    assert text.startswith("# owner/repo#42 A review") and "Jira: ABC-1" in text and "## Diff" in text


def test_claude_review_displays_interim_text_and_tool_calls(cli):
    events = [
        {"type": "system", "subtype": "init", "session_id": "internal-session"},
        {"type": "stream_event", "event": {"type": "content_block_delta", "delta": {
            "type": "text_delta", "text": "Inspecting the diff."}}},
        {"type": "assistant", "message": {"content": [
            {"type": "text", "text": "Inspecting the diff."},
            {"type": "tool_use", "name": "Bash", "input": {"description": "Read PR diff", "command": "git diff"}},
        ]}},
        {"type": "stream_event", "event": {"type": "content_block_delta", "delta": {
            "type": "text_delta", "text": "Review saved."}}},
        {"type": "result", "is_error": False, "result": "Review saved."},
    ]
    result, _ = cli("review", "owner/repo", "42", "claude", CLAUDE_EVENTS=json.dumps(events))
    assert result.returncode == 0, result.stderr
    assert result.stdout.count("Inspecting the diff.") == 1
    assert "Bash: Read PR diff" in result.stdout
    assert result.stdout.count("Review saved.") == 1
    assert "internal-session" not in result.stdout


@pytest.mark.parametrize("tool", ["pi", "claude", "opencode"])
def test_review_progress_is_recorded_next_to_the_review(cli, tool):
    result, calls = cli("review", "owner/repo", "42", tool)
    assert result.returncode == 0, result.stderr
    agent = next(args for name, *args in calls if name == tool)
    findings = next(line.removeprefix("findings_file: ") for line in agent[-1].splitlines()
                    if line.startswith("findings_file: "))
    assert [args for name, *args in calls if name == "agent-progress"] == [[findings.removesuffix(".findings") + ".progress"]]


@pytest.mark.parametrize("tool", ["pi", "claude", "opencode"])
def test_running_reviewer_cannot_consume_user_input(cli, tool):
    result, calls = cli("review", "owner/repo", "42", tool,
                        CHECK_AGENT_INPUT="1", input_text="\n")
    assert result.returncode == 0, result.stderr
    assert [call for call in calls if call[0] == "agent-input"] == [["agent-input", ""]]


@pytest.mark.parametrize("overrides", [
    {"AGENT_FAIL": "1"}, {"MISSING_OUTPUT": "1"}, {"FINDINGS": '{"findings": [{"file": 1}]}'},
])
def test_unsuccessful_review_does_not_silently_close(cli, tmp_path, overrides):
    result, _ = cli("review", "owner/repo", "42", "opencode", **overrides)
    assert result.returncode != 0
    assert "Press any key" in result.stderr
    assert (result.stdout + result.stderr).count("\a") == 1
    store = tmp_path / "reviews"
    assert not [meta for meta in store.glob("*.json") if not meta.with_suffix(".md").exists()], "orphan metadata"
    assert bool(list(store.glob("*.findings.invalid"))) == ("FINDINGS" in overrides)
    assert not list(store.glob("*.findings"))
    for leftover in [*store.glob("*.packet.md"), *store.glob("*.progress")]:
        assert (store / (leftover.name.split(".")[0] + ".json")).exists(), f"orphan {leftover.name}"


@pytest.mark.parametrize("anchor, valid", [("actual anchor", True), ("wrong anchor", False)])
def test_checked_out_review_validates_findings_against_the_pr_head(cli, tmp_path, anchor, valid):
    origin = tmp_path / "owner/repo"
    origin.mkdir(parents=True)

    def git(*args):
        return subprocess.check_output(["git", "-C", str(origin), *args], text=True).strip()

    git("init", "-q", "-b", "main")
    (origin / "a.txt").write_text("actual anchor\n")
    git("add", "a.txt")
    git("-c", "user.name=test", "-c", "user.email=test@example.com", "-c", "commit.gpgsign=false",
        "-c", "core.hooksPath=/dev/null", "commit", "-qm", "fixture")
    head = git("rev-parse", "HEAD")
    git("update-ref", "refs/pull/42/head", head)
    clones = tmp_path / "clones"
    subprocess.run(["git", "clone", "-q", str(origin), str(clones / "repo")], check=True)
    findings = {"tldr": "Review", "findings": [{
        "file": "a.txt", "line": 1, "anchor": anchor, "category": "bug", "severity": "P1",
        "title": "Finding", "comment": "Comment.",
    }]}
    result, calls = cli("review", "owner/repo", "42", "opencode", input_text="\n",
                        REAL_GIT=shutil.which("git"), PR_HEAD=head, HOME=str(tmp_path),
                        FINDINGS=json.dumps(findings))
    assert "unrecognized arguments" not in result.stderr
    assert (result.returncode == 0) == valid, result.stderr
    assert any(name == "glow" for name, *_ in calls) == valid
    assert bool(list((tmp_path / "reviews").glob("*.findings.invalid"))) == (not valid)
    if not valid:
        assert "anchor does not match a.txt:1" in result.stdout


@pytest.mark.parametrize("earlier_pr, expected", [(42, True), (99, False)])
def test_review_brief_points_at_the_previous_review_of_the_same_pr(cli, tmp_path, earlier_pr, expected):
    store = tmp_path / "reviews"
    store.mkdir()
    base = store / f"20200101-000000__owner_repo__{earlier_pr}__codex"
    base.with_suffix(".json").write_text(json.dumps({
        "repo": "owner/repo", "pr": earlier_pr, "at": "earlier", "tool": "codex", "sha": "abc1234",
    }))
    base.with_suffix(".findings").write_text('{"tldr": "x", "findings": []}')
    result, calls = cli("review", "owner/repo", "42", "claude")
    assert result.returncode == 0, result.stderr
    brief = next(args for name, *args in calls if name == "claude")[-1]
    assert (f"previous_findings: {base}.findings" in brief) == expected
    assert ("previous_sha: abc1234" in brief) == expected
    assert "check: ghd check " in brief


@pytest.mark.parametrize("choice, model", [
    ("GPT-6.1 Sol · high · pi", "openai-codex/gpt-6.1-sol:high"),
    ("Opus 5.5 · high · pi", "anthropic/claude-opus-5-5:high"),
])
def test_menu_launches_review_in_the_dashboard_popup(cli, choice, model):
    result, calls = cli("review", "owner/repo", "42", MENU_CHOICE=choice)
    assert result.returncode == 0, result.stderr
    popups = [args for name, *args in calls if name == "tmux" and args[0] == "display-popup"]
    assert len(popups) == 2, calls
    assert shlex.split(popups[-1][-1])[-4:] == ["owner/repo", "42", "pi", model]
    assert not any(name == "osascript" for name, *_ in calls)


@pytest.mark.parametrize("key, model", [("ctrl+g", "anthropic/claude-opus-5-5:high"), ("ctrl+t", "openai-codex/gpt-6.1-sol:high")])
def test_review_shortcuts_run_in_the_dashboard_popup(cli, key, model):
    command = [arg.replace("{{.RepoName}}", "owner/repo").replace("{{.PrNumber}}", "42")
               for arg in key_command(key)]
    result, calls = cli(*command[1:])
    assert result.returncode == 0, result.stderr
    popup = next(args for name, *args in calls if name == "tmux" and args[0] == "display-popup")
    assert shlex.split(popup[-1])[-4:] == ["owner/repo", "42", "pi", model]
    assert not any(name == "osascript" for name, *_ in calls)


@pytest.mark.parametrize("tool", ["pi", "claude", "opencode"])
def test_completed_review_opens_its_saved_markdown_before_returning(cli, tool):
    result, calls = cli("review", "owner/repo", "42", tool, input_text="\n")
    assert result.returncode == 0, result.stderr
    agent = next(args for name, *args in calls if name == tool)
    markdown = next(line.removeprefix("review_file: ") for line in agent[-1].splitlines()
                    if line.startswith("review_file: "))
    viewers = [args for name, *args in calls if name == "glow"]
    assert len(viewers) == 1, calls
    assert "-p" in viewers[0] and viewers[0][-1] == markdown
    assert result.stdout.count("\a") == 1


def test_saved_review_opens_in_the_current_popup(cli, tmp_path):
    store = tmp_path / "reviews"
    store.mkdir()
    markdown = store / "past.md"
    markdown.write_text("# Past review")
    markdown.with_suffix(".json").write_text(json.dumps({
        "repo": "owner/repo", "pr": 42, "at": "earlier", "tool": "codex", "sha": "1234567890",
    }))
    result, calls = cli("history", MENU_CHOICE=str(markdown), input_text="\n")
    assert result.returncode == 0, result.stderr
    viewers = [args for name, *args in calls if name == "glow"]
    assert len(viewers) == 1, calls
    assert viewers[0][-1] == str(markdown)
    assert not any(name == "osascript" for name, *_ in calls)


def test_popup_can_open_a_ghostty_tab_with_literal_arguments(cli):
    result, calls = cli("open", "popup", str(ROOT / "ghd/open"), "tab", "printf", "hello 'world' $HOME", RUN_POPUP="1")
    assert result.returncode == 0, result.stderr
    surfaces = [args for name, *args in calls if name == "osascript"]
    assert len(surfaces) == 1, calls
    assert shlex.split(surfaces[0][2]) == ["printf", "hello 'world' $HOME"]


@pytest.mark.parametrize("choice, script", [
    ("Past reviews of this PR", "history.py"),
    ("Post to GitHub (pending)", "post.py"),
])
def test_menu_opens_the_selected_picker_in_a_larger_popup(cli, choice, script):
    result, calls = cli("review", "owner/repo", "42", MENU_CHOICE=choice)
    assert result.returncode == 0, result.stderr
    popups = [args for name, *args in calls if name == "tmux" and args[0] == "display-popup"]
    assert len(popups) == 2
    assert popups[-1][popups[-1].index("-w") + 1] == "90%"
    assert shlex.split(popups[-1][-1])[-3:] == [str(ROOT / "ghd" / script), "owner/repo", "42"]
