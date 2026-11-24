from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import pty
import select
import shutil
import signal
import struct
import subprocess
import sys
import tempfile
import termios
import time
import uuid

import pytest


LIB = Path(__file__).resolve().parent


@pytest.fixture
def terminal(tmp_path):
    with open_terminal(tmp_path) as session:
        yield session


@contextmanager
def open_terminal(tmp_path):
    master, slave = pty.openpty()

    def settings():
        attrs = termios.tcgetattr(slave)
        attrs[3] &= ~getattr(termios, "PENDIN", 0)
        return attrs

    original = settings()

    def resize(width, height):
        fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", height, width, 0, 0))

    resize(100, 24)
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

    try:
        yield start, expect, send, resize
    finally:
        for process in processes:
            if process.poll() is None:
                process.terminate()
            process.wait(timeout=3)
        assert settings() == original, "terminal settings were not restored"
        os.close(master)
        os.close(slave)


@pytest.mark.skipif(not shutil.which("tmux"), reason="needs tmux")
def test_second_dashboard_opens_while_first_shows_a_review(tmp_path, terminal):
    for filename in ("start", "tmux.conf"):
        shutil.copy(LIB / filename, tmp_path)
    dash = tmp_path / "dash"
    dash.write_text('#!/bin/sh\nprintf "Dashboard %s\\n" "$TERM_PROGRAM"\nread -r key\nprintf "Review running\\n"\nread -r key\n')
    dash.chmod(0o755)
    start, expect, send, _ = terminal

    with tempfile.TemporaryDirectory(prefix="ghd-", dir="/tmp") as socket_dir:
        try:
            first = start([str(tmp_path / "start")], TMUX_TMPDIR=socket_dir, TERM_PROGRAM="first")
            expect(b"Dashboard first")
            send(b"\r")
            expect(b"Review running")

            with open_terminal(tmp_path) as (start_second, expect_second, send_second, _):
                second = start_second([str(tmp_path / "start")], TMUX_TMPDIR=socket_dir, TERM_PROGRAM="second")
                assert b"Review running" not in expect_second(b"Dashboard second")
                send_second(b"\x02d")  # Detach with tmux's default prefix.
                assert second.wait(timeout=3) == 0
                active = subprocess.run(["tmux", "-L", f"ghd-{second.pid}", "has-session"],
                                        env={**os.environ, "TMUX_TMPDIR": socket_dir}, capture_output=True, timeout=3)
                assert active.returncode != 0, "detaching left the second dashboard running"

            assert first.poll() is None
            send(b"\r")
            assert first.wait(timeout=3) == 0
        finally:
            for socket in Path(socket_dir).glob("tmux-*/*"):
                subprocess.run(["tmux", "-S", str(socket), "kill-server"], capture_output=True, timeout=3)


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
            'id': 'pr', 'headRefOid': 'abc', 'reviews': {'nodes': []},
            'reviewThreads': {'nodes': [], 'pageInfo': {'hasNextPage': False}}
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


@pytest.mark.parametrize("dry, steps, outcome", [
    (False, [(b"1", None)], b"comment(s) added to your pending review"),
    (True, [(b"1", None)], b'"threads":'),
    (False, [(b"2", None)], b"review posted"),
    (False, [(b"3", b"Approval message"), (b"LGTM", None), (b"\r", None)], b"review approved"),
])
def test_p_posts_the_chosen_way(terminal, posting, tmp_path, dry, steps, outcome):
    start, expect, send, _ = terminal
    process = start([str(LIB / "post.py"), "owner/repo", "42", *(["--dry"] if dry else [])], **posting)
    expect(b"p post")
    send(b"p")
    expect(b"Approve with a message")
    for key, prompt in steps:
        send(key)
        if prompt:
            expect(prompt)
    output = expect(b"Posting result")
    assert b"[s] post" not in output
    expect(outcome)
    assert (tmp_path / "posted").exists() != dry
    send(b"\r")
    expect(b"p post")
    send(b"q")
    assert process.wait(timeout=3) == 0


def test_history_opens_findings_in_the_same_terminal(terminal, posting):
    start, expect, send, _ = terminal
    process = start([str(LIB / "history.py"), "owner/repo", "42"], **posting)
    expect(b"Saved reviews")
    expect(b"enter select")
    send(b"\r")
    expect(b"p post")
    send(b"q")
    assert process.wait(timeout=3) == 0


@pytest.mark.skipif(not shutil.which("tmux"), reason="needs tmux")
def test_review_pane_follows_the_parent_terminal_size(terminal):
    start, expect, send, resize = terminal
    tmux = ["tmux", "-L", f"ghd-test-{uuid.uuid4().hex}", "-f", "/dev/null"]

    def command(*args):
        return subprocess.check_output([*tmux, *args], text=True, timeout=3).strip()

    command("new-session", "-d", "-x", "100", "-y", "24", "sleep", "60")
    client = None
    try:
        if "new-pane" not in command("list-commands"):
            pytest.skip("needs tmux with floating panes")
        command("set-option", "-g", "status", "off")
        pane = command("split-window", "-h", "-P", "-F", "#{pane_id}", "sleep", "60")
        client = start([*tmux, "attach-session"], TMUX="")
        expect("│".encode())
        environment = command("display-message", "-p", "#{socket_path},#{pid},0")
        launcher = start(
            [str(LIB / "open"), "floating", sys.executable, "-u", "-c", """
import os, signal
def report(*_):
    width, height = os.get_terminal_size()
    print(f"review size {width}x{height}")
signal.signal(signal.SIGWINCH, report)
report()
input()
"""],
            TMUX=environment, TMUX_PANE=pane,
        )
        expect(b"review size 88x17")
        review = command("display-message", "-p", "#{window_modal_pane}")
        assert review and review != pane

        def assert_centered(width, height, columns, rows):
            left, top = map(int, command("display-message", "-p", "-t", review, "#{pane_left} #{pane_top}").split())
            assert abs(2 * left + columns - width) <= 1
            assert abs(2 * top + rows - height) <= 1

        assert_centered(100, 24, 88, 17)
        for width, height, columns, rows in [(160, 50, 142, 38), (80, 20, 70, 14)]:
            resize(width, height)
            client.send_signal(signal.SIGWINCH)
            expect(f"review size {columns}x{rows}".encode())
            assert_centered(width, height, columns, rows)

        send(b"\r")
        assert launcher.wait(timeout=3) == 0
        assert command("display-message", "-p", "#{pane_id}") == pane
    finally:
        command("kill-server")
        if client is not None:
            client.wait(timeout=3)
