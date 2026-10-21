import importlib.util
import json
import pathlib
import shutil
import subprocess
import sys

import pytest

LIB = pathlib.Path(__file__).parent
spec = importlib.util.spec_from_file_location("progress", LIB / "progress.py")
progress = importlib.util.module_from_spec(spec)
spec.loader.exec_module(progress)


def claude(event, tool, tool_input, response=None):
    return {"hook_event_name": event, "session_id": "s1", "tool_name": tool,
            "tool_input": tool_input, "tool_response": response}


def opencode(phase, tool, tool_input, output=None):
    return {"sessionID": "s1", "phase": phase, "tool": tool, "input": tool_input, "output": output}


@pytest.mark.parametrize("harness, raw, expected", [
    ("claude", claude("PreToolUse", "Agent", {"description": "Security review", "subagent_type": "general-purpose"}),
     {"kind": "agent_start", "label": "Security review"}),
    ("claude", claude("PreToolUse", "Task", {"description": "Risk review"}), {"kind": "agent_start", "label": "Risk review"}),
    ("claude", claude("PostToolUse", "Agent", {"description": "Security review"}), {"kind": "agent_end", "label": "Security review"}),
    ("claude", claude("PostToolUse", "Edit", {"file_path": "/store/r.findings"}), {"kind": "file", "label": "/store/r.findings"}),
    ("claude", claude("PostToolUse", "Write", {"file_path": "/store/r.md"}), {"kind": "file", "label": "/store/r.md"}),
    ("claude", claude("PostToolUse", "Bash", {"command": "ghd check /store/r.findings --head abc"}, {"stdout": "ok: 3 finding(s)\n"}),
     {"kind": "check", "ok": True}),
    ("claude", claude("PostToolUse", "Bash", {"command": "ghd check /store/r.findings"}, {"stdout": "finding 1: anchor does not match"}),
     {"kind": "check", "ok": False}),
    ("claude", claude("PostToolUse", "Bash", {"command": "git diff"}, {"stdout": ""}), {"kind": "tool", "label": "Bash"}),
    ("claude", claude("PreToolUse", "Bash", {"command": "git diff"}), None),
    ("claude", claude("PostToolUse", "Read", {"file_path": "/x"}), {"kind": "tool", "label": "Read"}),
    ("opencode", opencode("before", "subagent", {"agent": "security-review", "description": "Security pass"}),
     {"kind": "agent_start", "label": "Security pass"}),
    ("opencode", opencode("after", "subagent", {"agent": "security-review", "description": "Security pass"}),
     {"kind": "agent_end", "label": "Security pass"}),
    ("opencode", opencode("after", "edit", {"path": "/store/r.findings"}), {"kind": "file", "label": "/store/r.findings"}),
    ("opencode", opencode("after", "write", {"path": "/store/r.md"}), {"kind": "file", "label": "/store/r.md"}),
    ("opencode", opencode("after", "shell", {"command": "ghd check /store/r.findings"}, "ok: 0 finding(s)"), {"kind": "check", "ok": True}),
    ("opencode", opencode("after", "shell", {"command": "ghd check /store/r.findings"}, "tldr: missing"), {"kind": "check", "ok": False}),
    ("opencode", opencode("after", "read", {"path": "/x"}), {"kind": "tool", "label": "read"}),
    ("opencode", opencode("before", "read", {"path": "/x"}), None),
])
def test_harness_events_normalise_to_review_progress(harness, raw, expected):
    event = progress.normalise(harness, raw)
    if expected is None:
        assert event is None
    else:
        assert event == {"session": "s1", **expected}


def events(*kinds):
    return [{"session": "s1", "kind": kind, "label": label} if kind != "check" else {"session": "s1", "kind": "check", "ok": label}
            for kind, label in kinds]


@pytest.mark.parametrize("recorded, elapsed, expected", [
    ([], 3, ["0:03  starting"]),
    (events(("tool", "Read"), ("tool", "Bash")), 65, ["1:05  gather  ·  2 tool calls"]),
    (events(("tool", "Read"), ("agent_start", "Security"), ("agent_start", "Bugs")), 190,
     ["3:10  review  ·  1 tool call", "Security ●  Bugs ●"]),
    (events(("agent_start", "Security"), ("agent_end", "Security"), ("agent_start", "Bugs")), 200,
     ["3:20  review", "Security ✓  Bugs ●"]),
    (events(("agent_start", "Security"), ("agent_end", "Security")), 300, ["5:00  verify", "Security ✓"]),
    (events(("agent_start", "Security"), ("agent_end", "Security"), ("file", "/s/r.md")), 360,
     ["6:00  write", "Security ✓", "review ✓  findings –"]),
    (events(("file", "/s/r.md"), ("file", "/s/r.findings"), ("check", False)), 400,
     ["6:40  check failed", "review ✓  findings ✓"]),
    (events(("file", "/s/r.findings"), ("check", False), ("file", "/s/r.findings"), ("check", True)), 3725,
     ["1:02:05  check ok", "review –  findings ✓"]),
])
def test_summary_describes_the_review_phase(recorded, elapsed, expected):
    assert progress.summary(recorded, elapsed) == expected


def saved_review(store, session):
    store.mkdir(exist_ok=True)
    base = store / "20261021-120000__owner_repo__42__claude"
    (base.with_suffix(".json")).write_text(json.dumps({"repo": "owner/repo", "pr": 42, "session": session}))
    return base.with_suffix(".progress")


@pytest.mark.parametrize("harness, raw", [
    ("claude", claude("PostToolUse", "Read", {"file_path": "/x"})),
    ("opencode", opencode("after", "read", {"path": "/x"})),
])
@pytest.mark.parametrize("session, recorded", [("s1", True), ("other", False)])
def test_cli_appends_events_to_the_review_of_that_session(tmp_path, harness, raw, session, recorded):
    store = tmp_path / "store"
    file = saved_review(store, session)
    run = subprocess.run([sys.executable, str(LIB / "progress.py"), harness], input=json.dumps(raw), text=True,
                         capture_output=True, env={"GHD_STORE": str(store), "PATH": "/usr/bin:/bin"})
    assert run.returncode == 0, run.stderr
    assert file.exists() == recorded
    if recorded:
        assert [json.loads(line)["kind"] for line in file.read_text().splitlines()] == ["tool"]


def test_cli_ignores_input_it_cannot_parse(tmp_path):
    run = subprocess.run([sys.executable, str(LIB / "progress.py"), "claude"], input="not json", text=True,
                         capture_output=True, env={"GHD_STORE": str(tmp_path), "PATH": "/usr/bin:/bin"})
    assert run.returncode == 0


@pytest.mark.skipif(not shutil.which("bun"), reason="needs bun")
@pytest.mark.parametrize("session, parent, recorded", [
    ("ses_ghd1", None, True), ("ses_child", "ses_ghd1", True), ("ses_other", None, False), ("ses_child2", "ses_other", False),
])
def test_opencode_plugin_forwards_tool_events_of_ghd_sessions(tmp_path, session, parent, recorded):
    store = tmp_path / "store"
    file = saved_review(store, "ses_ghd1")
    harness = tmp_path / "harness.ts"
    harness.write_text(f"""
import plugin from {json.dumps(str(LIB / "progress-plugin.ts"))}
const hooks = {{}}
const sessions = {{ ses_child: {{ parentID: "ses_ghd1" }}, ses_child2: {{ parentID: "ses_other" }} }}
await plugin.setup({{
  tool: {{ hook: async (name, callback) => {{ hooks[name] = callback; return {{ dispose: async () => {{}} }} }} }},
  session: {{ get: async ({{ sessionID }}) => sessions[sessionID] ?? {{}} }},
}})
const base = {{ sessionID: {json.dumps(session)}, agent: "pr-review", id: "call1", messageID: "m1" }}
await hooks["execute.before"]({{ ...base, tool: "subagent", input: {{ agent: "bugs", description: "Bug pass" }} }})
await hooks["execute.after"]({{ ...base, tool: "shell", input: {{ command: "ghd check x" }}, status: "completed", result: {{ output: "ok: 1 finding(s)" }} }})
await hooks["execute.after"]({{ ...base, tool: "read", input: {{ path: "/x" }}, status: "error", error: {{ message: "nope" }} }})
await new Promise((resolve) => setTimeout(resolve, 500))
""")
    run = subprocess.run([shutil.which("bun"), str(harness)], capture_output=True, text=True, env={"GHD_STORE": str(store), "PATH": "/usr/bin:/bin"})
    assert run.returncode == 0, run.stderr
    assert file.exists() == recorded
    if recorded:
        kinds = [json.loads(line)["kind"] for line in file.read_text().splitlines()]
        assert kinds == ["agent_start", "check", "tool"]


def test_claude_hooks_in_the_skill_report_progress():
    frontmatter = (LIB.parent / "ai/skills/pr-review/SKILL.md").read_text().split("---")[1]
    assert "hooks:" in frontmatter
    for event in ("PreToolUse", "PostToolUse"):
        assert f"{event}:" in frontmatter
    assert frontmatter.count("command: ghd progress claude") == 2
