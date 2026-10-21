#!/usr/bin/env python3
"""Live progress of a running review, fed by the harness rather than the agent.

Usage: ghd progress claude            Claude Code hook: PreToolUse/PostToolUse JSON on stdin
       ghd progress opencode          OpenCode plugin: {sessionID, phase, tool, input, output} on stdin
       ghd progress watch <file>      redraw the summary of a progress file every second

Events are appended to <review>.progress next to the review whose metadata
names the session; events of other sessions are dropped. Reporting never
fails the hook, so the review continues whatever happens here.
"""
from __future__ import annotations

import glob
import json
import os
import sys
import time

STORE = os.environ.get("GHD_STORE") or os.path.expanduser("~/.local/share/gh-dash-reviews")
CHECK = "ghd check"


def normalise(harness: str, raw: dict) -> dict | None:
    if harness == "claude":
        after = raw.get("hook_event_name") == "PostToolUse"
        session, tool, args = raw.get("session_id"), raw.get("tool_name"), raw.get("tool_input") or {}
        response = raw.get("tool_response")
        output = response.get("stdout", "") if isinstance(response, dict) else str(response or "")
        agent, files, shell = tool in ("Agent", "Task"), tool in ("Edit", "Write"), tool == "Bash"
        path = args.get("file_path")
    else:
        after = raw.get("phase") == "after"
        session, tool, args, output = raw.get("sessionID"), raw.get("tool"), raw.get("input") or {}, raw.get("output") or ""
        agent, files, shell = tool == "subagent", tool in ("edit", "write"), tool == "shell"
        path = args.get("path")
    event = {"session": session}
    if agent:
        return {**event, "kind": "agent_end" if after else "agent_start", "label": args.get("description") or tool}
    if not after:
        return None
    if files:
        return {**event, "kind": "file", "label": path}
    if shell and (args.get("command") or "").startswith(CHECK):
        return {**event, "kind": "check", "ok": output.lstrip().startswith("ok")}
    return {**event, "kind": "tool", "label": tool}


def progress_file(session: str) -> str | None:
    for meta in glob.glob(f"{STORE}/*.json"):
        try:
            if json.load(open(meta)).get("session") == session:
                return meta[: -len(".json")] + ".progress"
        except (OSError, ValueError):
            continue
    return None


def record(harness: str, raw: dict) -> None:
    event = normalise(harness, raw)
    file = event and progress_file(event["session"])
    if file:
        with open(file, "a") as out:
            out.write(json.dumps(event) + "\n")


def clock(seconds: float) -> str:
    hours, rest = divmod(int(seconds), 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes}:{secs:02d}"


def summary(events: list[dict], elapsed: float) -> list[str]:
    agents: dict[str, str] = {}
    files: dict[str, str] = {}
    tools = 0
    for event in events:
        kind = event["kind"]
        if kind == "agent_start":
            agents[event["label"]] = "●"
        elif kind == "agent_end":
            agents[event["label"]] = "✓"
        elif kind == "file" and event["label"].endswith((".md", ".findings")):
            files[event["label"].rsplit(".", 1)[1]] = "✓"
        elif kind == "tool":
            tools += 1
    last = events[-1]["kind"] if events else None
    if last == "check":
        phase = "check ok" if events[-1]["ok"] else "check failed"
    elif files:
        phase = "write"
    elif "●" in agents.values():
        phase = "review"
    elif agents:
        phase = "verify"
    else:
        phase = "gather" if events else "starting"
    lines = [f"{clock(elapsed)}  {phase}" + (f"  ·  {tools} tool call{'s' if tools != 1 else ''}" if tools else "")]
    if agents:
        lines.append("  ".join(f"{label} {mark}" for label, mark in agents.items()))
    if files:
        lines.append(f"review {files.get('md', '–')}  findings {files.get('findings', '–')}")
    return lines


def watch(file: str) -> None:
    started = time.monotonic()
    while True:
        try:
            events = [json.loads(line) for line in open(file) if line.strip()]
        except (OSError, ValueError):
            events = []
        sys.stdout.write("\033[H\033[J " + "\n ".join(summary(events, time.monotonic() - started)) + "\n")
        sys.stdout.flush()
        time.sleep(1)


def main(argv: list[str]) -> None:
    if argv[:1] == ["watch"]:
        return watch(argv[1])
    try:
        record(argv[0], json.load(sys.stdin))
    except (ValueError, OSError, IndexError, AttributeError):
        pass


if __name__ == "__main__":
    main(sys.argv[1:])
