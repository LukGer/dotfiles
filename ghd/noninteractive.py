#!/usr/bin/env python3
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import termios


def run_with_scrollback():
    tmux = ["tmux", "-L", f"ghd-review-{os.getpid()}"]
    env = {key: value for key, value in os.environ.items() if key not in ("TMUX", "TMUX_PANE")}
    with tempfile.TemporaryDirectory(prefix="ghd-review-") as directory:
        result = Path(directory) / "exit-code"
        env["GHD_REVIEW_SCROLLBACK"] = str(result)
        try:
            status = subprocess.call([
                *tmux, "-f", str(Path(__file__).with_name("tmux.conf")),
                "new-session", "-s", "review", sys.executable, str(Path(__file__).resolve()), *sys.argv[1:],
            ], env=env)
            return int(result.read_text()) if result.exists() else status or 1
        except KeyboardInterrupt:
            return 130
        finally:
            subprocess.run([*tmux, "kill-server"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main():
    if sys.stdin.isatty() and os.environ.get("TMUX") and not os.environ.get("GHD_REVIEW_SCROLLBACK"):
        return run_with_scrollback()

    terminal = sys.stdin.fileno() if sys.stdin.isatty() else None
    original = termios.tcgetattr(terminal) if terminal is not None else None
    try:
        if terminal is not None:
            quiet = termios.tcgetattr(terminal)
            quiet[3] &= ~(termios.ECHO | termios.ECHONL)
            termios.tcsetattr(terminal, termios.TCSAFLUSH, quiet)
        return subprocess.call(sys.argv[1:], stdin=subprocess.DEVNULL)
    except KeyboardInterrupt:
        return 130
    finally:
        if terminal is not None:
            termios.tcsetattr(terminal, termios.TCSAFLUSH, original)


if __name__ == "__main__":
    status = main()
    if result := os.environ.get("GHD_REVIEW_SCROLLBACK"):
        Path(result).write_text(str(status))
    sys.exit(status)
