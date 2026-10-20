import fcntl
import json
import os
from pathlib import Path
import pty
import select
import shutil
import struct
import subprocess
import termios
import time
import uuid

import pytest


ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.skipif(not shutil.which("tmux") or not shutil.which("fzf"), reason="needs tmux and fzf")
@pytest.mark.parametrize("key, tool", [(b"\x1b", None), (b"q", None), (b"1", "claude"), (b"2", "codex")])
def test_review_menu_waits_for_selection_before_returning_to_dashboard(tmp_path, key, tool):
    tmux = ["tmux", "-L", f"ghd-test-{uuid.uuid4().hex}"]
    record = tmp_path / "calls.jsonl"
    stub = tmp_path / "stub"
    stub.write_text("""#!/usr/bin/env python3
import json, os, pathlib, sys
name = pathlib.Path(sys.argv[0]).name
args = sys.argv[1:]
with open(os.environ['CALLS'], 'a') as f:
    f.write(json.dumps([name, *args]) + '\\n')
if name == 'gh':
    print('A review\\tauthor\\t1234567890\\tmain')
elif name == 'git':
    sys.exit(1)
elif name in ('codex', 'claude'):
    for line in args[-1].splitlines():
        if line.startswith(('review_file: ', 'findings_file: ')):
            pathlib.Path(line.split(': ', 1)[1]).write_text('{}')
elif name == 'glow':
    print('REVIEW-READY', flush=True)
    input()
""")
    stub.chmod(0o755)
    for name in ("osascript", "gh", "git", "codex", "claude", "glow"):
        (tmp_path / name).symlink_to(stub)
    env = {**os.environ, "PATH": f"{tmp_path}:{os.environ['PATH']}", "TERM": "xterm-256color",
           "CALLS": str(record), "GHD_STORE": str(tmp_path / "reviews"),
           "GHD_CODE_DIR": str(tmp_path / "missing")}
    master, slave = pty.openpty()
    fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 40, 120, 0, 0))
    client = menu = None

    def command(*args):
        return subprocess.check_output([*tmux, *args], env=env, text=True).strip()

    try:
        command("-f", str(ROOT / "ghd/tmux.conf"), "new-session", "-d", "-s", "test", "sleep", "60")
        client = subprocess.Popen([*tmux, "attach", "-t", "test"], stdin=slave, stdout=slave, stderr=slave, env=env)
        deadline = time.monotonic() + 5
        while not command("list-clients"):
            assert time.monotonic() < deadline, "client did not attach"
            time.sleep(.01)
        menu = subprocess.Popen(
            [str(ROOT / "bin/ghd"), "review", "owner/repo", "42"],
            env={**env, "TMUX": command("display-message", "-p", "#{socket_path},#{pid},0"),
                 "TERM_PROGRAM": "ghostty"},
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        output = b""
        deadline = time.monotonic() + 5
        while not all(label in output for label in (b"Claude", b"Codex", b"Past reviews", b"Post to GitHub")):
            assert time.monotonic() < deadline, "menu did not draw all choices"
            if select.select([master], [], [], .05)[0]:
                output += os.read(master, 65536)
        time.sleep(.05)
        assert menu.poll() is None, "menu returned before selection; dashboard can repaint over it"
        os.write(master, key)
        if tool:
            output = b""
            deadline = time.monotonic() + 5
            while b"REVIEW-READY" not in output:
                assert time.monotonic() < deadline, "completed review was not shown in the popup"
                if select.select([master], [], [], .05)[0]:
                    output += os.read(master, 65536)
            assert menu.poll() is None, "review viewer should stay open until dismissed"
            os.write(master, b"\n")
            output = b""
            deadline = time.monotonic() + 5
            while b"choose findings to post" not in output:
                assert time.monotonic() < deadline, "posting prompt was not shown after the review"
                if select.select([master], [], [], .05)[0]:
                    output += os.read(master, 65536)
            assert menu.poll() is None, "posting should remain a user choice"
            os.write(master, b"\n")
        stdout, stderr = menu.communicate(timeout=5)
        assert menu.returncode == 0, stderr.decode()
        if tool:
            calls = [json.loads(line) for line in record.read_text().splitlines()]
            assert any(name == tool for name, *_ in calls)
            assert any(name == "glow" for name, *_ in calls)
            assert not any(name == "osascript" for name, *_ in calls)
        else:
            assert not record.exists()
    finally:
        subprocess.run([*tmux, "kill-server"], env=env, capture_output=True)
        for process in (menu, client):
            if process and process.poll() is None:
                process.terminate()
                process.wait(timeout=5)
        os.close(master)
        os.close(slave)
