import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

spec = importlib.util.spec_from_file_location("chat", Path(__file__).with_name("chat.py"))
chat = importlib.util.module_from_spec(spec)
spec.loader.exec_module(chat)


@pytest.mark.parametrize("model", ["openai/gpt-6.1-sol#high", "claude-agent/opus#high"])
@pytest.mark.parametrize("diff", ["+changed line", "+large diff\n" * 50000])
def test_pr_chat_supplies_snapshot_without_putting_large_diffs_in_arguments(monkeypatch, model, diff):
    view = {"title": "Example", "body": "PR requirements", "url": "https://github.com/o/r/pull/1",
            "headRefName": "feature", "baseRefName": "main", "headRefOid": "abc"}
    def run(command, **kwargs):
        return subprocess.CompletedProcess(command, 0, stdout=json.dumps(view) if command[2] == "view" else diff)

    calls = []
    def call(command, *, cwd, stdin):
        calls.append((command, stdin.read(), cwd))
        return 0

    monkeypatch.setattr(chat.subprocess, "run", run)
    monkeypatch.setattr(chat.subprocess, "call", call)
    monkeypatch.setattr(sys, "argv", ["ghd chat", "o/r", "1", "--model", model])
    assert chat.main() == 0
    command, snapshot, cwd = calls[0]
    assert command[:3] == ["opencode", "mini", "--standalone"]
    assert command[command.index("--agent") + 1] == "ghd-chat"
    assert command[command.index("--model") + 1] == model
    assert diff in snapshot and "PR requirements" in snapshot and "Head when loaded: abc" in snapshot
    assert sum(map(len, command)) < 1000
