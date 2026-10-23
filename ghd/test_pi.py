import importlib.util
import io
import json
import pathlib
import subprocess

import pytest

HERE = pathlib.Path(__file__).parent
spec = importlib.util.spec_from_file_location("pi", HERE / "pi.py")
pi = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pi)


@pytest.mark.parametrize("event, printed, error", [
    ({"type": "message_update", "assistantMessageEvent": {"type": "text_delta", "delta": "Hi"}}, "Hi", None),
    ({"type": "message_update", "assistantMessageEvent": {"type": "thinking_delta", "delta": "hmm"}}, "", None),
    ({"type": "tool_execution_start", "toolCallId": "1", "toolName": "bash", "args": {"command": "git log\n--oneline"}}, "\nbash: git log\n", None),
    ({"type": "tool_execution_start", "toolCallId": "1", "toolName": "codemode", "args": {"code": "x" * 120}}, "\ncodemode: " + "x" * 100 + "…\n", None),
    ({"type": "tool_execution_start", "toolCallId": "1/1", "parentToolCallId": "1", "toolName": "read", "args": {"path": "a"}}, "", None),
    ({"type": "tool_execution_start", "toolCallId": "2", "toolName": "review_pass", "args": {"specialist": "risk", "scope": "s"}}, "\nreview_pass: risk\n", None),
    ({"type": "message_end", "message": {"role": "assistant", "stopReason": "error", "errorMessage": "boom"}}, "", "boom"),
    ({"type": "message_end", "message": {"role": "assistant", "stopReason": "error"}}, "", "pi reported an error"),
    ({"type": "message_end", "message": {"role": "assistant", "stopReason": "stop"}}, "", None),
])
def test_render(event, printed, error):
    out = io.StringIO()
    assert pi.render(json.dumps(event) + "\n", out) == error
    assert out.getvalue() == printed


def test_render_passes_non_json_lines_through():
    out = io.StringIO()
    assert pi.render("plain text\n", out) is None
    assert out.getvalue() == "plain text\n"


def test_extension_helpers():
    result = subprocess.run(["node", "--test", str(HERE / "pi" / "lib.test.ts")], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
