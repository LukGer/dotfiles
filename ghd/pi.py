#!/usr/bin/env python3
"""Run pi headless and render its JSON events as they stream.

Usage: pi.py <pi arguments...>   (ghd review adds --mode json itself)

Prints assistant text as it is generated and one line per tool call. pi exits 0
when the provider fails, so the exit status here is 1 whenever an assistant
message ended in an error.
"""
import json
import subprocess
import sys

DETAIL_KEYS = ("specialist", "title", "path", "command", "pattern", "code")


def detail(name: str, args: dict) -> str:
    value = next((args[key] for key in DETAIL_KEYS if args.get(key)), "")
    first = str(value).strip().splitlines()[0] if value else ""
    return f"{first[:100]}…" if len(first) > 100 else first


def render(line: str, out) -> str | None:
    try:
        event = json.loads(line)
    except json.JSONDecodeError:
        out.write(line)
        return None
    kind = event.get("type")
    if kind == "message_update":
        delta = event.get("assistantMessageEvent", {})
        if delta.get("type") == "text_delta":
            out.write(delta["delta"])
    elif kind == "tool_execution_start" and not event.get("parentToolCallId"):
        out.write(f"\n{event['toolName']}: {detail(event['toolName'], event.get('args') or {})}\n")
    elif kind == "message_end":
        message = event.get("message") or {}
        if message.get("role") == "assistant" and message.get("stopReason") == "error":
            return message.get("errorMessage") or "pi reported an error"
    out.flush()
    return None


def main() -> int:
    command = ["pi", *sys.argv[1:]]
    error = None
    with subprocess.Popen(command, stdout=subprocess.PIPE, text=True) as process:
        for line in process.stdout:
            error = render(line, sys.stdout) or error
        print(flush=True)
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
