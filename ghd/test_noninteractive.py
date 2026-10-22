import os
import fcntl
import json
from pathlib import Path
import pty
import select
import shutil
import signal
import struct
import subprocess
import sys
import termios
import time
from types import SimpleNamespace

import pytest


RUNNER = Path(__file__).with_name("noninteractive.py")


@pytest.mark.parametrize("outcome, exit_code", [("success", 0), ("failure", 1), ("interrupt", 130)])
def test_terminal_input_is_restored_and_cleared_on_exit(tmp_path, outcome, exit_code):
    release = tmp_path / "release"
    master, slave = pty.openpty()
    original = termios.tcgetattr(slave)
    agent = """
import pathlib, sys, time
assert sys.stdin.read() == ''
print('READY', flush=True)
while not pathlib.Path(sys.argv[1]).exists():
    time.sleep(.01)
sys.exit(int(sys.argv[2]))
"""
    process = subprocess.Popen(
        [sys.executable, str(RUNNER), sys.executable, "-c", agent, str(release), str(exit_code)],
        stdin=slave, stdout=slave, stderr=slave,
    )
    try:
        assert select.select([master], [], [], 5)[0], "agent did not start"
        assert b"READY" in os.read(master, 65536)
        os.write(master, b"ignored\n")
        assert not select.select([master], [], [], .1)[0], "typing was echoed"
        if outcome == "interrupt":
            process.send_signal(signal.SIGINT)
        else:
            release.touch()
        assert process.wait(timeout=5) == exit_code
        assert termios.tcgetattr(slave) == original
        assert not select.select([slave], [], [], 0)[0], "typing was left queued for the viewer"
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)
        os.close(master)
        os.close(slave)


LIVE_AGENT = """
import os, pathlib, sys, time
assert sys.stdin.read() == ''
for number in range(200):
    print(f'REVIEW-LINE-{number:03}', flush=True)
print('REVIEW-RUNNING', flush=True)
pathlib.Path(sys.argv[1]).write_text(os.environ['TMUX'].split(',')[0])
while not pathlib.Path(sys.argv[2]).exists():
    time.sleep(.01)
sys.exit(int(sys.argv[3]))
"""


@pytest.fixture
def live_review(tmp_path):
    """Starts the runner inside a fake dashboard tmux and returns its handles."""
    socket_file = tmp_path / "socket"
    release = tmp_path / "release"
    master, slave = pty.openpty()
    fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 20, 80, 0, 0))
    started = []

    def start(exit_code=0, agent_command=None, **env):
        process = subprocess.Popen(
            [sys.executable, str(RUNNER), *(agent_command or [sys.executable, "-c", LIVE_AGENT]),
             str(socket_file), str(release), str(exit_code)],
            stdin=slave, stdout=slave, stderr=slave,
            env={**os.environ, "TMUX": "/outer-dashboard,1,0", "TERM": "xterm-256color", **env},
        )
        started.append(process)

        def wait_for(predicate):
            deadline = time.monotonic() + 5
            while not predicate():
                assert time.monotonic() < deadline, "live review did not reach the expected state"
                if select.select([master], [], [], .02)[0]:
                    os.read(master, 65536)

        wait_for(socket_file.exists)
        socket = socket_file.read_text()
        assert socket != "/outer-dashboard", "live output has no independent scrollback"

        def tmux(*args):
            return subprocess.check_output(["tmux", "-S", socket, *args], text=True).strip()

        return SimpleNamespace(process=process, master=master, socket=socket, tmux=tmux, wait_for=wait_for, release=release)

    yield start
    release.touch()
    for process in started:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)
    os.close(master)
    os.close(slave)


@pytest.mark.skipif(not shutil.which("tmux"), reason="needs tmux")
@pytest.mark.parametrize("outcome, exit_code", [("success", 0), ("failure", 7), ("interrupt", 130)])
def test_live_review_can_scroll_without_interrupting_the_agent(live_review, outcome, exit_code):
    review = live_review(exit_code)
    assert int(review.tmux("display-message", "-p", "#{history_size}")) > 100
    os.write(review.master, b"\x1b[<64;20;10M" * 5)
    review.wait_for(lambda: review.tmux("display-message", "-p", "#{pane_in_mode}") == "1")
    review.wait_for(lambda: int(review.tmux("display-message", "-p", "#{scroll_position}")) > 0)
    assert review.process.poll() is None, "scrolling interrupted the agent"
    os.write(review.master, b"q")
    review.wait_for(lambda: review.tmux("display-message", "-p", "#{pane_in_mode}") == "0")
    assert "REVIEW-RUNNING" in review.tmux("capture-pane", "-p")
    if outcome == "interrupt":
        os.write(review.master, b"\x03")
    else:
        review.release.touch()
    review.wait_for(lambda: review.process.poll() is not None)
    assert review.process.returncode == exit_code
    assert subprocess.run(
        ["tmux", "-S", review.socket, "list-sessions"], capture_output=True,
    ).returncode != 0, "review scrollback server was left running"


@pytest.mark.skipif(not shutil.which("tmux"), reason="needs tmux")
def test_live_review_shows_progress_above_the_agent(live_review, tmp_path):
    progress = tmp_path / "review.progress"
    review = live_review(GHD_PROGRESS=str(progress))
    panes = review.tmux("list-panes", "-F", "#{pane_height} #{pane_active}").splitlines()
    assert panes[0] == "3 0" and panes[1].endswith(" 1"), panes
    review.wait_for(lambda: "starting" in review.tmux("capture-pane", "-p", "-t", "0"))
    progress.write_text('{"session": "s", "kind": "agent_start", "label": "Security"}\n')
    review.wait_for(lambda: "Security ●" in review.tmux("capture-pane", "-p", "-t", "0"))
    assert "REVIEW-RUNNING" in review.tmux("capture-pane", "-p", "-t", "1")
    assert review.process.poll() is None
    review.release.touch()
    review.wait_for(lambda: review.process.poll() is not None)
    assert review.process.returncode == 0, "the progress pane kept the review open after the agent finished"


@pytest.mark.skipif(not shutil.which("tmux"), reason="needs tmux")
@pytest.mark.parametrize("events, expected, exit_code", [
    ([{"type": "stream_event", "event": {"delta": {"type": "text_delta", "text": "Checking café…"}}},
      {"type": "assistant", "message": {"content": [{"type": "text", "text": "Checking café…"}]}},
      {"type": "result", "is_error": False, "result": "Checking café…"}], "Checking café…", 0),
    ([{"type": "assistant", "message": {"content": [
        {"type": "tool_use", "name": "Bash", "input": {"command": "git diff"}},
    ]}}], "Bash: git diff", 0),
    ([{"type": "assistant", "message": {"content": [
        {"type": "tool_use", "name": "Read", "input": {"file_path": "/repo/src/app.py"}},
    ]}}], "Read: /repo/src/app.py", 0),
    ([{"type": "result", "is_error": True, "errors": ["Review request failed"]}], "Review request failed", 7),
    ([{"type": "assistant", "message": {"content": [
        {"type": "tool_use", "name": "Agent", "input": {"description": "Review accessibility"}},
    ]}}], "Agent: Review accessibility", 130),
])
def test_claude_output_is_visible_before_the_review_finishes(live_review, tmp_path, events, expected, exit_code):
    claude = tmp_path / "claude"
    claude.write_text(f"#!{sys.executable}\n" + """
import os, pathlib, sys, time
assert sys.stdin.read() == ''
assert sys.argv[sys.argv.index('--output-format') + 1] == 'stream-json'
assert '--verbose' in sys.argv and '--include-partial-messages' in sys.argv
print(os.environ['CLAUDE_EVENTS'], flush=True)
pathlib.Path(sys.argv[-3]).write_text(os.environ['TMUX'].split(',')[0])
while not pathlib.Path(sys.argv[-2]).exists():
    time.sleep(.01)
sys.exit(int(sys.argv[-1]))
""")
    claude.chmod(0o755)
    review = live_review(
        exit_code, agent_command=[sys.executable, str(RUNNER.with_name("claude.py"))],
        PATH=f"{tmp_path}:{os.environ['PATH']}",
        CLAUDE_EVENTS="\n".join(json.dumps(event) for event in events),
        GHD_PROGRESS=str(tmp_path / "review.progress"),
    )
    review.wait_for(lambda: expected in review.tmux("capture-pane", "-p", "-t", "1"))
    output = review.tmux("capture-pane", "-p", "-t", "1")
    assert output.count(expected) == 1, output
    assert '"type"' not in output
    assert review.process.poll() is None, "output appeared only after the agent exited"
    if exit_code == 130:
        os.write(review.master, b"\x03")
    else:
        review.release.touch()
    review.wait_for(lambda: review.process.poll() is not None)
    assert review.process.returncode == exit_code
