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


@pytest.fixture(scope="module", autouse=True)
def built_review_screen():
    # The test's empty MISE_DATA_DIR has no Go toolchain, so build with the real one first.
    subprocess.run([str(ROOT / "ghd/tui")], capture_output=True, timeout=600)


@pytest.mark.skipif(any(not shutil.which(name) for name in ("tmux", "glow")),
                    reason="needs tmux and glow")
@pytest.mark.parametrize("key, instructions, tool, paragraphs, action, response", [
    (b"\x1b", "", None, 0, None, None), (b"q", "", None, 0, None, None),
    (b"1", "", "pi", 1, b"p", b"nothing selected"),
    (b"2", "quality only, skip gen/", "pi", 80, b"c", b"CONVERSATION-READY"),
])
def test_review_menu_waits_for_selection_before_returning_to_dashboard(tmp_path, key, instructions, tool, paragraphs, action, response):
    tmux = ["tmux", "-L", f"ghd-test-{uuid.uuid4().hex}"]
    record = tmp_path / "calls.jsonl"
    stub = tmp_path / "stub"
    stub.write_text("""#!/usr/bin/env python3
import json, os, pathlib, sys, termios, time
name = pathlib.Path(sys.argv[0]).name
args = sys.argv[1:]
with open(os.environ['CALLS'], 'a') as f:
    f.write(json.dumps([name, *args]) + '\\n')
if name == 'gh':
    if args[:1] == ['api']:
        pull = {'title': 'A review', 'body': '', 'user': {'login': 'author'}, 'head': {'ref': 'feature'}, 'base': {'ref': 'main'}}
        print(json.dumps([pull] if next(a for a in args if a.startswith('repos/')).split('/')[-1].isdigit() else [[]]))
    else:
        print('A review\\tauthor\\t1234567890\\tmain')
elif name == 'git':
    sys.exit(1)
elif name in ('opencode', 'claude', 'pi'):
    if args[0] in ('--session', '--resume'):
        print('CONVERSATION-READY', flush=True)
        sys.exit(0)
    print('REVIEW-RUNNING', flush=True)
    deadline = time.monotonic() + 5
    while not pathlib.Path(os.environ['RELEASE_AGENT']).exists():
        assert time.monotonic() < deadline, 'agent was never released'
        time.sleep(.01)
    for line in args[-1].splitlines():
        if line.startswith(('review_file: ', 'findings_file: ')):
            file = pathlib.Path(line.split(': ', 1)[1])
            file.write_text('# REVIEW-READY\\n\\n' + 'Review paragraph.\\n\\n' * int(os.environ['REVIEW_PARAGRAPHS'])
                            + 'REVIEW-END\\n' if file.suffix == '.md' else '{"tldr": "stub", "findings": []}')
elif name == 'glow':
    assert termios.tcgetattr(sys.stdin.fileno())[3] & termios.ECHO, 'input was not restored'
    os.execv(os.environ['REAL_GLOW'], ['glow', *args])
""")
    stub.chmod(0o755)
    for name in ("osascript", "gh", "git", "opencode", "claude", "pi", "glow"):
        (tmp_path / name).symlink_to(stub)
    env = {**os.environ, "PATH": f"{tmp_path}:{os.environ['PATH']}", "TERM": "xterm-256color",
           "MISE_DATA_DIR": str(tmp_path / "mise"),  # zshenv puts mise's shims first; keep the stubbed pi ahead of the real one
           "CALLS": str(record), "GHD_STORE": str(tmp_path / "reviews"),
           "RELEASE_AGENT": str(tmp_path / "release"),
           "REAL_GLOW": shutil.which("glow"), "REVIEW_PARAGRAPHS": str(paragraphs),
           "PAGER": "less -R", "LESS": "",
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
        while not all(label in output for label in (b"GPT-6.1 Sol", b"Opus 5.5", b"pi", b"Past reviews", b"Post to GitHub")):
            assert time.monotonic() < deadline, "menu did not draw all choices"
            if select.select([master], [], [], .05)[0]:
                output += os.read(master, 65536)
        time.sleep(.05)
        assert menu.poll() is None, "menu returned before selection; dashboard can repaint over it"
        os.write(master, key)
        if tool:
            output = b""
            deadline = time.monotonic() + 5
            while b"Instructions" not in output:
                assert time.monotonic() < deadline, f"choosing a model did not ask for instructions: {output[-800:]!r}"
                if select.select([master], [], [], .05)[0]:
                    output += os.read(master, 65536)
            os.write(master, instructions.encode() + b"\r")
            output = b""
            deadline = time.monotonic() + 5
            while b"REVIEW-RUNNING" not in output:
                assert time.monotonic() < deadline, "review did not start"
                if select.select([master], [], [], .05)[0]:
                    output += os.read(master, 65536)
            os.write(master, b"ignored-input\np\n")
            if select.select([master], [], [], .1)[0]:
                output += os.read(master, 65536)
            assert b"ignored-input" not in output, "typing was echoed during the review"
            (tmp_path / "release").touch()
            deadline = time.monotonic() + 15
            while b"p post" not in output:
                assert time.monotonic() < deadline, f"the review screen did not open after the review: {output[-800:]!r}"
                if select.select([master], [], [], .05)[0]:
                    output += os.read(master, 65536)
            assert b"\a" in output, "completion bell did not reach the outer terminal"

            def expect(text, failure):
                nonlocal output
                deadline = time.monotonic() + 10
                while text not in output:
                    assert time.monotonic() < deadline, f"{failure}: {output[-800:]!r}"
                    if select.select([master], [], [], .05)[0]:
                        output += os.read(master, 65536)

            assert b"nothing selected" not in output, "queued typing chose to post"
            assert menu.poll() is None, "posting should remain a user choice"
            os.write(master, b"\t")
            expect(b"REVIEW-READY", "tab did not show the review text")
            os.write(master, b"\t")
            os.write(master, action)
            output = b""
            expect(response, "action required Enter after its shortcut")
            expect(b"p post", "action did not return to the review screen")
            os.write(master, b"q")
        stdout, stderr = menu.communicate(timeout=5)
        assert menu.returncode == 0, stderr.decode()
        if tool:
            calls = [json.loads(line) for line in record.read_text().splitlines()]
            brief = next(args for name, *args in calls if name == tool)[-1]
            assert ("Instructions from the human" in brief) == bool(instructions)
            assert brief.endswith(instructions)
            assert not any(name == "osascript" for name, *_ in calls)
        else:
            assert not record.exists()
    finally:
        subprocess.run([*tmux, "kill-server"], env=env, capture_output=True)
        for process in (menu, client):
            if process and process.poll() is None:
                process.kill()
                process.wait(timeout=5)
        os.close(master)
        os.close(slave)
