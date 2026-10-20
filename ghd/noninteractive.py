#!/usr/bin/env python3
import subprocess
import sys
import termios


def main():
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
    sys.exit(main())
