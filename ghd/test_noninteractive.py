import os
import fcntl
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


@pytest.mark.skipif(not shutil.which("tmux"), reason="needs tmux")
@pytest.mark.parametrize("outcome, exit_code", [("success", 0), ("failure", 7), ("interrupt", 130)])
def test_live_review_can_scroll_without_interrupting_the_agent(tmp_path, outcome, exit_code):
    socket_file = tmp_path / "socket"
    release = tmp_path / "release"
    master, slave = pty.openpty()
    fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 20, 80, 0, 0))
    agent = """
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
    process = subprocess.Popen(
        [sys.executable, str(RUNNER), sys.executable, "-c", agent, str(socket_file), str(release), str(exit_code)],
        stdin=slave, stdout=slave, stderr=slave,
        env={**os.environ, "TMUX": "/outer-dashboard,1,0", "TERM": "xterm-256color"},
    )

    def wait_for(predicate):
        deadline = time.monotonic() + 5
        while not predicate():
            assert time.monotonic() < deadline, "live review did not reach the expected state"
            if select.select([master], [], [], .02)[0]:
                os.read(master, 65536)

    try:
        wait_for(socket_file.exists)
        socket = socket_file.read_text()
        assert socket != "/outer-dashboard", "live output has no independent scrollback"

        def tmux(*args):
            return subprocess.check_output(["tmux", "-S", socket, *args], text=True).strip()

        assert int(tmux("display-message", "-p", "#{history_size}")) > 100
        os.write(master, b"\x1b[<64;20;10M" * 5)
        wait_for(lambda: tmux("display-message", "-p", "#{pane_in_mode}") == "1")
        wait_for(lambda: int(tmux("display-message", "-p", "#{scroll_position}")) > 0)
        assert process.poll() is None, "scrolling interrupted the agent"
        os.write(master, b"q")
        wait_for(lambda: tmux("display-message", "-p", "#{pane_in_mode}") == "0")
        assert "REVIEW-RUNNING" in tmux("capture-pane", "-p")
        if outcome == "interrupt":
            os.write(master, b"\x03")
        else:
            release.touch()
        wait_for(lambda: process.poll() is not None)
        assert process.returncode == exit_code
        assert subprocess.run(
            ["tmux", "-S", socket, "list-sessions"], capture_output=True,
        ).returncode != 0, "review scrollback server was left running"
    finally:
        release.touch()
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)
        os.close(master)
        os.close(slave)
