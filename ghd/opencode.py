#!/usr/bin/env python3
"""Render OpenCode V2's headless JSON stream outside the review screen."""
import json
import subprocess
import sys

from pi import detail


def render(line, out):
    try:
        event = json.loads(line)
    except json.JSONDecodeError:
        out.write(line)
        return None
    part = event.get("part") or {}
    if event.get("type") == "text":
        out.write(part.get("text", "") + "\n")
    elif event.get("type") == "tool_use":
        state = part.get("state") or {}
        out.write(f"\n{part.get('tool', 'tool')}: {detail('', state.get('input') or {})}\n")
    elif event.get("type") == "error":
        error = event.get("error") or {}
        return error.get("message") or error.get("data", {}).get("message") or "OpenCode reported an error"
    out.flush()
    return None


def main():
    error = None
    with subprocess.Popen(["opencode", *sys.argv[1:]], stdout=subprocess.PIPE, text=True) as process:
        for line in process.stdout:
            error = render(line, sys.stdout) or error
        status = process.wait()
    if error:
        print(error, file=sys.stderr, flush=True)
        return 1
    return status


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
