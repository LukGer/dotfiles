import os
from pathlib import Path
import pty
import select
import signal
import subprocess
import sys
import termios

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
