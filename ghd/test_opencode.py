import importlib.util
import io
import json
from pathlib import Path
import subprocess

import pytest

LIB = Path(__file__).parent
spec = importlib.util.spec_from_file_location("opencode", LIB / "opencode.py")
opencode = importlib.util.module_from_spec(spec)
spec.loader.exec_module(opencode)


@pytest.mark.parametrize("event, printed, error", [
    ({"type": "text", "part": {"text": "Reading"}}, "Reading\n", None),
    ({"type": "reasoning", "part": {"text": "Thinking"}}, "", None),
    ({"type": "tool_use", "part": {"tool": "subagent", "state": {"input": {"description": "Security pass"}}}}, "\nsubagent: Security pass\n", None),
    ({"type": "error", "error": {"message": "Token expired"}}, "", "Token expired"),
    ({"type": "error", "error": {"data": {"message": "Unavailable"}}}, "", "Unavailable"),
    ({"type": "error", "error": {}}, "", "OpenCode reported an error"),
])
def test_json_events_render_text_tools_and_provider_errors(event, printed, error):
    out = io.StringIO()
    assert opencode.render(json.dumps(event), out) == error
    assert out.getvalue() == printed


def test_review_plugin_validates_findings_and_enforces_read_only_access():
    result = subprocess.run(["node", "--test", str(LIB / "opencode.test.ts"), str(LIB / "review-lib.test.ts")], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
