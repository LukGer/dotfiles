import sys
import termios
import tty


def choice(prompt: str, keys: str) -> str:
    terminal = sys.stdin.isatty()
    original = termios.tcgetattr(sys.stdin) if terminal else None
    try:
        if terminal:
            tty.setcbreak(sys.stdin, termios.TCSANOW)
        print(prompt, end="", flush=True)
        while True:
            key = sys.stdin.read(1).lower()
            if not key or key == "\x04" or key in keys:
                print()
                return "" if key == "\x04" else key
    except KeyboardInterrupt:
        raise SystemExit(130)
    finally:
        if terminal:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, original)


def reviewer(meta: dict) -> str:
    """`tool model` for a saved review, with the provider and thinking level dropped from pi models."""
    model = (meta.get("model") or "").rsplit("/", 1)[-1].split(":")[0]
    return f"{meta['tool']} {model}".strip()


def pause(message: str) -> None:
    print(message)
    choice("\n[enter/esc/q] close > ", "\r\n\x1bq")
