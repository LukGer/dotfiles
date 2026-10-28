import json
from pathlib import Path
import subprocess
import sys
import tempfile


LIB = Path(__file__).resolve().parent


def screen(request: dict) -> dict | None:
    with tempfile.TemporaryDirectory(prefix="ghd-screen-") as directory:
        source, result = Path(directory) / "request.json", Path(directory) / "result.json"
        source.write_text(json.dumps(request))
        subprocess.run([str(LIB / "tui"), "screen", str(source), str(result)], check=True)
        return json.loads(result.read_text()) if result.exists() else None


def choose(title: str, items: list[dict], *, copy: bool = False) -> int | None:
    result = screen({"title": title, "items": items, "copy": copy})
    return result["index"] if result is not None else None


def review_screen(prefix: str, *, dry: bool = False) -> None:
    subprocess.run([str(LIB / "tui"), prefix, *(["--dry"] if dry else [])], check=True)


def reviewer(meta: dict) -> str:
    """`tool model` for a saved review, with the provider and thinking level dropped from pi models."""
    model = (meta.get("model") or "").rsplit("/", 1)[-1].split(":")[0]
    return f"{meta['tool']} {model}".strip()


def pause(message: str) -> None:
    if sys.stdin.isatty() and sys.stdout.isatty():
        screen({"title": "ghd", "message": message})
    else:
        print(message)
