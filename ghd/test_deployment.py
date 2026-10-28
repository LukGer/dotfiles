import fcntl
import json
import os
from pathlib import Path
import pty
import select
import struct
import subprocess
import termios
import time

import pytest


ROOT = Path(__file__).resolve().parent.parent


def response(deployments, *, head="current", cursor=None):
    return {"data": {"repository": {"pullRequest": {
        "headRefOid": head,
        "commits": {
            "nodes": [{"commit": {"oid": sha, "deployments": {"nodes": items}}}
                      for sha, items in deployments],
            "pageInfo": {"hasNextPage": cursor is not None, "endCursor": cursor},
        },
    }}}}


def deployment(environment="preview", *, state="ACTIVE", url="https://preview.example.com",
               created="2026-10-21T09:00:00Z"):
    return {"environment": environment, "state": state, "createdAt": created,
            "latestStatus": {"state": "SUCCESS" if state == "ACTIVE" else state,
                             "environmentUrl": url}}


@pytest.fixture
def cli(tmp_path):
    calls = tmp_path / "calls"
    stub = tmp_path / "stub"
    stub.write_text("""#!/usr/bin/env python3
import json, os, pathlib, sys
name = pathlib.Path(sys.argv[0]).name
calls = pathlib.Path(os.environ['CALLS'])
previous = calls.read_text().splitlines() if calls.exists() else []
with calls.open('a') as f:
    f.write(json.dumps([name, *sys.argv[1:]]) + '\\n')
if name == 'gh':
    if os.environ.get('GH_ERROR'):
        print(os.environ['GH_ERROR'], file=sys.stderr)
        sys.exit(1)
    page = sum(json.loads(line)[0] == 'gh' for line in previous)
    print(json.dumps(json.loads(os.environ['RESPONSES'])[page]))
""")
    stub.chmod(0o755)
    for name in ("gh", "open"):
        (tmp_path / name).symlink_to(stub)

    def run(*pages, **overrides):
        env = {**os.environ, "PATH": f"{tmp_path}:{os.environ['PATH']}",
               "CALLS": str(calls), "RESPONSES": json.dumps(pages), **overrides}
        command = [str(ROOT / "bin/ghd"), "deployment", "owner/repo", "42"]
        if "CHOICE" in overrides:
            master, slave = pty.openpty()
            fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 24, 100, 0, 0))
            process = subprocess.Popen(command, env={**env, "TERM": "xterm-256color"},
                                       stdin=slave, stdout=slave, stderr=slave)
            output = b""
            try:
                deadline = time.monotonic() + 10
                sent = False
                while process.poll() is None:
                    assert time.monotonic() < deadline, f"deployment picker did not finish: {output[-500:]!r}"
                    if select.select([master], [], [], .05)[0]:
                        output += os.read(master, 65536)
                    if not sent and b"enter select" in output:
                        choice = overrides["CHOICE"]
                        os.write(master, b"\x1b" if choice == "cancel" else b"j" * int(choice) + b"\r")
                        sent = True
                assert sent, f"deployment picker never appeared: {output[-500:]!r}"
                result = subprocess.CompletedProcess(command, process.returncode, output.decode(), "")
            finally:
                if process.poll() is None:
                    process.kill()
                process.wait(timeout=3)
                os.close(master)
                os.close(slave)
        else:
            result = subprocess.run(command, env=env, input="", capture_output=True, text=True, timeout=10)
        recorded = [json.loads(line) for line in calls.read_text().splitlines()] if calls.exists() else []
        return result, recorded

    return run


def test_opens_the_deployed_site(cli):
    result, calls = cli(response([("current", [deployment()])]))
    assert result.returncode == 0, result.stderr
    assert [call for call in calls if call[0] == "open"] == [["open", "https://preview.example.com"]]
    assert "preview" in result.stdout


@pytest.mark.parametrize("commits, expected_url, revision", [
    ([("current", [deployment(url="https://old.example.com", created="2026-10-20T09:00:00Z"),
                    deployment()])], "https://preview.example.com", "current commit"),
    ([("older", [deployment()]),
      ("current", [deployment(state="IN_PROGRESS", url=None)])],
     "https://preview.example.com", "earlier commit"),
    ([("current", [deployment(state="INACTIVE", url="https://inactive.example.com"),
                    deployment()])], "https://preview.example.com", "current commit"),
])
def test_opens_the_latest_active_deployment(cli, commits, expected_url, revision):
    result, calls = cli(response(commits))
    assert result.returncode == 0, result.stderr
    assert [call for call in calls if call[0] == "open"] == [["open", expected_url]]
    assert revision in result.stdout


@pytest.mark.parametrize("items, message", [
    ([], "No deployments"),
    ([deployment(state="IN_PROGRESS", url=None)], "IN_PROGRESS"),
    ([deployment(state="FAILURE", url=None)], "FAILURE"),
    ([deployment(state="INACTIVE")], "INACTIVE"),
    ([{**deployment(), "latestStatus": None}], "ACTIVE"),
    ([deployment(url="file:///tmp/site")], "No active deployment URL"),
])
def test_explains_why_no_site_can_be_opened(cli, items, message):
    result, calls = cli(response([("current", items)]))
    assert result.returncode == 1
    assert message in result.stdout
    assert not any(call[0] == "open" for call in calls)
    assert "Traceback" not in result.stderr


@pytest.mark.parametrize("choice, expected", [("0", "https://preview.example.com"),
                                             ("1", "https://staging.example.com"),
                                             ("cancel", None)])
def test_chooses_between_environments(cli, choice, expected):
    result, calls = cli(response([("current", [
        deployment(), deployment("staging", url="https://staging.example.com"),
        deployment(url="https://old.example.com", created="2026-10-20T09:00:00Z"),
    ])]), CHOICE=choice)
    assert result.returncode == 0, result.stderr
    assert "Deployment" in result.stdout
    assert [call for call in calls if call[0] == "open"] == ([["open", expected]] if expected else [])


@pytest.mark.parametrize("page, error, message", [
    (response([]), "gh: permission denied", "permission denied"),
    ({"errors": [{"message": "deployment access denied"}]}, "", "deployment access denied"),
    ({"data": {"repository": {"pullRequest": None}}}, "", "PR not found"),
])
def test_reports_github_errors(cli, page, error, message):
    result, calls = cli(page, GH_ERROR=error)
    assert result.returncode == 1
    assert message in result.stderr
    assert "Traceback" not in result.stderr
    assert not any(call[0] == "open" for call in calls)


def test_checks_deployments_beyond_the_first_page_of_commits(cli):
    result, calls = cli(response([], cursor="next-page"),
                        response([("current", [deployment()])]))
    assert result.returncode == 0, result.stderr
    assert [call for call in calls if call[0] == "open"] == [["open", "https://preview.example.com"]]
    requests = [call for call in calls if call[0] == "gh"]
    assert len(requests) == 2
    assert "endCursor=next-page" in requests[1]


@pytest.mark.parametrize("field", ["mergeCommit", "potentialMergeCommit"])
def test_finds_deployments_of_the_pr_merge_commit(cli, field):
    page = response([])
    page["data"]["repository"]["pullRequest"][field] = {
        "oid": "merge", "deployments": {"nodes": [deployment("staging")]},
    }
    result, calls = cli(page)
    assert result.returncode == 0, result.stderr
    assert [call for call in calls if call[0] == "open"] == [["open", "https://preview.example.com"]]
    assert "merge commit" in result.stdout
