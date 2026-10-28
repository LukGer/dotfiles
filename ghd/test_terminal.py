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


LIB = Path(__file__).resolve().parent


@pytest.fixture
def terminal(tmp_path):
    master, slave = pty.openpty()

    def settings():
        attrs = termios.tcgetattr(slave)
        attrs[3] &= ~getattr(termios, "PENDIN", 0)
        return attrs

    original = settings()
    fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 24, 100, 0, 0))
    processes = []
    pending = b""

    def start(command, **env):
        process = subprocess.Popen(
            command, stdin=slave, stdout=slave, stderr=slave,
            env={**os.environ, "TERM": "xterm-256color", "GHD_STORE": str(tmp_path), **env},
        )
        processes.append(process)
        return process

    def expect(text):
        nonlocal pending
        deadline = time.monotonic() + 3
        while text not in pending:
            assert time.monotonic() < deadline, f"terminal never showed {text!r}: {pending[-500:]!r}"
            if select.select([master], [], [], .05)[0]:
                pending += os.read(master, 65536)
        end = pending.index(text) + len(text)
        output, pending = pending[:end], pending[end:]
        return output

    def send(key):
        os.write(master, key)

    yield start, expect, send
    for process in processes:
        if process.poll() is None:
            process.kill()
        process.wait(timeout=3)
    assert settings() == original, "terminal settings were not restored"
    os.close(master)
    os.close(slave)


@pytest.fixture
def posting(tmp_path):
    (tmp_path / "review.md").write_text("# Review summary")
    (tmp_path / "review.json").write_text(json.dumps({
        "repo": "owner/repo", "pr": 42, "sha": "abc", "at": "today", "tool": "claude",
    }))
    (tmp_path / "review.findings").write_text(json.dumps({
        "tldr": "Review summary", "findings": [{
            "file": "f.py", "line": 1, "severity": "P1", "category": "bug",
            "title": "Finding", "comment": "Long comment.\n" * 80,
        }],
    }))
    stub = tmp_path / "stub"
    stub.write_text("""#!/usr/bin/env python3
import json, pathlib, sys
name = pathlib.Path(sys.argv[0]).name
if name == 'gh':
    if sys.argv[1] == 'pr':
        print('OPEN abc')
    elif 'graphql' in sys.argv:
        payload = json.loads(sys.stdin.read())
        if 'mutation' in payload['query']:
            pathlib.Path(__file__).with_name('posted').touch()
            print(json.dumps({'data': {'addPullRequestReview': {'pullRequestReview': {'id': 'review'}}, 'addPullRequestReviewThread': {'thread': {'id': 'thread'}}}}))
            sys.exit(0)
        print(json.dumps({'data': {'repository': {'pullRequest': {
            'id': 'pr', 'headRefOid': 'abc', 'reviews': {'nodes': []}
        }}}}))
    else:
        print(json.dumps({'filename': 'f.py', 'patch': '@@ -1 +1 @@\\n+code'}))
elif name == 'less':
    pathlib.Path(__file__).with_name('pager-used').touch()
    print(sys.stdin.read())
""")
    stub.chmod(0o755)
    for name in ("gh", "less"):
        (tmp_path / name).symlink_to(stub)
    return {"PATH": f"{tmp_path}:{os.environ['PATH']}"}


@pytest.fixture(scope="module", autouse=True)
def built_screen():
    subprocess.run([str(LIB / "tui")], capture_output=True, timeout=600)


@pytest.mark.parametrize("dry", [False, True])
def test_p_posts_without_a_second_confirmation(terminal, posting, tmp_path, dry):
    start, expect, send = terminal
    process = start([str(LIB / "post.py"), "owner/repo", "42", *(["--dry"] if dry else [])], **posting)
    expect(b"p post")
    send(b"p")
    output = expect(b"Posting result")
    assert b"[s] post" not in output
    expect(b'"threads":' if dry else b"comment(s) added to your pending review")
    assert (tmp_path / "posted").exists() != dry
    send(b"\r")
    expect(b"p post")
    send(b"q")
    assert process.wait(timeout=3) == 0


def test_history_opens_findings_in_the_same_terminal(terminal, posting):
    start, expect, send = terminal
    process = start([str(LIB / "history.py"), "owner/repo", "42"], **posting)
    expect(b"Saved reviews")
    expect(b"enter select")
    send(b"\r")
    expect(b"p post")
    send(b"q")
    assert process.wait(timeout=3) == 0
